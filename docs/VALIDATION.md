# Kiểm tra phiên bản 0.4.0

Đã kiểm tra trên Windows 11 x64, Python 3.12. Không dùng các kết quả dưới đây để suy ra mọi loại webcam hoặc phần mềm gọi video đều tương thích.

## Kiểm thử tự động

- 71 bài kiểm thử đạt; Ruff đạt.
- Các kiểm tra bao gồm hình học cử chỉ, giữ/nhả tay và cooldown; renderer ẩn hoàn toàn; âm thanh; thay đổi thiết lập giao diện; IPC hai tiến trình; khởi động cùng Windows; giải phóng tài nguyên.
- Tự chụp nền được kiểm bằng chuỗi ảnh có dao động sáng, nhiễu, vật chuyển động và người quay lại trong lúc chụp. Mask được kiểm soát trong các bài thử thuật toán; đây không phải nghiệm thu người rời phòng dưới ánh sáng thật.
- Camera dùng chung không tự fallback sang camera chiếm riêng. Native session được mở và đóng trên cùng luồng sở hữu COM.
- Khi ứng dụng khác đổi định dạng camera, kích thước hình xuất giữ ổn định. Nếu đang ẩn, frame xuất vẫn chỉ có ảnh nền, không lộ hình trực tiếp.

## Kiểm tra thiết bị thật

| Phép thử | Kết quả |
| --- | --- |
| Camera dùng chung → Media Foundation, hai tiến trình | Cả hai nhận hình không đen đồng thời |
| Media Foundation → camera dùng chung, hai tiến trình | Cả hai nhận hình không đen đồng thời |
| Camera dùng chung → DirectShow, hai tiến trình | Cả hai nhận hình không đen đồng thời |
| DirectShow → camera dùng chung, hai tiến trình | Cả hai nhận hình không đen đồng thời |
| Pipeline AI → OBS trong khi client thứ hai đọc webcam | 152 frame gửi OBS; client thứ hai nhận 103 frame, không lỗi |
| Pipeline webcam → AI → OBS trong 4 giây | 117 frame, median 30,16 FPS; mở lại camera sau khi dừng thành công |
| Runtime đóng gói → AI → OBS trong 3 giây | 74 frame, không lỗi; mở lại camera sau dừng thành công |
| Bộ cài và EXE đã cài | Mở giao diện thành công, mã kiểm tra EXE khớp payload |

Bốn phép thử camera dùng hai tiến trình Windows/OpenCV trên cùng webcam, mỗi bên nhận 60–62 frame không đen trong khoảng 2 giây giao nhau. Đây không phải thao tác nghiệm thu trực tiếp trong Zoom hoặc Meet. Trong phép thử pipeline đồng thời, hình xuất giữ 1280×720 trong khi client thứ hai dùng 640×480.

Các probe không lưu ảnh hoặc video. Log, đường dẫn cài cá nhân và báo cáo máy cục bộ không đưa vào repo.

## Phạm vi chưa nghiệm thu

- Chất lượng cử chỉ và nền khi một người thực hiện toàn bộ thao tác trước webcam có người quan sát.
- Hình và âm thanh ở phía nhận cuộc gọi Meet/Zoom/Discord.
- Chạy liên tục 20 phút, mọi webcam, mọi driver, 1080p và rút cáp giữa phiên.

Khả năng chia sẻ camera phụ thuộc Windows và driver. Thành phần dùng chung đặt `MF_DEVSOURCE_ATTRIBUTE_FRAMESERVER_SHARE_MODE=1` tại lúc tạo media source; xem [tài liệu Microsoft](https://learn.microsoft.com/en-us/windows/win32/medfound/mf-devsource-attribute-frameserver-share-mode).

## Chạy lại

```powershell
.\scripts\build-native.ps1
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check animecam tests tools scripts main.py launcher.py
.\.venv\Scripts\python.exe tools/live_smoke.py --camera 0 --virtual --seconds 4
.\.venv\Scripts\python.exe tools/verify_camera_sharing.py
.\.venv\Scripts\python.exe tools/verify_pipeline_sharing.py
```

Không chạy các probe camera đồng thời với nhau.
