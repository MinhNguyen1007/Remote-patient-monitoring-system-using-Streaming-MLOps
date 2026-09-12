"""Render các sơ đồ viết bằng HTML/CSS trong `docs/report/figures/src/` thành PNG.

Chạy từ gốc repo:
    python docs/report/tools/render_html_figures.py                # render tất cả
    python docs/report/tools/render_html_figures.py so_do_tong_quat  # render một hình

Dùng Chrome ở chế độ headless với `--force-device-scale-factor=2` để chữ sắc nét. Chrome không tự cắt ảnh
theo nội dung và ở chế độ dòng lệnh cũng không chạy được JS để đo chiều cao, nên cách làm là **chụp với
chiều cao dư rồi cắt phần nền trắng thừa** bằng Pillow. Nhờ vậy sửa nội dung HTML không phải sửa lại
chiều cao ở đâu cả.

Logo nằm ở `figures/logos/` (tải bằng `fetch_logos.py`), được tham chiếu bằng đường dẫn tương đối nên
Chrome đọc trực tiếp từ đĩa, không cần mạng.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "docs" / "report" / "figures" / "src"
OUT_DIR = REPO_ROOT / "docs" / "report" / "figures"
SCALE = 2

CHROME_CANDIDATES = [
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    Path.home() / ".cache/puppeteer/chrome",
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
]


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
        if candidate.is_dir():  # thư mục cache của puppeteer: .../chrome/<version>/chrome-win64/chrome.exe
            found = sorted(candidate.glob("*/chrome-*/chrome*"))
            binaries = [f for f in found if f.is_file() and f.suffix in ("", ".exe")]
            if binaries:
                return str(binaries[-1])
    for name in ("google-chrome", "chromium", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit("không tìm thấy Chrome/Chromium để render HTML")


def sheet_width(html: Path) -> int:
    """Bề rộng khai báo trong `.sheet { width: ...px }` của chính tệp HTML."""
    match = re.search(r"\.sheet\s*\{[^}]*?width:\s*(\d+)px", html.read_text(encoding="utf-8"))
    return int(match.group(1)) if match else 1400


def run_chrome(chrome: str, url: str, width: int, height: int, extra: list[str]) -> str:
    with tempfile.TemporaryDirectory() as profile:
        command = [
            chrome, "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}",
            f"--force-device-scale-factor={SCALE}",
            f"--window-size={width},{height}",
            *extra, url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        return result.stdout + result.stderr


def crop_white(path: Path) -> tuple[int, int]:
    """Cắt phần nền trắng thừa ở dưới/phải, giữ lề 24px (đã nhân SCALE)."""
    from PIL import Image

    margin = 12 * SCALE
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        # getbbox() trên ảnh đảo màu: vùng khác trắng
        from PIL import ImageChops

        white = Image.new("RGB", rgb.size, (255, 255, 255))
        box = ImageChops.difference(rgb, white).getbbox()
        if box is None:
            raise SystemExit(f"{path.name}: ảnh trắng hoàn toàn")
        right = min(rgb.width, box[2] + margin)
        bottom = min(rgb.height, box[3] + margin)
        cropped = rgb.crop((0, 0, right, bottom))
        cropped.save(path)
        return cropped.size


def render(name: str, chrome: str) -> None:
    html = SRC_DIR / f"{name}.html"
    if not html.exists():
        raise SystemExit(f"không thấy {html}")
    width = sheet_width(html)
    target = OUT_DIR / f"{name}.png"
    url = html.resolve().as_uri()
    # Chụp với chiều cao dư thật nhiều rồi cắt nền trắng — không đoán chiều cao.
    run_chrome(chrome, url, width, 4000, [f"--screenshot={target}"])
    if not target.exists():
        raise SystemExit(f"render {name} thất bại (Chrome không tạo được ảnh)")
    size = crop_white(target)
    print(f"  {name + '.png':26} {size[0]}x{size[1]}  {target.stat().st_size // 1024} KB")


def main() -> None:
    chrome = find_chrome()
    names = sys.argv[1:] or sorted(p.stem for p in SRC_DIR.glob("*.html"))
    print(f"Chrome: {chrome}\n")
    for name in names:
        render(name, chrome)
    print(f"\n{len(names)} hình trong {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
