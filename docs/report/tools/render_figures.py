"""Render mọi sơ đồ Mermaid của tài liệu thiết kế thành PNG nền trắng cho báo cáo.

Chạy từ gốc repo:  python docs/report/tools/render_figures.py
                   python docs/report/tools/render_figures.py --list   # chỉ liệt kê, không render

Nguồn sơ đồ gồm hai chỗ:
  1. các khối ```mermaid trong docs/design/02_*.md — trích tự động theo đúng thứ tự xuất hiện;
  2. các tệp .mmd trong docs/report/figures/src/ — sơ đồ chỉ dùng cho báo cáo, không có trong tài liệu thiết kế.

Tên tệp PNG được đặt theo bảng NAMES bên dưới thay vì sinh từ tiêu đề, để báo cáo trích dẫn được một
tên ngắn và ổn định. **Thêm hoặc bớt một khối mermaid trong docs/design sẽ làm lệch chỉ số** — khi đó
script báo lỗi rõ ràng và phải cập nhật NAMES, chứ không âm thầm ghi sai tên tệp.

Cần Node.js; lần chạy đầu `npx @mermaid-js/mermaid-cli` sẽ tải Chromium.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_DIR = REPO_ROOT / "docs" / "design"
FIGURES_DIR = REPO_ROOT / "docs" / "report" / "figures"
SRC_DIR = FIGURES_DIR / "src"

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE = re.compile(r"^```mermaid\s*$")

# (tệp nguồn trong docs/design, thứ tự khối mermaid trong tệp đó) → (tên PNG, chú thích)
NAMES = {
    ("02_1_so_do_chuc_nang.md", 1): ("so_do_chuc_nang", "Sơ đồ chức năng tổng quát của hệ thống"),
    ("02_2_usecase.md", 1): ("usecase", "Biểu đồ Use Case"),
    ("02_3_activity.md", 1): ("activity_streaming_a", "Xử lý dữ liệu streaming: từ message tới bản ghi đã lưu"),
    ("02_3_activity.md", 2): ("activity_streaming_b", "Quyết định cảnh báo và thông báo người được phân công"),
    ("02_3_activity.md", 3): ("activity_dang_nhap", "Luồng đăng nhập và mở kết nối realtime"),
    ("02_3_activity.md", 4): ("activity_drift_a", "DAG drift_check: phát hiện drift và quyết định kích hoạt"),
    ("02_3_activity.md", 5): ("activity_drift_b", "DAG retrain_pipeline: huấn luyện lại và quality gate"),
    ("02_4_sequence.md", 1): ("sequence_realtime", "Tuần tự dự đoán realtime và phát cảnh báo"),
    ("02_4_sequence.md", 2): ("sequence_dang_nhap", "Tuần tự đăng nhập và mở WebSocket"),
    ("02_4_sequence.md", 3): ("sequence_retrain", "Tuần tự kích hoạt huấn luyện lại thủ công"),
    ("02_4_sequence.md", 4): ("sequence_drift", "Tuần tự phát hiện drift và thông báo Admin"),
    ("02_5_class.md", 1): ("class_diagram", "Biểu đồ lớp"),
    ("02_6_dfd_database.md", 1): ("dfd_level0", "DFD mức ngữ cảnh (Level 0)"),
    ("02_6_dfd_database.md", 2): ("dfd_level1", "DFD mức 1"),
    ("02_7_erd.md", 1): ("erd", "Biểu đồ quan hệ dữ liệu (ERD)"),
    ("02_8_thiet_ke_giao_dien.md", 1): ("ia_navigation", "Kiến trúc thông tin và điều hướng giao diện"),
}

# Sơ đồ chỉ dùng cho báo cáo, nguồn nằm ở figures/src/
EXTRA = {"kien_truc_he_thong": "Kiến trúc tổng quát của hệ thống"}

MERMAID_CONFIG = {"theme": "default", "flowchart": {"useMaxWidth": False}, "sequence": {"useMaxWidth": False}}


def extract(path: Path) -> list[dict]:
    """Các khối ```mermaid trong một tệp markdown, kèm tiêu đề gần nhất phía trên."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks, heading, index, i = [], "", 0, 0
    while i < len(lines):
        match = HEADING.match(lines[i])
        if match:
            heading = match.group(2).strip("* ")
        elif FENCE.match(lines[i]):
            body, i = [], i + 1
            while i < len(lines) and lines[i].strip() != "```":
                body.append(lines[i])
                i += 1
            index += 1
            blocks.append({"source": path.name, "heading": heading, "index": index, "code": "\n".join(body)})
        i += 1
    return blocks


def collect() -> list[dict]:
    found = []
    for path in sorted(DESIGN_DIR.glob("02_*.md")):
        for block in extract(path):
            key = (block["source"], block["index"])
            if key not in NAMES:
                raise SystemExit(
                    f"khối mermaid #{block['index']} trong {block['source']} (\"{block['heading']}\") chưa có tên.\n"
                    f"Số khối trong tệp đã thay đổi — cập nhật NAMES trong {Path(__file__).name}."
                )
            name, caption = NAMES[key]
            found.append({**block, "name": name, "caption": caption})
    expected = set(NAMES)
    actual = {(b["source"], b["index"]) for b in found}
    if expected - actual:
        raise SystemExit(f"NAMES khai báo khối không còn tồn tại: {sorted(expected - actual)}")
    for name, caption in EXTRA.items():
        source = SRC_DIR / f"{name}.mmd"
        if not source.exists():
            raise SystemExit(f"thiếu {source}")
        found.append({"source": str(source.relative_to(REPO_ROOT)), "heading": caption, "index": 1,
                      "name": name, "caption": caption, "code": source.read_text(encoding="utf-8")})
    return found


def render(blocks: list[dict]) -> None:
    npx = shutil.which("npx") or "npx"
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        config = work / "mermaid.json"
        config.write_text(json.dumps(MERMAID_CONFIG), encoding="utf-8")
        for block in blocks:
            source = work / f"{block['name']}.mmd"
            source.write_text(block["code"] + "\n", encoding="utf-8")
            target = FIGURES_DIR / f"{block['name']}.png"
            result = subprocess.run(
                [npx, "-y", "@mermaid-js/mermaid-cli", "-i", str(source), "-o", str(target),
                 "-b", "white", "-s", "2", "-c", str(config)],
                capture_output=True, text=True,
            )
            if result.returncode != 0 or not target.exists():
                raise SystemExit(f"render {block['name']} thất bại:\n{result.stdout}\n{result.stderr}")
            print(f"  {block['name'] + '.png':28} {target.stat().st_size // 1024:5} KB   {block['caption']}")


def main() -> None:
    blocks = collect()
    if "--list" in sys.argv:
        for block in blocks:
            print(f"  {block['name']:28} <- {block['source']} #{block['index']} | {block['heading']}")
    else:
        render(blocks)
    print(f"\n{len(blocks)} sơ đồ")


if __name__ == "__main__":
    main()
