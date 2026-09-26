"""HUST ticket monitor. Python 3.12+; pip install playwright requests.

First run: python hust_bot.py --setup
Run:       python hust_bot.py
Uses the site's normal buttons, including its confirmation dialog.
No password, cookie or HUST token is exported. Never cancels tickets.
If the Office 365 session expires, the bot can reuse credentials already
saved/autofilled by Chromium; it never stores, logs or transmits the password.
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import re
import secrets
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent
URL = "https://ctsv.hust.edu.vn/dat-ve"
LOGIN_HOST = "asso.hust.edu.vn"
CONFIG = ROOT / "config.json"
STATE = ROOT / "state.json"
PROFILE = ROOT / "browser-profile"
OUTBOX = ROOT / "telegram-outbox.json"


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        raise RuntimeError(f"Khong doc duoc {path.name}. Dung bot va kiem tra file.") from None


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def telegram(token, method, data=None):
    # Never propagate requests exceptions: their text can contain the bot token.
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}",
                          json=data or {}, timeout=(5, 15))
        result = r.json()
        if r.status_code != 200 or not result.get("ok"):
            raise RuntimeError(f"Telegram tra loi loi HTTP {r.status_code}; kiem tra token/mang.")
        return result["result"]
    except (requests.RequestException, ValueError):
        raise RuntimeError("Khong ket noi duoc Telegram. Kiem tra mang va token.") from None


def setup():
    print("CAI DAT TELEGRAM - token chi luu tren may nay, khong gui cho nguoi khac.")
    token = getpass.getpass("Paste token BotFather, roi Enter (khong hien ky tu): ").strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise RuntimeError("Token sai dinh dang. Chay lai --setup.")
    me = telegram(token, "getMe")
    if telegram(token, "getWebhookInfo").get("url"):
        raise RuntimeError("Bot Telegram nay dang dung webhook. Hay tao bot rieng cho chuong trinh.")
    code = "HUST-" + secrets.token_hex(4).upper()
    print(f"\nMo Telegram -> @{me['username']} -> bam Start.")
    print(f"Gui DUNG tin nhan nay vao bot: {code}")
    offset = None
    while True:
        input("Gui xong, quay lai CMD va nhan Enter: ")
        args = {"timeout": 0, "allowed_updates": ["message"]}
        if offset is not None:
            args["offset"] = offset
        updates = telegram(token, "getUpdates", args)
        chat_id = None
        for item in updates:
            offset = item["update_id"] + 1
            msg = item.get("message", {})
            if msg.get("text", "").strip() == code and msg.get("chat", {}).get("type") == "private":
                chat_id = msg["chat"]["id"]
        if chat_id is not None:
            break
        print("Chua thay ma. Kiem tra dung bot va gui lai ma tren.")
    telegram(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "Ket noi HUST bot thanh cong. Bot CHUA chay; hay chay hust_bot.py tren may tinh.",
    })
    write_json(CONFIG, {"telegram_token": token, "telegram_chat_id": chat_id,
                        "interval_seconds": 0.5, "auto_register": True})
    print("\nDA KET NOI TELEGRAM. Bay gio chay: .venv\\Scripts\\python.exe hust_bot.py")


class Notifier:
    """A persistent queue: Telegram latency never blocks ticket registration."""
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        self.items = read_json(OUTBOX, [])
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.thread.start()

    def send(self, text):
        with self.lock:
            self.items.append({"id": secrets.token_hex(8),
                               "text": time.strftime("[%d/%m %H:%M:%S] ") + text[:3600]})
            write_json(OUTBOX, self.items)

    def work(self):
        retry = 15
        while not self.stop.is_set():
            with self.lock:
                item = self.items[0] if self.items else None
            if item is None:
                self.stop.wait(0.5)
                continue
            try:
                telegram(self.config["telegram_token"], "sendMessage", {
                    "chat_id": self.config["telegram_chat_id"], "text": item["text"],
                    "link_preview_options": {"is_disabled": True},
                })
                with self.lock:
                    self.items = [x for x in self.items if x["id"] != item["id"]]
                    write_json(OUTBOX, self.items)
                retry = 15
                self.stop.wait(1)
            except Exception:
                logging.warning("Chua gui duoc Telegram; tin duoc giu trong hang doi de thu lai.")
                self.stop.wait(retry)
                retry = min(retry * 2, 300)


class SiteError(RuntimeError):
    def __init__(self, message, wait=0):
        super().__init__(message)
        self.wait = wait


def api_response(response, action):
    if response.status == 429:
        value = response.headers.get("retry-after", "60")
        try:
            delay = max(60, int(value))
        except ValueError:
            from email.utils import parsedate_to_datetime
            try:
                delay = max(60, parsedate_to_datetime(value).timestamp() - time.time())
            except Exception:
                delay = 60
        raise SiteError("Website gioi han truy cap (429). Tam dung theo Retry-After.", delay)
    if response.status in (401, 403):
        raise SiteError("Phien dang nhap/ quyen truy cap khong hop le. Kiem tra trinh duyet.", 60)
    if response.status != 200:
        raise SiteError(f"{action}: HTTP {response.status}", 30)
    try:
        data = response.json()
    except Exception:
        raise SiteError("Website khong tra JSON hop le.", 30) from None
    if not isinstance(data, dict) or "RespCode" not in data:
        raise SiteError("Cau truc phan hoi da thay doi. Can kiem tra lai bot.", 60)
    return data


def matches(response, suffix):
    return (response.request.method == "POST" and
            urlparse(response.url).path.rstrip("/").lower().endswith(suffix.lower()))


def eligible(event):
    if event.get("State") != "OPEN" or event.get("MyTicket") or event.get("BlockedBy"):
        return False
    # Capacity <= 0 means unlimited in the site's own UI.
    capacity = event.get("Capacity")
    remaining = event.get("Remaining")
    return (isinstance(capacity, (int, float)) and
            (capacity <= 0 or (isinstance(remaining, (int, float)) and remaining > 0)))


def describe(event):
    return (f"{event.get('Title', '(khong ten)')}\n"
            f"Thoi gian: {event.get('StartTime') or '?'}\n"
            f"Dia diem: {event.get('Location') or '?'}\n"
            f"Trang thai: {event.get('StateText') or event.get('State')}\n"
            f"Con cho: {event.get('Remaining', '?')}\n{URL}")


def _visible(locator):
    """Return visible matches without relying on a locator being unique."""
    result = []
    for index in range(locator.count()):
        item = locator.nth(index)
        try:
            if item.is_visible():
                result.append(item)
        except Exception:
            pass
    return result


def _click_visible_button(page, label, timeout=5000):
    # Some CTSV buttons contain an icon and wrap their caption across lines,
    # which makes the accessibility name differ from the visible text. Search
    # both semantic buttons and raw clickable elements by contained text.
    groups = [
        page.get_by_role("button", name=label, exact=False),
        page.locator("button, [role='button'], a").filter(has_text=label),
    ]
    for group in groups:
        # The login prompt can leave a second button in the dimmed background;
        # the modal's foreground button is normally the last DOM match.
        for button in reversed(_visible(group)):
            try:
                if button.is_enabled():
                    button.click(timeout=timeout)
                    return True
            except Exception:
                # A matched, visible login button is safe to force-click if an
                # overlay/animation briefly confuses Playwright hit testing.
                try:
                    if button.is_visible() and button.is_enabled():
                        button.click(timeout=timeout, force=True)
                        return True
                except Exception:
                    continue
    return False


def _wait_for_autofill(locator, timeout_ms=10000):
    """Wait for an autofilled field without retaining or logging its value."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if locator.count() and locator.first.is_visible() and locator.first.input_value():
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def recover_login(page, notify):
    """Recover the known HUST ADFS flow using Chromium's saved credentials.

    Known flows (verified from the user's screenshots):
    - Phien Office 365 da het han -> Dang nhap lai
    - Can dang nhap Office 365 -> Dang nhap Office 365
    Then: Next -> Sign in -> /dat-ve.
    Unknown pages, empty autofill fields, CAPTCHA and MFA require manual action.
    """
    parsed = urlparse(page.url)
    on_login_site = parsed.hostname == LOGIN_HOST
    login_prompts = (
        "Phiên Office 365 đã hết hạn",
        "Cần đăng nhập Office 365",
    )
    login_buttons = (
        "Đăng nhập lại",
        "Đăng nhập Office 365",
    )
    prompt_visible = any(
        _visible(page.get_by_text(text, exact=True)) for text in login_prompts
    )
    button_visible = any(
        _visible(page.get_by_role("button", name=label, exact=True))
        for label in login_buttons
    )
    if not on_login_site and not prompt_visible and not button_visible:
        return False

    logging.warning("Phat hien phien HUST het han; dang thu dang nhap lai bang autofill.")
    notify.send("PHIEN HUST DA HET HAN. Bot dang thu dang nhap lai bang thong tin Chrome da luu.")

    if parsed.hostname == "ctsv.hust.edu.vn":
        clicked = any(_click_visible_button(page, label) for label in login_buttons)
        if not clicked:
            raise SiteError("Khong bam duoc nut dang nhap Office 365; can dang nhap thu cong.", 30)

    deadline = time.monotonic() + 60
    clicked_next = False
    clicked_sign_in = False
    while time.monotonic() < deadline:
        parsed = urlparse(page.url)
        if parsed.hostname == "ctsv.hust.edu.vn":
            # ADFS normally preserves /dat-ve in its state. Navigate there only
            # if it returned to another CTSV page.
            if parsed.path.rstrip("/") != "/dat-ve":
                page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            page.locator("button.ev-refresh").wait_for(state="visible", timeout=15000)
            logging.info("Tu dong dang nhap lai HUST thanh cong.")
            notify.send("DA TU DANG NHAP LAI HUST. Bot tiep tuc theo doi.")
            return True

        if parsed.hostname == LOGIN_HOST:
            password = page.locator(
                "#passwordInput:visible, input[name='Password']:visible, input[type='password']:visible"
            )
            if password.count() and password.first.is_visible():
                if clicked_sign_in:
                    time.sleep(0.2)
                    continue
                if not _wait_for_autofill(password.first):
                    raise SiteError(
                        "Chrome khong tu dien mat khau; can dang nhap thu cong trong cua so bot.", 30
                    )
                if not _click_visible_button(page, "Sign in"):
                    raise SiteError("Khong bam duoc nut Sign in; can dang nhap thu cong.", 30)
                clicked_sign_in = True
                time.sleep(0.3)
                continue

            username = page.locator(
                "#userNameInput:visible, input[name='UserName']:visible, input[type='email']:visible"
            )
            if username.count() and username.first.is_visible():
                if clicked_next:
                    time.sleep(0.2)
                    continue
                if not _wait_for_autofill(username.first, timeout_ms=5000):
                    raise SiteError(
                        "Chrome khong tu dien tai khoan; can dang nhap thu cong trong cua so bot.", 30
                    )
                if not _click_visible_button(page, "Next"):
                    raise SiteError("Khong bam duoc nut Next; can dang nhap thu cong.", 30)
                clicked_next = True
                time.sleep(0.3)
                continue

        # Redirects and page painting can briefly leave no usable controls.
        time.sleep(0.2)

    raise SiteError(
        "Dang nhap lai khong hoan tat trong 60s (co the co MFA/CAPTCHA); can xu ly thu cong.", 30
    )


def refresh(page):
    # Click the actual site button. Listen only; never forge an authenticated API call.
    with page.expect_response(lambda r: matches(r, "/Event/GetEvents"), timeout=20000) as info:
        page.locator("button.ev-refresh").click(timeout=12000)
    data = api_response(info.value, "Lam moi")
    if data["RespCode"] != 0:
        raise SiteError("Khong lay duoc danh sach: " + str(data.get("RespText", "kiem tra dang nhap")), 30)
    events = data.get("Events")
    if not isinstance(events, list) or any(not isinstance(e, dict) or "Id" not in e for e in events):
        raise SiteError("Danh sach su kien khong dung cau truc; khong dang ky.", 60)
    from playwright.sync_api import expect
    expect(page.locator("button.ev-refresh")).to_be_enabled(timeout=10000)
    return events


def close_event_dialogs(page):
    for selector, label in [(".ev-success-dialog:visible", "Đã hiểu"),
                            (".ev-dialog:visible", "Đóng")]:
        dialog = page.locator(selector)
        if dialog.count() == 1:
            dialog.get_by_role("button", name=label, exact=True).click(timeout=5000)


def register(page, event, state, notify):
    from playwright.sync_api import expect
    api_title = " ".join(str(event["Title"]).split())
    # The user accepts any event. The API response may arrive just before Vue
    # repaints the page, so briefly wait for ANY visible, enabled Register button
    # and greedily take the first one from top to bottom.
    row = None
    button = None
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        rows = page.locator(".ev-row")
        for index in range(rows.count()):
            candidate = rows.nth(index)
            candidate_button = candidate.get_by_role(
                "button", name="Đăng ký", exact=True
            )
            if (candidate_button.count() == 1 and
                    candidate_button.is_visible() and
                    candidate_button.is_enabled()):
                row = candidate
                button = candidate_button
                break
        if row is not None:
            break
        page.wait_for_timeout(25)
    if row is None:
        raise SiteError("API bao co cho nhung giao dien chua co nut Dang ky dang bat: " + api_title, 5)
    button.click(timeout=5000)
    dialog = page.locator(".ev-dialog:visible")
    expect(dialog).to_be_visible(timeout=5000)
    dialog_title = dialog.locator(".el-dialog__title")
    expect(dialog_title).not_to_be_empty(timeout=5000)
    title = " ".join(dialog_title.inner_text().split())
    logging.info("DANG DANG KY: %s", title)
    confirm = dialog.get_by_role("button", name="Xác nhận đăng ký", exact=True)
    expect(confirm).to_be_enabled(timeout=5000)
    # Before the request is sent, the chosen row's EventId is not exposed in the
    # DOM. Store a provisional record, then move it to the actual ID as soon as
    # the site's own Register request is observed.
    provisional_id = "unknown:" + secrets.token_hex(8)
    state["pending"][provisional_id] = {
        "title": title, "time": time.time(), "warned": False
    }
    write_json(STATE, state)
    captured = {"event_id": None}

    def capture_register_request(request):
        if (request.method != "POST" or
                not urlparse(request.url).path.rstrip("/").lower().endswith("/event/register")):
            return
        try:
            payload = request.post_data_json
        except Exception:
            return
        if not isinstance(payload, dict) or payload.get("EventId") is None:
            return
        actual_id = str(payload["EventId"])
        captured["event_id"] = actual_id
        pending = state["pending"].pop(provisional_id, None)
        if pending is not None:
            state["pending"][actual_id] = pending
            write_json(STATE, state)

    page.on("request", capture_register_request)
    try:
        with page.expect_response(lambda r: matches(r, "/Event/Register"), timeout=20000) as info:
            confirm.click(timeout=5000)
        response = info.value
        payload = response.request.post_data_json
        if not isinstance(payload, dict) or payload.get("EventId") is None:
            raise SiteError("Khong doc duoc ID that cua yeu cau dang ky.", 60)
        actual_event_id = str(payload["EventId"])
        event_id = captured["event_id"] or actual_event_id
        if provisional_id in state["pending"]:
            pending = state["pending"].pop(provisional_id)
            state["pending"][event_id] = pending
            write_json(STATE, state)
        result = api_response(response, "Dang ky")
        if result["RespCode"] != 0:
            state["pending"].pop(event_id, None)
            state["cooldown"][event_id] = time.time() + 0.5
            write_json(STATE, state)
            notify.send("CHUA DANG KY DUOC: " + title + "\n" + str(result.get("RespText", "May chu tu choi")))
        else:
            logging.info("May chu da nhan; dang cho xac minh ve: %s", title)
    except Exception:
        if captured["event_id"] is None:
            # No Register request left the browser, so a retry is safe.
            state["pending"].pop(provisional_id, None)
            write_json(STATE, state)
        else:
            notify.send("CAN KIEM TRA VE: " + title +
                        "\nKhong ro ket qua sau buoc xac nhan. Bot se kiem tra Ve cua toi; "
                        "khong tu bam lai su kien nay khi chua ro.\n" + URL)
        raise
    finally:
        page.remove_listener("request", capture_register_request)


def reconcile(events, state, notify):
    old = state["events"]
    current = {}
    # If a duplicate-title row was selected and the response was lost, its
    # actual EventId may be unknown. A ticket with the attempted exact title is
    # still enough to verify that one of the accepted sessions succeeded.
    for pending_id, pending in list(state["pending"].items()):
        ticket_event = next((event for event in events
                             if event.get("MyTicket") and
                             " ".join(str(event.get("Title", "")).split()) == pending["title"]), None)
        if ticket_event is not None:
            notify.send("DA XAC MINH CO VE!\n" + describe(ticket_event) +
                        "\nXem ma ve tai muc Ve cua toi tren website.")
            logging.info("THANH CONG: %s", ticket_event.get("Title"))
            del state["pending"][pending_id]
    for event in events:
        key = str(event["Id"])
        available = eligible(event)
        current[key] = {"available": available, "state": event.get("State")}
        ticket = event.get("MyTicket")
        if key in state["pending"]:
            pending = state["pending"][key]
            if ticket:
                notify.send("DA XAC MINH CO VE!\n" + describe(event) +
                            "\nXem ma ve tai muc Ve cua toi tren website.")
                logging.info("THANH CONG: %s", event.get("Title"))
                del state["pending"][key]
            elif time.time() - pending["time"] > 45 and not pending["warned"]:
                pending["warned"] = True
                notify.send("CAN KIEM TRA THU CONG: " + pending["title"] +
                            "\nChua xac minh duoc ve. Tam dung tu dang ky RIENG su kien nay.\n" + URL)
        if event.get("State") == "ENDED":
            continue
        if key not in old and state.get("initialized"):
            notify.send("SU KIEN MOI\n" + describe(event))
        elif available and not old.get(key, {}).get("available", False):
            notify.send("CO THE DANG KY / CO CHO TRO LAI\n" + describe(event))
    # Retain absent IDs to avoid calling a temporarily missing event 'new' again.
    for key in old.keys() - current.keys():
        old[key]["available"] = False
    old.update(current)
    state["initialized"] = True
    write_json(STATE, state)


def run(config):
    from playwright.sync_api import sync_playwright
    interval = max(0.5, float(config.get("interval_seconds", 0.5)))
    state = read_json(STATE, {"events": {}, "pending": {}, "cooldown": {}, "initialized": False})
    notify = Notifier(config)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(PROFILE), headless=False, viewport={"width": 1360, "height": 850})
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(10000)
        try:
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                logging.warning("Trang chua tai xong. Kiem tra mang/trinh duyet.")
            print("\nNeu can, dang nhap HUST trong cua so vua mo va vao /dat-ve.")
            print("Bot se TU DANG KY MOI su kien du dieu kien; giu nguyen ve hien co.")
            input("Khi thay danh sach su kien, quay lai day nhan Enter de BAT DAU: ")
            notify.send(f"BOT DA BAT DAU. Chu ky {interval:g}s; tu dang ky = {config.get('auto_register', True)}.\n{URL}")
            failures = 0
            heartbeat = time.monotonic()
            status_at = 0
            while not page.is_closed():
                cycle_started = time.monotonic()
                delay = interval
                backoff = False
                try:
                    # Also catches a login page left open from a previous cycle.
                    if recover_login(page, notify):
                        failures = 0
                    close_event_dialogs(page)
                    open_tab = page.locator("button.ev-tab").filter(has_text="Sự kiện sắp tới")
                    if "is-active" not in (open_tab.get_attribute("class") or "").split():
                        open_tab.click()
                    events = refresh(page)
                    reconcile(events, state, notify)
                    if failures:
                        notify.send("DA KET NOI LAI HUST. Bot tiep tuc kiem tra.")
                    failures = 0
                    now = time.time()
                    pending_titles = {
                        pending["title"] for pending in state["pending"].values()
                    }
                    candidates = [e for e in events if eligible(e)
                                  and str(e["Id"]) not in state["pending"]
                                  and " ".join(str(e.get("Title", "")).split()) not in pending_titles
                                  and state["cooldown"].get(str(e["Id"]), 0) <= now]
                    candidates.sort(key=lambda e: (e.get("StartTime") or "9999", str(e["Id"])))
                    if config.get("auto_register", True) and candidates:
                        # One registration per fresh snapshot; re-fetch before next event.
                        register(page, candidates[0], state, notify)
                    if time.monotonic() - status_at >= 30:
                        logging.info("Dang theo doi %s su kien; %s co the dang ky. Chu ky %ss.",
                                     len(events), len(candidates), interval)
                        status_at = time.monotonic()
                    if time.monotonic() - heartbeat >= 3600:
                        notify.send("BOT VAN HOAT DONG; vua tai danh sach HUST thanh cong.")
                        heartbeat = time.monotonic()
                except Exception as exc:
                    # The failed refresh may itself have made the expiry modal
                    # appear. Recover immediately instead of waiting for the
                    # normal exponential error backoff.
                    recovered = False
                    recovery_exc = None
                    # Do not immediately run the same recovery twice when the
                    # exception already came from an attempted login flow.
                    already_attempted_login = (
                        isinstance(exc, SiteError) and
                        "can dang nhap thu cong" in str(exc).lower()
                    )
                    if not already_attempted_login:
                        try:
                            recovered = recover_login(page, notify)
                        except Exception as login_exc:
                            recovery_exc = login_exc
                    if recovered:
                        failures = 0
                        backoff = False
                        delay = interval
                    else:
                        if recovery_exc is not None:
                            exc = recovery_exc
                        failures += 1
                        backoff = True
                        delay = max(interval, min(300, 5 * 2 ** min(failures, 6)),
                                    getattr(exc, "wait", 0))
                        reason = str(exc)[:700] if isinstance(exc, SiteError) else type(exc).__name__
                        logging.warning("Loi: %s. Cho %.0fs; kiem tra trinh duyet neu can dang nhap.",
                                        reason, delay)
                        if failures == 1 or failures % 10 == 0:
                            notify.send(
                                f"BOT GAP LOI: {reason}\nThu lai sau {delay:.0f}s. "
                                "Kiem tra trinh duyet/dang nhap."
                            )
                        # Only recover by navigation if there was no server-mandated wait.
                        if failures % 3 == 0 and not getattr(exc, "wait", 0):
                            try:
                                page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                            except Exception:
                                pass
                # Normal polling is start-to-start. Backoff delays begin after
                # an error so the server still receives the full rest period.
                if backoff:
                    sleep_for = delay
                else:
                    sleep_for = max(0.0, delay - (time.monotonic() - cycle_started))
                page.wait_for_timeout(sleep_for * 1000)
        finally:
            notify.send("BOT DA DUNG. Khong con tu dong theo doi/lay ve cho den khi chay lai.")
            # Give the background sender a brief chance; unsent notifications stay on disk.
            time.sleep(1)
            notify.stop.set()
            context.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(), RotatingFileHandler(
                            ROOT / "bot.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")])
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Ket noi Telegram")
    args = parser.parse_args()
    # An OS lock prevents two copies using the same profile/state at the same time.
    lock = (ROOT / "bot.lock").open("a+b")
    lock.seek(0)
    lock.write(b"1")
    lock.flush()
    lock.seek(0)
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise RuntimeError("Bot da chay o cua so khac. Chi chay MOT ban.") from None
    try:
        if args.setup:
            setup()
        elif not CONFIG.exists():
            print("Chay lenh nay truoc: .venv\\Scripts\\python.exe hust_bot.py --setup")
        else:
            run(read_json(CONFIG, {}))
    finally:
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDa dung bot.")
    except Exception as exc:
        # Don't print arbitrary exception traces, which may contain sensitive URLs.
        if type(exc) is RuntimeError:
            print("LOI:", str(exc))
        else:
            print("LOI:", type(exc).__name__)
            print("Dong cua so Playwright cu, kiem tra mang va thu lai. Khong mo hai bot cung luc.")
        sys.exit(1)
