"""Xuất bao_cao_do_an.md và bai_bao.md sang .docx bằng Pandoc.

Chạy từ gốc repo:  python docs/report/build_docx.py            # xuất cả hai
                   python docs/report/build_docx.py bao_cao    # chỉ báo cáo
                   python docs/report/build_docx.py bai_bao    # chỉ bài báo

Ảnh được tham chiếu bằng đường dẫn tương đối từ docs/report (`figures/...`) hoặc từ gốc repo
(`../../images/...`, `../../ml/reports/...`); `--resource-path` gồm cả hai nên Pandoc tìm được hết.
Trước khi gọi Pandoc, script kiểm tra mọi ảnh được tham chiếu có tồn tại — thiếu ảnh thì Pandoc chỉ
cảnh báo rồi bỏ qua, tài liệu xuất ra sẽ thiếu hình mà không ai để ý.

Tuỳ chọn: đặt một file Word mẫu tên `reference.docx` cạnh script để Pandoc dùng đúng font, cỡ chữ,
kiểu heading của trường (tạo bằng: pandoc -o reference.docx --print-default-data-file reference.docx,
rồi sửa style trong Word).
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPORT_DIR.parents[1]
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")

# Pandoc bỏ lặng lẽ \newpage khi xuất docx (chỉ hiểu nó ở đầu ra LaTeX), nên tài liệu sẽ không có ngắt
# trang nào mà cũng không báo lỗi. Cách duy nhất hiệu quả với docx là chèn một khối OpenXML thô.
PAGE_BREAK = '\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n'

DOCUMENTS = {
    "bao_cao": ("bao_cao_do_an.md", "BaoCao_GiamSatBenhNhanTuXa.docx", True),
    "bai_bao": ("bai_bao.md", "BaiBao_GiamSatBenhNhanTuXa.docx", False),
}


def check_images(source: Path) -> list[str]:
    """Trả về danh sách ảnh được tham chiếu nhưng không tồn tại."""
    missing = []
    for match in IMAGE.finditer(source.read_text(encoding="utf-8")):
        reference = match.group(1)
        if reference.startswith(("http://", "https://")):
            continue
        if not (source.parent / reference).resolve().exists():
            missing.append(reference)
    return missing


def build(key: str) -> Path:
    name, output, with_toc = DOCUMENTS[key]
    source = REPORT_DIR / name
    if not source.exists():
        raise SystemExit(f"không thấy {source}")
    missing = check_images(source)
    if missing:
        raise SystemExit("thiếu ảnh được tham chiếu:\n  " + "\n  ".join(missing))

    target = REPORT_DIR / output
    # File trung gian phải nằm cùng thư mục với bản gốc để đường dẫn ảnh tương đối vẫn đúng.
    prepared = REPORT_DIR / f".{source.stem}.pandoc.md"
    prepared.write_text(source.read_text(encoding="utf-8").replace("\\newpage", PAGE_BREAK), encoding="utf-8")
    command = [
        pandoc, str(prepared), "-o", str(target),
        "--from", "markdown+pipe_tables+raw_attribute",
        "--resource-path", f"{REPORT_DIR}{';' if sys.platform == 'win32' else ':'}{REPO_ROOT}",
        # Mermaid đã được render sẵn thành PNG; không cần filter nào.
        "--dpi", "200",
    ]
    if with_toc:
        command += ["--toc", "--toc-depth", "3"]
    reference = REPORT_DIR / "reference.docx"
    if reference.exists():
        command += ["--reference-doc", str(reference)]

    try:
        result = subprocess.run(command, capture_output=True, text=True, cwd=REPORT_DIR)
    finally:
        prepared.unlink(missing_ok=True)
    if result.returncode != 0:
        raise SystemExit(f"pandoc lỗi:\n{result.stdout}\n{result.stderr}")
    if result.stderr.strip():
        print("  pandoc:", result.stderr.strip()[:500])
    print(f"  {target.relative_to(REPO_ROOT)}  ({target.stat().st_size // 1024} KB)"
          f"{'  [kiểu Word từ reference.docx]' if reference.exists() else '  [kiểu Word mặc định của Pandoc]'}")
    return target


def main() -> None:
    keys = sys.argv[1:] or list(DOCUMENTS)
    unknown = [k for k in keys if k not in DOCUMENTS]
    if unknown:
        raise SystemExit(f"không rõ tài liệu {unknown}; chọn trong {list(DOCUMENTS)}")
    for key in keys:
        print(f"xuất {key}...")
        build(key)


pandoc = shutil.which("pandoc") or "pandoc"

if __name__ == "__main__":
    main()
