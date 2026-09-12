"""Tải logo công nghệ (SVG) về `docs/report/figures/logos/` để render sơ đồ không cần mạng.

Chạy từ gốc repo:  python docs/report/tools/fetch_logos.py

Nguồn: Simple Icons (https://simpleicons.org) — giấy phép **CC0 1.0**, không yêu cầu ghi công, nên
commit trực tiếp vào repo được. Mỗi icon là một path đơn sắc đã mang màu thương hiệu chính thức, nét đồng
đều giữa các hãng — đúng thứ cần cho sơ đồ trông gọn thay vì mỗi logo một phong cách.

Logo đã tải thì bỏ qua; thêm `--force` để tải lại.
"""

import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "docs" / "report" / "figures" / "logos"

# tên tệp → slug của Simple Icons
LOGOS = {
    "kafka": "apachekafka",
    "postgresql": "postgresql",
    "timescale": "timescale",
    "mlflow": "mlflow",
    "airflow": "apacheairflow",
    "fastapi": "fastapi",
    "react": "react",
    "docker": "docker",
    "prometheus": "prometheus",
    "grafana": "grafana",
    "tensorflow": "tensorflow",
    "scikitlearn": "scikitlearn",
    "python": "python",
}


def main() -> None:
    force = "--force" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, slug in LOGOS.items():
        target = OUT_DIR / f"{name}.svg"
        if target.exists() and not force:
            print(f"  bỏ qua {name}.svg (đã có)")
            continue
        request = urllib.request.Request(
            f"https://cdn.simpleicons.org/{slug}",
            headers={"User-Agent": "rpm-report-figures/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        if not data.lstrip().startswith(b"<svg"):
            raise SystemExit(f"{slug}: phản hồi không phải SVG")
        target.write_bytes(data)
        print(f"  {name}.svg  {len(data)} bytes  (slug {slug})")

    (OUT_DIR / "NGUON.md").write_text(
        "# Nguồn logo\n\n"
        "Toàn bộ tệp `.svg` trong thư mục này tải từ [Simple Icons](https://simpleicons.org) bằng\n"
        "`python docs/report/tools/fetch_logos.py`.\n\n"
        "Giấy phép: **CC0 1.0 Universal** (không yêu cầu ghi công).\n\n"
        "Logo là nhãn hiệu của các chủ sở hữu tương ứng; ở đây chỉ dùng để chỉ dẫn công nghệ được sử dụng\n"
        "trong sơ đồ kiến trúc, không hàm ý bất kỳ sự bảo trợ nào.\n",
        encoding="utf-8",
    )
    print(f"\n{len(LOGOS)} logo trong {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
