# Teleportation Cam

Ứng dụng webcam cho Windows: đưa hai ngón tay lên trán để biến mất, làm lại để xuất hiện cùng vệt sáng và âm thanh ngắn. Video được xử lý ngay trên máy bằng MediaPipe và OpenCV.

Ứng dụng hiện hiển thị tên **AnimeCam FX** trong Windows. Repo và trang phát hành dùng tên **Teleportation Cam**.

## Tải và cài đặt

Tải bộ cài Windows x64 tại [GitHub Releases](https://github.com/quyen2867/Teleportation-Cam/releases/latest). Không cần cài Python.

1. Cài ứng dụng, mở icon **AnimeCam FX**.
2. Bấm **Bật camera**, rời khung hình và giữ camera cố định để tự chụp nền.
3. Quay lại, đưa hai ngón tay lên trán và giữ khoảng 0,5 giây. Hạ tay trước khi làm lại.
4. Để dùng hiệu ứng trong cuộc gọi, cài [OBS Studio](https://obsproject.com/), bật **camera ảo** trong AnimeCam rồi chọn **OBS Virtual Camera** trong ứng dụng gọi video.

| Phím | Thao tác |
| --- | --- |
| F9 | Biến mất / xuất hiện có hiệu ứng |
| F10 | Ẩn ngay bằng ảnh nền đã chụp |
| F8 | Hiện ngay, bỏ qua hiệu ứng và âm thanh |
| Ctrl+B | Chụp nền thủ công sau 3 giây |

Khi ẩn hoàn toàn, cả khung hình là ảnh nền đã lưu nên cảnh phòng đứng yên. Âm thanh hiệu ứng phát trên máy; camera ảo chỉ truyền hình. Muốn người trong cuộc gọi nghe tiếng hiệu ứng, cần chia sẻ âm thanh máy hoặc dùng thiết bị âm thanh ảo.

## Camera và tự chụp nền

Mặc định **Camera → Chế độ → Dùng chung (Windows)**: ứng dụng đọc qua Windows Frame Server, không điều khiển lại thông số phần cứng. Ứng dụng khác vẫn có thể đọc camera thật nếu driver hỗ trợ. Camera thật chỉ cho hình gốc; hiệu ứng được gửi qua camera ảo.

Chế độ dùng chung giữ độ phân giải và tốc độ hình Windows đang dùng. Nếu camera không hỗ trợ, chọn **Tương thích**; chế độ này có thể chiếm riêng webcam. Bấm **Tắt camera** để nhả webcam. Ứng dụng không tự chuyển sang chế độ chiếm riêng khi dùng chung thất bại.

Tự chụp nền chờ cảnh không có người ổn định khoảng 2 giây, chịu được dao động sáng nhẹ và nhiễu cảm biến. Sau khi đã chụp, nền không tự bị ghi đè. Bấm **Chờ chụp nền mới** khi muốn chụp lại. Camera chuyển động, hình quá tối/sáng hoặc thay đổi ánh sáng lớn vẫn cần đợi ổn định.

## Chạy từ mã nguồn

Cần Windows 10/11 x64, Python 3.12 và Visual Studio C++ x64 Build Tools kèm Windows SDK. Công cụ C++ chỉ cần trên máy phát triển để build thành phần camera dùng chung.

```powershell
.\scripts\setup.ps1
.\scripts\build-native.ps1
.\scripts\run.ps1
```

Nếu không dùng Python Launcher, truyền đường dẫn Python vào bước thiết lập:

```powershell
.\scripts\setup.ps1 -Python 'C:\duong-dan\python.exe'
```

Bước thiết lập tải mô hình từ Google MediaPipe, kiểm tra SHA-256 trong `models/checksums.json`. Khi chạy webcam, ứng dụng không tải thêm mô hình và không gửi hình lên mạng.

## Kiểm thử và đóng gói

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check animecam tests tools scripts main.py launcher.py
.\scripts\build-installer.ps1
```

Bộ cài được tạo trong `dist/`. Payload chỉ gồm EXE và thư viện, mô hình, tài nguyên cần thiết; không kèm môi trường phát triển, script chạy hay tài liệu hướng dẫn. Bản phát hành trên GitHub dùng tên `TeleportationCam-Setup-0.4.0.exe`; đó là cùng bộ cài được script tạo dưới tên `AnimeCamFX-Setup-0.4.0.exe`.

Các probe sau mở thiết bị thật, chỉ ghi thông số và không lưu ảnh/video. Chạy từng lệnh riêng để tránh tranh webcam:

```powershell
.\.venv\Scripts\python.exe tools/live_smoke.py --camera 0 --virtual --seconds 4
.\.venv\Scripts\python.exe tools/verify_camera_sharing.py
.\.venv\Scripts\python.exe tools/verify_pipeline_sharing.py
```

Kết quả và giới hạn kiểm tra: [docs/VALIDATION.md](docs/VALIDATION.md). Các thay đổi theo phiên bản: [CHANGELOG.md](CHANGELOG.md).

## Các phần chính

| Thư mục / tệp | Công dụng |
| --- | --- |
| `animecam/` | Pipeline webcam, nhận cử chỉ, nền, hiệu ứng, âm thanh và giao diện |
| `native/shared_camera.cpp` | Camera dùng chung qua Windows Media Foundation |
| `assets/` | Icon, biểu tượng điều khiển, âm thanh và thông tin nguồn |
| `models/checksums.json` | Mã kiểm tra các mô hình tải về |
| `tests/` | Kiểm thử thuật toán, pipeline, giao diện và vòng đời camera |
| `tools/` | Chẩn đoán thiết bị thật và benchmark cho phát triển |
| `scripts/` | Thiết lập môi trường, chạy ứng dụng và đóng gói |
| `installer/` | Cấu hình PyInstaller và bộ cài NSIS |

Mã nguồn và thư viện phụ thuộc giữ điều khoản riêng; xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Âm thanh mặc định có thông tin nguồn tại `assets/sound-source.json`; có thể chọn tệp khác trong ứng dụng.
