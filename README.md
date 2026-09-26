# HUST Ticket Monitor

A personal Playwright-based bot that monitors the [HUST Student Affairs ticket page](https://ctsv.hust.edu.vn/dat-ve), sends Telegram notifications, and can optionally register for available events through the website's normal user interface.

> [!WARNING]
> This is an unofficial personal project and is not affiliated with Hanoi University of Science and Technology. Use it responsibly, follow HUST's rules and the website's terms, avoid aggressive polling, and never run multiple instances with the same browser profile.

## Features

- Opens Chromium with a dedicated persistent profile.
- Refreshes the event list through the website's **Refresh** button.
- Sends Telegram alerts for newly listed events and seats that become available again.
- Can optionally register for an eligible event by:
  1. Clicking **Register**.
  2. Clicking the red confirmation button in the dialog.
  3. Refreshing the page and verifying the ticket under **My tickets**.
- Does not cancel or replace an existing ticket.
- Attempts to recover an expired Office 365 session using credentials already stored by Chromium Autofill.
- Stores pending Telegram messages locally during temporary network failures.
- Uses increasing retry delays when the website fails or rate-limits requests.
- Uses a process lock to prevent two bot instances from sharing one browser profile.

## Requirements

- Windows 10 or Windows 11.
- Python 3.12 or newer.
- A HUST account with access to the ticket page.
- A Telegram bot created through [@BotFather](https://t.me/BotFather).
- A computer that remains powered on, connected to the internet, and awake while the bot is running.

## Installation on Windows

Open **Command Prompt** and run:

```bat
cd /d "%USERPROFILE%"
git clone https://github.com/ghuy4g/hust-ticket-alert.git hust-ticket-bot
cd /d "%USERPROFILE%\hust-ticket-bot"

py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

If `py -3.12` is unavailable, install Python 3.12 from the official Python website, enable **Add Python to PATH**, and reopen Command Prompt.

## Telegram setup

### 1. Create a Telegram bot

1. Open Telegram and find `@BotFather`.
2. Send `/newbot`.
3. Choose a display name.
4. Choose a username ending in `bot`.
5. BotFather will provide a token. Never share or commit this token.

### 2. Connect the bot to your private chat

From the project directory, run:

```bat
.venv\Scripts\python.exe hust_bot.py --setup
```

Then:

1. Paste the BotFather token into Command Prompt and press Enter. The token is not displayed.
2. Open the Telegram bot and press **Start**.
3. Send the exact `HUST-XXXXXXXX` pairing code shown by the program.
4. Return to Command Prompt and press Enter.
5. Wait for the Telegram confirmation message.

The program creates a local `config.json`. It contains the Telegram token and chat ID and must never be committed.

## First HUST login

Run:

```bat
.venv\Scripts\python.exe hust_bot.py
```

A dedicated Chromium window will open:

1. Sign in to HUST/Office 365 in that window.
2. If Chromium offers to save the account or password, allow it. The data remains inside the local `browser-profile` directory and is not read directly by the source code.
3. Open `https://ctsv.hust.edu.vn/dat-ve`.
4. Wait until the event list and the **Refresh** button appear.
5. Return to Command Prompt and press Enter to start monitoring.

Do not close the Chromium window while the bot is running.

## Running the bot later

```bat
cd /d "%USERPROFILE%\hust-ticket-bot"
.venv\Scripts\python.exe hust_bot.py
```

When the event list is visible, return to Command Prompt and press Enter.

To stop the bot, select Command Prompt and press `Ctrl + C`.

## Configuration

After `--setup`, `config.json` has this structure:

```json
{
  "telegram_token": "SECRET_DO_NOT_COMMIT",
  "telegram_chat_id": 123456789,
  "interval_seconds": 0.5,
  "auto_register": true
}
```

- `interval_seconds` controls the polling interval. The program does not allow values below `0.5` seconds. Values between `2` and `5` seconds place less load on the server.
- `auto_register: true` enables registration and confirmation.
- `auto_register: false` only monitors availability and sends Telegram alerts.

Stop the bot before editing `config.json`, save the file, and restart it.

## Session recovery

When the website reports an expired Office 365 session, the bot attempts to:

1. Click **Sign in again** or **Sign in with Office 365**.
2. Wait for Chromium to autofill the account and click **Next**.
3. Wait for Chromium to autofill the password and click **Sign in**.
4. Return to `/dat-ve` and resume monitoring.

The bot does not store a password in its source code, configuration, logs, or Telegram messages. CAPTCHA, MFA, or failed Autofill must be handled manually in the bot's browser window.

## Registration rules

An event is considered eligible only when:

- Its API status is `OPEN`.
- The account does not already have its ticket.
- The website does not block it because of an event conflict.
- At least one seat remains, or the event has unlimited capacity.

If multiple events are eligible, the bot prioritizes the earliest event. It attempts only one registration per refresh and reloads the state before trying another event.

## Telegram messages

Important messages include:

- `BOT DA BAT DAU`: monitoring started.
- `SU KIEN MOI`: a new event appeared.
- `CO THE DANG KY / CO CHO TRO LAI`: registration is open or a seat became available again.
- `DA XAC MINH CO VE`: the website confirms that the account owns the ticket.
- `CAN KIEM TRA THU CONG`: the result could not be verified with confidence.
- `PHIEN HUST DA HET HAN`: the bot detected an expired session and is attempting recovery.
- `BOT GAP LOI`: a network, website, interface, or login error occurred.
- `BOT VAN HOAT DONG`: hourly heartbeat.
- `BOT DA DUNG`: the process stopped.

## Local files

| File or directory | Purpose | Commit to GitHub? |
|---|---|---|
| `hust_bot.py` | Main source code | Yes |
| `README.md` | Documentation | Yes |
| `requirements.txt` | Python dependencies | Yes |
| `.gitignore` | Excluded private/local files | Yes |
| `config.json` | Telegram token and chat ID | **No** |
| `browser-profile/` | Cookies, login session, and browser data | **No** |
| `state.json` | Event and pending-registration state | **No** |
| `telegram-outbox.json` | Pending notifications | **No** |
| `bot.log*` | Runtime logs | **No** |
| `bot.lock` | Process lock | **No** |
| `.venv/` | Local Python environment | **No** |

## Troubleshooting

### Another bot instance is already running

Only one instance may run at a time. Stop the old Command Prompt process with `Ctrl + C`. If it closed unexpectedly, make sure no old Python or bot Chromium process remains before restarting.

### `TargetClosedError`

The bot's Chromium window or browser profile was closed. Stop any old process and restart the bot. Do not run two instances simultaneously.

### Automatic login recovery fails

- Confirm that the account and password were saved in the bot's dedicated Chromium profile.
- Confirm that Autofill works on both the account and password pages.
- Complete CAPTCHA or MFA manually.
- Once `/dat-ve` is open again, the bot resumes on a later cycle.

### HTTP `429`

The website is rate-limiting requests. The bot waits according to the response and applies a minimum delay. Do not open another instance, and increase `interval_seconds`.

### Telegram receives no messages

- Check the internet connection.
- Open the Telegram bot and press **Start**.
- Confirm that BotFather has not revoked the token.
- Run `hust_bot.py --setup` again if the private chat must be paired again.

### The HUST interface changes

The automation depends on the current website controls and API structure. If button labels or the page structure change, the bot may stop uncertain actions and report an error to avoid repeated incorrect registration attempts.

## Security

- Never commit `config.json` or `browser-profile/`.
- Never publish screenshots containing tokens, ticket codes, email addresses, student IDs, or cookies.
- Never share the Telegram token.
- If a token is exposed, immediately use `/revoke` in BotFather, generate a replacement, and rerun `--setup`.
- Before every push, inspect tracked files with `git status` and `git ls-files`.

## Limitations

- The computer must remain powered on and connected to the internet.
- Automatic login recovery depends on Chromium Autofill in the local profile.
- CAPTCHA, MFA, outages, and website changes may require manual intervention.
- Ticket acquisition still depends on network latency, server response, and competing users; success is not guaranteed.
- Faster polling does not grant priority and may trigger rate limits.

## Updating

If the local directory has no uncommitted source changes:

```bat
cd /d "%USERPROFILE%\hust-ticket-bot"
git pull
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Local configuration, browser session, and state files remain untouched because Git does not track them.

## License

No open-source license is currently included. The author retains all rights by default. Add a license such as MIT if you want to allow others to use, modify, and redistribute the code.
