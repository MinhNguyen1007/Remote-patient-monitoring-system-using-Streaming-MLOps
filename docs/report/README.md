# Thư mục viết báo cáo (Giai đoạn I)

## Tệp trong thư mục

| Tệp | Vai trò |
|---|---|
| [`ghi_chu_bao_cao.md`](ghi_chu_bao_cao.md) | **Nguồn số liệu duy nhất**: mọi kết quả, quyết định và 16 hạn chế bắt buộc công khai, sắp theo mục báo cáo. Đọc file này trước khi viết bất cứ mục nào |
| [`bao_cao_do_an.md`](bao_cao_do_an.md) | Khung báo cáo đồ án 5 chương + phần đầu/phần cuối, theo sườn `BaoCao_GiaoDichDinhLuong.md` |
| [`bai_bao.md`](bai_bao.md) | Khung bài báo 5 mục, theo sườn `Mau_Bai_bao_Project_NLP.md` |
| `BaoCao_GiaoDichDinhLuong.md`, `Mau_Bai_bao_Project_NLP.md` | Hai tệp mẫu của người dùng (chỉ để tham khảo sườn, **không sửa**) |
| [`build_docx.py`](build_docx.py) | Xuất `.docx` bằng Pandoc |
| `figures/` | 15 hình sơ đồ đã render sẵn thành PNG; `figures/src/` chứa nguồn Mermaid của hình không lấy từ `docs/design/` |

Ảnh khác được tham chiếu trực tiếp từ chỗ chúng đang nằm, không sao chép: 3 hình kết quả mô hình ở `ml/reports/`, 9 ảnh chụp giao diện ở `images/`.

## Xuất Word

```bash
python docs/report/build_docx.py             # cả hai tài liệu
python docs/report/build_docx.py bao_cao     # chỉ báo cáo
```

Cần Pandoc trên máy (đã kiểm tra với 3.9.0.2). Script tự kiểm tra mọi ảnh được tham chiếu có tồn tại trước khi gọi Pandoc — thiếu ảnh thì Pandoc chỉ cảnh báo rồi bỏ qua, tài liệu xuất ra sẽ khuyết hình mà không ai để ý.

Hai tệp `.docx` sinh ra **không** nằm trong git (xem `.gitignore`): chúng là kết quả build, tạo lại bằng một lệnh. Chỉ nguồn `.md` và hình được commit.

### Kiểu chữ theo mẫu của trường

Mặc định Pandoc dùng kiểu Word riêng của nó. Để ra đúng font/cỡ chữ/kiểu heading của trường:

```bash
pandoc -o docs/report/reference.docx --print-default-data-file reference.docx
```

Mở `reference.docx` trong Word, sửa các style (Normal, Heading 1–3, Caption, Table) theo quy định, lưu lại. Lần build sau script tự dùng nó.

## Render lại sơ đồ

14 hình trong `figures/` được trích tự động từ các khối ```mermaid trong `docs/design/02_*.md`; hình `kien_truc_he_thong.png` render từ `figures/src/kien_truc_he_thong.mmd`. Khi sơ đồ thiết kế thay đổi thì render lại:

```bash
npx -y @mermaid-js/mermaid-cli -i <file.mmd> -o docs/report/figures/<tên>.png -b white -s 2
```

Bố cục phải chọn theo tỉ lệ khung in: trang A4 dọc dùng được tỉ lệ khoảng 0,67. Sơ đồ kiến trúc dùng `flowchart TB` (tỉ lệ 0,70) thay vì `LR` (4,68) chính vì lý do này.

**Ba hình chưa lọt trang A4** và cần xử lý trước khi nộp:

| Hình | Tỉ lệ | Vấn đề |
|---|---|---|
| `activity_drift.png` | 0,35 | Cao gấp ~3 lần khung trang; đổi sang `LR` cũng không cứu được (tỉ lệ thành 7,65) |
| `activity_streaming.png` | 0,41 | Như trên |
| `usecase.png` | 0,50 | Hơi cao, còn xoay xở được |

Ba phương án: (a) tách mỗi sơ đồ hoạt động dài thành 2 hình theo giai đoạn — đồng thời làm `docs/design/` dễ đọc hơn; (b) để mỗi hình trên một trang ngang riêng; (c) để hình trải hai trang dọc. Phương án (a) tốt nhất cho bản in.

## Còn thiếu (cần người dùng cung cấp)

1. **Thông tin hành chính** cho phần đầu báo cáo — mọi chỗ đánh dấu `⟨…⟩`: tên môn học, mã lớp, học vị + họ tên giảng viên hướng dẫn và email, danh sách thành viên nhóm kèm MSSV (hoặc xác nhận làm một mình để bỏ mục "LÀM VIỆC NHÓM").
2. **Logo trường** (mẫu dùng một ảnh logo ở trang bìa) — chưa có trong repo.
3. **Tài liệu tham khảo**: mục 2 của bài báo và mục 2.2 của báo cáo cần tra cứu, trích dẫn tài liệu thật (NEWS2, MIMIC-III, PSI/drift, LSTM-AE). Danh sách nền ở `ghi_chu_bao_cao.md` mục 5 chưa đủ và chưa kiểm tra định dạng.

## Lưu ý khi viết

- **Giờ trong ghi chú là UTC.** Các mốc ở `ghi_chu_bao_cao.md` mục 3.4(d) (15:00, 15:06, 15:14) là giờ UTC; giao diện trong ảnh chụp hiển thị giờ địa phương UTC+7 (22:00, 22:06, 22:14). Phải thống nhất một hệ giờ giữa phần chữ và hình.
- Số thập phân dùng dấu phẩy, theo đúng hai tệp mẫu.
- Các hạn chế ở `ghi_chu_bao_cao.md` mục 3.5 là **bắt buộc** xuất hiện trong báo cáo, đặc biệt: tập kiểm tra đã dùng hai lần, và ngưỡng quality gate được hiệu chỉnh sau khi đã xem kết quả trên tập kiểm tra.
