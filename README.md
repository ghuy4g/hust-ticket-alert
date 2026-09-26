# HUST Ticket Monitor

Bot cá nhân dùng Playwright để theo dõi trang [Đặt vé CTSV HUST](https://ctsv.hust.edu.vn/dat-ve), gửi thông báo qua Telegram và, nếu được bật, tự đăng ký sự kiện còn chỗ bằng đúng luồng thao tác trên giao diện website.

> Đây là dự án cá nhân, không phải sản phẩm chính thức của Đại học Bách khoa Hà Nội. Hãy sử dụng có trách nhiệm, tuân thủ quy định của HUST và không chạy nhiều bản bot cùng lúc.

## Tính năng

- Mở Chromium bằng một hồ sơ riêng và giữ phiên đăng nhập giữa các lần chạy.
- Làm mới danh sách bằng nút **Làm mới** của website.
- Gửi Telegram khi có sự kiện mới hoặc một sự kiện có chỗ trở lại.
- Có thể tự đăng ký sự kiện đủ điều kiện:
  1. Bấm **Đăng ký**.
  2. Bấm **Xác nhận đăng ký** trong hộp thoại màu đỏ.
  3. Làm mới và kiểm tra `Vé của tôi` trước khi báo thành công.
- Không hủy hoặc thay thế vé đang có.
- Tự thử đăng nhập lại khi phiên Office 365 hết hạn bằng thông tin mà Chromium đã lưu và tự điền.
- Giữ hàng đợi Telegram trên ổ đĩa khi mạng tạm thời lỗi.
- Tự tăng thời gian chờ khi website lỗi hoặc giới hạn truy cập.
- Khóa tiến trình để tránh hai bản bot dùng chung một hồ sơ trình duyệt.

## Yêu cầu

- Windows 10 hoặc Windows 11.
- Python 3.12 trở lên.
- Tài khoản HUST có quyền truy cập trang đặt vé.
- Một Telegram bot được tạo bằng [@BotFather](https://t.me/BotFather).
- Máy phải đang bật, có mạng và không ở chế độ Sleep trong lúc bot hoạt động.

## Cài đặt trên Windows

Mở **Command Prompt** rồi chạy lần lượt:

```bat
cd /d "%USERPROFILE%"
git clone https://github.com/YOUR_GITHUB_USERNAME/hust-ticket-monitor.git hust-ticket-bot
cd /d "%USERPROFILE%\hust-ticket-bot"

py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Nếu lệnh `py -3.12` không tồn tại, hãy cài Python 3.12 từ trang chính thức, chọn **Add Python to PATH**, rồi mở lại Command Prompt.

## Tạo và kết nối Telegram bot

### 1. Tạo bot

1. Mở Telegram và tìm `@BotFather`.
2. Gửi lệnh `/newbot`.
3. Nhập tên hiển thị cho bot.
4. Nhập username kết thúc bằng `bot`.
5. BotFather sẽ gửi một token. Không chia sẻ token này và không đưa nó lên GitHub.

### 2. Kết nối bot với cuộc trò chuyện riêng

Trong thư mục dự án, chạy:

```bat
.venv\Scripts\python.exe hust_bot.py --setup
```

Sau đó:

1. Dán token BotFather vào Command Prompt rồi nhấn Enter. Token sẽ không hiện trên màn hình.
2. Mở đúng bot Telegram vừa tạo và bấm **Start**.
3. Gửi chính xác mã dạng `HUST-XXXXXXXX` mà chương trình hiển thị.
4. Quay lại Command Prompt và nhấn Enter.
5. Khi Telegram báo kết nối thành công, cấu hình đã hoàn tất.

Chương trình tạo `config.json` trên máy. File này chứa token Telegram và chat ID nên đã được `.gitignore` chặn khỏi GitHub.

## Thiết lập đăng nhập HUST lần đầu

Chạy:

```bat
.venv\Scripts\python.exe hust_bot.py
```

Một cửa sổ Chromium riêng sẽ mở ra:

1. Đăng nhập HUST/Office 365 trong cửa sổ đó.
2. Nếu Chromium hỏi lưu tài khoản hoặc mật khẩu, chọn lưu. Dữ liệu này nằm trong thư mục cục bộ `browser-profile` và không được mã nguồn đọc trực tiếp.
3. Đi tới `https://ctsv.hust.edu.vn/dat-ve`.
4. Chờ đến khi nhìn thấy danh sách sự kiện và nút **Làm mới**.
5. Quay lại Command Prompt và nhấn Enter để bot bắt đầu theo dõi.

Không đóng cửa sổ Chromium do bot mở trong lúc bot đang chạy.

## Chạy bot những lần sau

```bat
cd /d "%USERPROFILE%\hust-ticket-bot"
.venv\Scripts\python.exe hust_bot.py
```

Khi danh sách sự kiện đã hiện, quay lại Command Prompt và nhấn Enter.

Để dừng bot, chọn cửa sổ Command Prompt và nhấn `Ctrl + C`. Telegram sẽ báo bot đã dừng.

## Cấu hình

Sau khi chạy `--setup`, `config.json` có cấu trúc:

```json
{
  "telegram_token": "SECRET_DO_NOT_COMMIT",
  "telegram_chat_id": 123456789,
  "interval_seconds": 0.5,
  "auto_register": true
}
```

- `interval_seconds`: chu kỳ kiểm tra. Chương trình không cho nhỏ hơn `0.5` giây. Kiểm tra quá nhanh có thể khiến website giới hạn truy cập; giá trị `2` đến `5` giây nhẹ hơn cho máy chủ.
- `auto_register: true`: tự bấm đăng ký và xác nhận.
- `auto_register: false`: chỉ theo dõi và gửi thông báo Telegram, không đăng ký.

Hãy dừng bot trước khi sửa `config.json`, lưu file, rồi chạy lại.

## Tự khôi phục phiên đăng nhập

Khi website hiện **Phiên Office 365 đã hết hạn** hoặc **Cần đăng nhập Office 365**, bot sẽ thử:

1. Bấm **Đăng nhập lại** hoặc **Đăng nhập Office 365**.
2. Chờ Chromium tự điền tài khoản và bấm **Next**.
3. Chờ Chromium tự điền mật khẩu và bấm **Sign in**.
4. Quay lại `/dat-ve` và tiếp tục theo dõi.

Bot không lưu mật khẩu trong mã nguồn, `config.json`, log hoặc Telegram. Nếu Chromium không tự điền, hoặc trang yêu cầu CAPTCHA/MFA, bạn phải xử lý thủ công trong cửa sổ bot.

## Cách bot quyết định đăng ký

Một sự kiện chỉ được coi là có thể đăng ký khi:

- Trạng thái API là `OPEN`.
- Tài khoản chưa có vé của sự kiện đó.
- Sự kiện không bị khóa bởi điều kiện xung đột của website.
- Số chỗ còn lại lớn hơn `0`, hoặc website đánh dấu sức chứa không giới hạn.

Nếu có nhiều sự kiện phù hợp, bot ưu tiên sự kiện bắt đầu sớm hơn. Mỗi lần làm mới bot chỉ thử một sự kiện rồi tải lại trạng thái trước khi thử sự kiện tiếp theo.

## Thông báo Telegram

Bot có thể gửi các thông báo chính:

- `BOT DA BAT DAU`: bot đã bắt đầu theo dõi.
- `SU KIEN MOI`: website xuất hiện sự kiện mới.
- `CO THE DANG KY / CO CHO TRO LAI`: một sự kiện đã mở hoặc vừa có chỗ lại.
- `DA XAC MINH CO VE`: website xác nhận tài khoản đã có vé.
- `CAN KIEM TRA THU CONG`: chưa xác minh chắc chắn kết quả đăng ký.
- `PHIEN HUST DA HET HAN`: bot đang thử đăng nhập lại.
- `BOT GAP LOI`: lỗi mạng, website, giao diện hoặc đăng nhập.
- `BOT VAN HOAT DONG`: heartbeat mỗi giờ.
- `BOT DA DUNG`: tiến trình đã dừng.

## File được tạo khi chạy

| File/thư mục | Nội dung | Được đưa lên GitHub? |
|---|---|---|
| `hust_bot.py` | Mã nguồn chính | Có |
| `README.md` | Tài liệu hướng dẫn | Có |
| `requirements.txt` | Thư viện Python | Có |
| `.gitignore` | Danh sách file riêng tư cần chặn | Có |
| `config.json` | Token Telegram và chat ID | **Không** |
| `browser-profile/` | Cookie, phiên đăng nhập và dữ liệu trình duyệt | **Không** |
| `state.json` | Trạng thái sự kiện và lần đăng ký đang chờ | **Không** |
| `telegram-outbox.json` | Hàng đợi thông báo | **Không** |
| `bot.log*` | Nhật ký hoạt động | **Không** |
| `bot.lock` | Khóa tiến trình | **Không** |
| `.venv/` | Môi trường Python cục bộ | **Không** |

## Xử lý lỗi thường gặp

### `Bot da chay o cua so khac`

Chỉ được chạy một bản bot. Dừng cửa sổ cũ bằng `Ctrl + C`. Nếu cửa sổ đã đóng bất thường, bảo đảm không còn tiến trình Python/Chromium của bot rồi chạy lại.

### `TargetClosedError`

Cửa sổ hoặc hồ sơ Chromium đã bị đóng trong khi bot hoạt động. Đóng tiến trình cũ và chạy lại bot; không chạy hai bản cùng lúc.

### Bot không tự đăng nhập lại

- Kiểm tra tài khoản và mật khẩu đã được lưu trong đúng cửa sổ Chromium của bot.
- Tự điền phải hoạt động ở cả trang tài khoản và trang mật khẩu.
- Nếu có CAPTCHA hoặc MFA, đăng nhập thủ công.
- Sau khi vào lại `/dat-ve`, bot sẽ tiếp tục ở chu kỳ sau.

### Website trả lỗi `429`

Website đang giới hạn tần suất truy cập. Bot tự chờ ít nhất 60 giây theo phản hồi của máy chủ. Không mở thêm bản bot; nên tăng `interval_seconds`.

### Telegram không nhận tin

- Kiểm tra máy còn mạng.
- Mở bot Telegram và bấm **Start**.
- Kiểm tra token chưa bị BotFather thu hồi.
- Chạy lại `hust_bot.py --setup` nếu cần kết nối lại.

### Giao diện HUST thay đổi

Bot phụ thuộc vào nút và hộp thoại hiện tại của website. Nếu tên nút hoặc cấu trúc API thay đổi, bot sẽ dừng thao tác không chắc chắn và gửi/cung cấp lỗi để tránh đăng ký nhầm liên tiếp.

## Bảo mật

- Không commit `config.json` hoặc `browser-profile/`.
- Không đăng ảnh chụp chứa token, mã vé, email, MSSV hoặc cookie.
- Không gửi token Telegram cho người khác.
- Nếu token từng xuất hiện công khai, dùng `/revoke` trong BotFather ngay lập tức, tạo token mới và chạy lại `--setup`.
- Trước mỗi lần push, chạy `git status` và `git ls-files` để kiểm tra danh sách file.

## Giới hạn

- Bot phải chạy trên máy đang bật và có mạng.
- Tự đăng nhập phụ thuộc vào autofill của hồ sơ Chromium cục bộ.
- CAPTCHA, MFA, website ngừng hoạt động hoặc giao diện thay đổi có thể cần xử lý thủ công.
- Vé vẫn phụ thuộc vào tốc độ mạng, phản hồi máy chủ và số người đăng ký cùng lúc; bot không bảo đảm lấy được vé.
- Tần suất kiểm tra thấp không đồng nghĩa với quyền ưu tiên, và tần suất quá cao có thể bị giới hạn.

## Cập nhật mã nguồn

Nếu thư mục không có thay đổi riêng:

```bat
cd /d "%USERPROFILE%\hust-ticket-bot"
git pull
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Các file cấu hình, phiên đăng nhập và trạng thái cục bộ vẫn được giữ nguyên vì không nằm trong Git.

## Giấy phép

Dự án hiện chưa kèm giấy phép mã nguồn mở. Mặc định tác giả giữ toàn bộ quyền đối với mã nguồn. Nếu muốn cho phép người khác sử dụng, sửa đổi và phân phối, hãy bổ sung một giấy phép phù hợp như MIT.
