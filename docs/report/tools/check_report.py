"""Soát và sửa tính nhất quán của báo cáo/bài báo.

Chạy từ gốc repo:
  python docs/report/tools/check_report.py            # chỉ soát, không sửa
  python docs/report/tools/check_report.py --renumber  # đánh số lại Hình/Bảng và sinh lại 2 danh mục

Bốn lỗi mà viết tay rất dễ mắc và script này bắt được:
  1. số Hình/Bảng lệch thứ tự xuất hiện (thêm một hình vào giữa là lệch hết phía sau);
  2. chú thích trong danh mục khác chú thích trong thân bài;
  3. bảng chưa được đánh số;
  4. trích dẫn [n] không có trong danh mục tài liệu tham khảo, hoặc ngược lại;
  5. ảnh được tham chiếu nhưng không tồn tại trên đĩa.

`--renumber` chỉ áp dụng cho báo cáo (có hai danh mục ở phần đầu); bài báo dùng số hình liên tục
nên không tự đánh số lại.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = REPO_ROOT / "docs" / "report"
REPORT = REPORT_DIR / "bao_cao_do_an.md"
PAPER = REPORT_DIR / "bai_bao.md"

CAPTION = re.compile(r"^\*\*(Hình|Bảng) ([\d.]+)\*\*\s*(.*)$")
CHAPTER = re.compile(r"^# CHƯƠNG (\d+)")
LIST_ROW = re.compile(r"^\| (Hình|Bảng) ([\d.]+) \| (.*?) \|$")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
TABLE_START = re.compile(r"^\|.*\|$")
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|$")
CITED = re.compile(r"(?<!\\)\[(\d+)\]")
LISTED_REF = re.compile(r"\\\[(\d+)\\\]")

problems: list[str] = []


def body_of(lines: list[str]) -> int:
    """Chỉ số dòng bắt đầu thân bài (sau phần đầu có 2 danh mục)."""
    for i, line in enumerate(lines):
        if line.startswith("# CHƯƠNG 1"):
            return i
    return 0


def walk_captions(lines: list[str], start: int) -> tuple[list, list]:
    chapter, counters = 0, {"Hình": 0, "Bảng": 0}
    figures, tables = [], []
    for i in range(start, len(lines)):
        match = CHAPTER.match(lines[i])
        if match:
            chapter, counters = int(match.group(1)), {"Hình": 0, "Bảng": 0}
            continue
        caption = CAPTION.match(lines[i])
        if caption:
            kind, number, text = caption.groups()
            counters[kind] += 1
            want = f"{chapter}.{counters[kind]}"
            entry = {"line": i, "kind": kind, "number": number, "want": want, "text": text.strip().rstrip(".")}
            (figures if kind == "Hình" else tables).append(entry)
    return figures, tables


def check_untitled_tables(lines: list[str], start: int) -> None:
    i = start
    while i < len(lines):
        if TABLE_START.match(lines[i]) and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1]):
            before = [lines[j].strip() for j in range(max(start, i - 3), i) if lines[j].strip()]
            if not any(b.startswith("**Bảng") for b in before):
                problems.append(f"bảng ở dòng {i + 1} chưa có chú thích **Bảng x.y**: {lines[i][:70]}")
            while i < len(lines) and lines[i].startswith("|"):
                i += 1
            continue
        i += 1


def check_lists(lines: list[str], figures: list, tables: list) -> None:
    listed = {"Hình": [], "Bảng": []}
    for line in lines[: body_of(lines)]:
        row = LIST_ROW.match(line)
        if row:
            kind, number, text = row.groups()
            listed[kind].append((number, text.strip().rstrip(".")))
    for kind, used in (("Hình", figures), ("Bảng", tables)):
        want = [(e["number"], e["text"]) for e in used]
        if listed[kind] != want:
            problems.append(f"danh mục {kind} không khớp thân bài ({len(listed[kind])} dòng so với {len(want)})")


def check_images(path: Path) -> None:
    for reference in IMAGE.findall(path.read_text(encoding="utf-8")):
        if reference.startswith(("http://", "https://")):
            continue
        if not (path.parent / reference).resolve().exists():
            problems.append(f"{path.name}: thiếu ảnh {reference}")


def check_refs(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    cut = text.rfind("TÀI LIỆU THAM KHẢO")
    if cut < 0:
        problems.append(f"{path.name}: không thấy mục TÀI LIỆU THAM KHẢO")
        return
    cited = {int(n) for n in CITED.findall(text[:cut])}
    listed = {int(n) for n in LISTED_REF.findall(text[cut:])}
    if cited - listed:
        problems.append(f"{path.name}: trích dẫn {sorted(cited - listed)} không có trong danh mục")
    if listed - cited:
        problems.append(f"{path.name}: tài liệu {sorted(listed - cited)} có trong danh mục nhưng chưa được trích dẫn")


def renumber(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = body_of(lines)
    figures, tables = walk_captions(lines, start)
    for entry in figures + tables:
        lines[entry["line"]] = f"**{entry['kind']} {entry['want']}** {entry['text']}"

    def render_list(kind: str, rows: list) -> list[str]:
        label = "hình" if kind == "Hình" else "bảng"
        return [f"| {kind} | Tên {label} |", "|---|---|"] + [
            f"| {kind} {e['want']} | {e['text']} |" for e in rows
        ]

    def replace(lines: list[str], header: str, kind: str, rows: list) -> list[str]:
        begin = next(i for i, line in enumerate(lines) if line.startswith(header))
        table = next(i for i in range(begin, begin + 12) if lines[i].startswith(f"| {kind} |"))
        end = table
        while end < len(lines) and lines[end].startswith("|"):
            end += 1
        return lines[:table] + render_list(kind, rows) + lines[end:]

    lines = replace(lines, "# DANH MỤC CÁC HÌNH VẼ", "Hình", figures)
    lines = replace(lines, "# DANH MỤC CÁC BẢNG", "Bảng", tables)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"đã đánh số lại {len(figures)} hình, {len(tables)} bảng và sinh lại 2 danh mục")


def main() -> None:
    if "--renumber" in sys.argv:
        renumber(REPORT)

    lines = REPORT.read_text(encoding="utf-8").splitlines()
    start = body_of(lines)
    figures, tables = walk_captions(lines, start)
    for entry in figures + tables:
        if entry["number"] != entry["want"]:
            problems.append(
                f"{entry['kind']} {entry['number']} ở dòng {entry['line'] + 1} lẽ ra là {entry['want']}"
                f" (thứ tự xuất hiện) — chạy lại với --renumber"
            )
    check_untitled_tables(lines, start)
    check_lists(lines, figures, tables)
    for path in (REPORT, PAPER):
        check_images(path)
        check_refs(path)

    print(f"báo cáo: {len(figures)} hình, {len(tables)} bảng")
    if problems:
        print(f"\n{len(problems)} vấn đề:")
        for item in problems:
            print("  -", item)
        raise SystemExit(1)
    print("không có vấn đề")


if __name__ == "__main__":
    main()
