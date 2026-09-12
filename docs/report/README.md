# Thư mục viết báo cáo (Giai đoạn I)

## Tệp trong thư mục

| Tệp | Vai trò |
|---|---|
| [`ghi_chu_bao_cao.md`](ghi_chu_bao_cao.md) | **Nguồn số liệu duy nhất**: mọi kết quả, quyết định và 16 hạn chế bắt buộc công khai, sắp theo mục báo cáo. Đọc file này trước khi viết bất cứ mục nào |
| [`bao_cao_do_an.md`](bao_cao_do_an.md) | Khung báo cáo đồ án 5 chương + phần đầu/phần cuối, theo sườn `BaoCao_GiaoDichDinhLuong.md` |
| [`bai_bao.md`](bai_bao.md) | Khung bài báo 5 mục, theo sườn `Mau_Bai_bao_Project_NLP.md` |
| `BaoCao_GiaoDichDinhLuong.md`, `Mau_Bai_bao_Project_NLP.md` | Hai tệp mẫu của người dùng (chỉ để tham khảo sườn, **không sửa**) |
| [`build_docx.py`](build_docx.py) | Xuất `.docx` bằng Pandoc (tuỳ chọn — bản giao hiện tại là Markdown) |
| [`tools/render_figures.py`](tools/render_figures.py) | Render sơ đồ Mermaid → PNG |
| [`tools/render_html_figures.py`](tools/render_html_figures.py) | Render 3 sơ đồ tổng quát viết bằng HTML/CSS → PNG |
| [`tools/fetch_logos.py`](tools/fetch_logos.py) | Tải logo công nghệ (SVG, CC0) về `figures/logos/` |
| [`tools/check_report.py`](tools/check_report.py) | Soát nhất quán hình/bảng/trích dẫn/ảnh; `--renumber` để đánh số lại |
| `figures/` | Hình đã render thành PNG; `figures/src/` chứa nguồn HTML/CSS của 3 sơ đồ tổng quát; `figures/logos/` chứa logo công nghệ |

Ảnh khác được tham chiếu trực tiếp từ chỗ chúng đang nằm, không sao chép: 3 hình kết quả mô hình ở `ml/reports/`, 9 ảnh chụp giao diện ở `images/`.

## Xuất Word (tuỳ chọn)

> Người dùng đã xác nhận **không cần** bản Word; bản giao là hai tệp Markdown ở trên. Phần này giữ lại vì script vẫn chạy được nếu về sau cần.


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

## Hai script bảo trì

```bash
python docs/report/tools/render_figures.py           # render lại toàn bộ 17 sơ đồ
python docs/report/tools/render_figures.py --list    # chỉ liệt kê nguồn từng hình
python docs/report/tools/check_report.py             # soát nhất quán (thoát mã 1 nếu có vấn đề)
python docs/report/tools/check_report.py --renumber   # đánh số lại Hình/Bảng + sinh lại 2 danh mục
```

**`render_figures.py`** trích các khối ```mermaid trong `docs/design/02_*.md` theo đúng thứ tự xuất hiện, cộng với các tệp `.mmd` trong `figures/src/` (sơ đồ chỉ dùng cho báo cáo). Tên tệp PNG lấy từ bảng `NAMES` trong script. **Thêm hoặc bớt một khối mermaid trong `docs/design` sẽ làm lệch chỉ số**; khi đó script báo lỗi rõ và phải cập nhật `NAMES`, chứ không âm thầm ghi sai tên tệp. Chạy lại script này mỗi khi sửa sơ đồ thiết kế.

**`check_report.py`** bắt năm lỗi mà viết tay rất dễ mắc:

1. số Hình/Bảng lệch thứ tự xuất hiện (chèn một hình vào giữa là lệch hết phía sau);
2. chú thích trong danh mục khác chú thích trong thân bài;
3. bảng chưa được đánh số;
4. trích dẫn `[n]` không có trong danh mục tài liệu tham khảo, hoặc ngược lại;
5. ảnh được tham chiếu nhưng không tồn tại trên đĩa.

Cả năm lỗi này đều **đã từng xảy ra** trong lần viết đầu (Hình 3.10 nằm giữa 3.6 và 3.7; 10 chú thích lệch danh mục; 4 bảng chưa đánh số; 3 tài liệu có trong danh mục mà chưa được trích dẫn), nên hãy chạy script sau mỗi lần sửa nội dung.

## Ba sơ đồ tổng quát vẽ bằng HTML/CSS

Khác với các sơ đồ UML sinh từ Mermaid, ba sơ đồ tổng quát được viết tay bằng HTML/CSS rồi render bằng
Chrome headless (`tools/render_html_figures.py`). Mỗi sơ đồ theo **một phong cách riêng**, bám theo ba
tệp mẫu người dùng đưa ở `images/Ve_So_Do/`:

| Sơ đồ | Phong cách (mẫu tương ứng) | CSS |
|---|---|---|
| `so_do_tong_quat.png` | Nhiều lớp, thanh tiêu đề màu đặc theo nhóm chức năng, thẻ có bullet, ô chú giải, dải hạ tầng và luồng đầu–cuối ở chân (`SoDoHeThongTongQuat.png`) | `style_layered.css` |
| `mo_hinh_train_serve_monitor.png` | Vẽ tay: font Segoe Print, panel pastel có gạch chéo, hộp bo góc không đều (`MoHinh_Trainiing_Serving_Monitoring.png`) | `style_sketch.css` |
| `vong_lap_mlops.png` | Lưu đồ đơn sắc: khung nét đứt có tiêu đề, hình thoi quyết định, logo đặt rời, chú thích serif dưới hình (`Mau_Mo_Hinh_Tong_Quat_He_Thong.png`) | `style_flow.css` |

Logo lấy từ [Simple Icons](https://simpleicons.org) — giấy phép **CC0**, mỗi logo là một path đơn sắc đã
mang màu thương hiệu chính thức, nên nét đồng đều giữa các hãng thay vì mỗi logo một phong cách.

Ba điều đã mắc phải khi làm, ghi lại để khỏi lặp:

- **Khai báo `.s` / `.sub` (nhãn phụ) phải ở phạm vi toàn cục, không bó trong một lớp hộp.** Bó trong
  `.box` hay `.bx` thì ở các loại hộp khác nhãn phụ mất `display:block` và chữ dính liền dòng trên. Lỗi
  này đã xảy ra ở hai style khác nhau.
- **Mũi tên dọc không được đi xuyên qua hộp kết cục của nhánh rẽ** — người đọc sẽ hiểu là luồng chính
  chạy qua nhánh. Dùng bố cục hai làn (`.gflow` trong `style_flow.css`): luồng chính ở cột 1, nhánh rẽ
  sang cột 2–3.
- **Kiểm lại chiều mũi tên bằng cách đọc thành câu.** Nhánh phải của MLflow Registry từng chỉ sai chiều,
  đọc thành “Monitoring → Registry” trong khi thực tế Monitoring *đọc* phân phối tham chiếu từ registry.

## Về việc hình có lọt trang in hay không

Tiêu chí đúng **không phải tỉ lệ khung hình** mà là **cỡ chữ sau khi thu hình cho vừa khung**. Một sơ đồ rộng 5.586 px ở cỡ chữ mặc định của Mermaid, khi thu về bề rộng 16 cm, cho chữ khoảng 2,3 pt — không đọc được, dù tỉ lệ khung hình của nó (1,22) trông rất "vừa trang".

Tính nhanh: `cỡ chữ (pt) ≈ 794 × bề_rộng_in(cm) / bề_rộng_ảnh(px)`, với ảnh render ở `-s 2`. Ngưỡng đọc được là khoảng 7 pt.

Theo tiêu chí này, các sơ đồ tuần tự và `dfd_level1` là những hình khó in nhất, không phải các sơ đồ hoạt động. Vì bản giao hiện tại là Markdown (đọc trên màn hình, phóng to được) nên đây **không phải vấn đề đang chặn**. Nếu về sau cần bản in, ba cách xử lý: đặt hình trên một trang ngang riêng, tách sơ đồ thành nhiều phần nhỏ hơn, hoặc giảm số nút trên mỗi sơ đồ.

Hai sơ đồ hoạt động dài (2.3.1 và 2.3.3) đã được tách thành hai phần a/b trong `docs/design/02_3_activity.md`, với điểm tách trùng ranh giới nghiệp vụ thật nên hai phần đọc độc lập được.

## Trạng thái nội dung

Cả hai tài liệu đã viết xong nội dung: báo cáo ~19.600 từ (5 chương, 27 hình, 21 bảng), bài báo ~7.350 từ (5 mục, 7 hình, 4 bảng). Mỗi tài liệu có 12 tài liệu tham khảo đã được tra cứu và xác minh; script `check_refs.py` trong lịch sử phiên đã kiểm tra mọi trích dẫn `[n]` trong thân bài đều có trong danh mục và ngược lại.

Hai chỗ còn đánh dấu `⟨…⟩` trong báo cáo **là ghi chú cố ý** cho người dùng khi mở file Word: chỗ cần thay danh sách hình/bảng thủ công bằng mục lục tự động của Word.

## Còn thiếu (cần người dùng cung cấp)

Theo yêu cầu "chưa biết thì không ghi", những thông tin dưới đây đã được **bỏ trống hẳn** thay vì để chỗ trống hay điền giả:

1. **Trang bìa**: tên môn học, mã lớp, học vị + họ tên giảng viên hướng dẫn. Hiện trang bìa chỉ có tên trường, khoa, tên đề tài, họ tên + MSSV người thực hiện, khoá và năm.
2. **Lời cảm ơn và trang cam đoan** viết "giảng viên hướng dẫn" chung, không nêu tên.
3. **Bài báo** chỉ có một tác giả và một email; nếu làm nhóm hoặc muốn ghi tên giảng viên hướng dẫn làm đồng tác giả (như tệp mẫu) thì cần bổ sung.
4. **Hai mục "LÀM VIỆC NHÓM" và "TỰ ĐÁNH GIÁ"** của mẫu đã được **bỏ khỏi** báo cáo vì không biết đồ án làm một mình hay theo nhóm. Nếu môn học yêu cầu thì thêm lại.
5. **Logo trường** ở trang bìa — mẫu có, repo chưa có ảnh này.
6. **Hai ảnh giao diện cần chụp lại** (cần đăng nhập, Claude không tự nhập mật khẩu được):
   - `images/3_patient_detail.png` — bản đang dùng ở báo cáo vẫn còn lỗi cũ: bệnh nhân ở giờ thứ 88, dải bất thường đầy đủ, nhưng thẻ "Diễn biến bất thường" ghi "Chưa đủ 16 giờ". Lỗi đã sửa trong code, chỉ thiếu ảnh mới.
   - `images/3_patient_detail_v2.png` — thực ra là ảnh **danh sách bệnh nhân** chụp lại sau khi sửa (đã hiện đúng "Thiếu dữ liệu cửa sổ"), bị đặt nhầm tên. Nên đổi tên thành `2_patient_list.png` để thay bản cũ (bản cũ vẫn ghi sai "Chưa đủ 16 giờ" ở nhiều thẻ).

## Lưu ý khi viết

- **Giờ trong ghi chú là UTC.** Các mốc ở `ghi_chu_bao_cao.md` mục 3.4(d) (15:00, 15:06, 15:14) là giờ UTC; giao diện trong ảnh chụp hiển thị giờ địa phương UTC+7 (22:00, 22:06, 22:14). Phải thống nhất một hệ giờ giữa phần chữ và hình.
- Số thập phân dùng dấu phẩy, theo đúng hai tệp mẫu.
- Các hạn chế ở `ghi_chu_bao_cao.md` mục 3.5 là **bắt buộc** xuất hiện trong báo cáo, đặc biệt: tập kiểm tra đã dùng hai lần, và ngưỡng quality gate được hiệu chỉnh sau khi đã xem kết quả trên tập kiểm tra.
