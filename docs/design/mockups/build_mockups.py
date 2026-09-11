"""Sinh các artboard mockup (.dc.html) cho giao diện RPM — docs/design/02_8_thiet_ke_giao_dien.md.

Design system: skill `csgo-case-opening-design` (token lấy nguyên từ reference/DESIGN_DNA.md), màu trạng thái theo
skill `dataviz` (luôn kèm icon + nhãn chữ). Mọi số liệu là số liệu mẫu, định dạng giống hệt response của backend.

Chạy: python docs/design/mockups/build_mockups.py  → ghi *.dc.html + canvas.json cạnh file này.
"""

import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------------------------- tokens
BG, FG, CARD, POPOVER = "#101113", "#f3f3ef", "#191a1e", "#24252a"
PRIMARY, PRIMARY_FG = "#d2f65b", "#15180c"
SECONDARY, MUTED, MUTED_FG = "#25272c", "#24252b", "#999ba3"
ACCENT, ACCENT_FG, BORDER, INPUT = "#33362c", "#e4ff99", "#303137", "#3d3f46"
RISK = {  # màu trạng thái (dataviz status palette, dark surface) — luôn đi kèm icon + nhãn
    "NORMAL": ("#0ca30c", "Bình thường", "check"),
    "WARNING": ("#fab219", "Cảnh báo", "triangle"),
    "CRITICAL": ("#d03b3b", "Nguy kịch", "octagon"),
}
ANOMALY = "#9085e9"   # --anomaly-flag, tách biệt khỏi màu risk-level
SERIES = "#3987e5"    # đường vitals (dataviz categorical slot 1, dark)
SERIES_2 = "#86b6ef"  # tâm trương (cùng hue, nhạt hơn + nét đứt)
GRID, AXIS = "#2c2c2a", "#383835"
W = 1440

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800'
         '&amp;family=JetBrains+Mono:wght@400;500;600&amp;display=swap">')

BASE_CSS = f"""
:root {{
  --background: {BG}; --foreground: {FG}; --card: {CARD}; --popover: {POPOVER};
  --primary: {PRIMARY}; --primary-foreground: {PRIMARY_FG}; --secondary: {SECONDARY};
  --muted: {MUTED}; --muted-foreground: {MUTED_FG}; --accent: {ACCENT}; --accent-foreground: {ACCENT_FG};
  --border: {BORDER}; --input: {INPUT}; --ring: {PRIMARY}; --radius: .4rem;
  --radius-sm: calc(var(--radius) * .6); --radius-md: calc(var(--radius) * .8); --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4); --radius-2xl: calc(var(--radius) * 1.8);
  --risk-normal: {RISK['NORMAL'][0]}; --risk-warning: {RISK['WARNING'][0]}; --risk-critical: {RISK['CRITICAL'][0]};
  --anomaly-flag: {ANOMALY};
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--background); color: var(--foreground);
  font-family: "Be Vietnam Pro", "Segoe UI", system-ui, sans-serif; font-size: 14px; line-height: 1.5;
  -webkit-font-smoothing: antialiased; }}
a {{ color: var(--primary); text-decoration: none; }} a:hover {{ color: {ACCENT_FG}; }}
.mono {{ font-family: "JetBrains Mono", ui-monospace, Consolas, monospace; font-variant-numeric: tabular-nums; }}
.eyebrow {{ font-family: "JetBrains Mono", ui-monospace, Consolas, monospace; font-size: 12px; letter-spacing: 2px;
  text-transform: uppercase; color: var(--muted-foreground); display: flex; align-items: center; gap: 8px; }}
.eyebrow::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--primary); }}
h1 {{ margin: 0; font-size: 34px; font-weight: 800; letter-spacing: -1.2px; line-height: 1.15; }}
h2 {{ margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -.4px; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-xl); }}
.muted {{ color: var(--muted-foreground); }}
.btn {{ display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 36px; padding: 0 14px;
  border-radius: var(--radius-lg); font: 600 13px "Be Vietnam Pro", "Segoe UI", sans-serif; border: 1px solid transparent; }}
.btn-primary {{ background: var(--primary); color: var(--primary-foreground); }}
.btn-outline {{ background: transparent; color: var(--foreground); border-color: var(--border); }}
.btn-ghost {{ background: transparent; color: var(--muted-foreground); }}
.chip {{ display: inline-flex; align-items: center; gap: 6px; height: 26px; padding: 0 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600; border: 1px solid var(--border); background: var(--secondary); }}
table {{ border-collapse: collapse; width: 100%; }}
th {{ text-align: left; font: 500 11px "JetBrains Mono", ui-monospace, monospace; letter-spacing: 1.5px;
  text-transform: uppercase; color: var(--muted-foreground); padding: 10px 16px; border-bottom: 1px solid var(--border); }}
td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
.input {{ height: 38px; border-radius: var(--radius-lg); border: 1px solid var(--input); background: {BG};
  display: flex; align-items: center; padding: 0 12px; gap: 8px; color: var(--foreground); }}
.focus {{ outline: 2px solid var(--primary); outline-offset: 3px; }}
"""

# ------------------------------------------------------------------------------------------------ icons
ICON_PATHS = {
    "check": '<circle cx="12" cy="12" r="9"></circle><path d="m8.5 12.5 2.5 2.5 4.5-5"></path>',
    "triangle": '<path d="M12 3.5 2.8 19.5h18.4z"></path><path d="M12 10v4.5"></path><path d="M12 17.2v.1"></path>',
    "octagon": '<path d="M8.2 3h7.6L21 8.2v7.6L15.8 21H8.2L3 15.8V8.2z"></path><path d="M12 7.5v5.5"></path><path d="M12 16.3v.1"></path>',
    "pulse": '<path d="M3 12h4l2.5-6 5 12 2.5-6h4"></path>',
    "bell": '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"></path><path d="M10 20.5a2 2 0 0 0 4 0"></path>',
    "grid": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"></rect><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"></rect><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"></rect><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"></rect>',
    "users": '<circle cx="9" cy="8" r="3.5"></circle><path d="M2.5 20a6.5 6.5 0 0 1 13 0"></path><path d="M16 4.5a3.5 3.5 0 0 1 0 7"></path><path d="M18 14.5a6.5 6.5 0 0 1 3.5 5.5"></path>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"></path><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"></path>',
    "sliders": '<path d="M4 7h9"></path><path d="M17 7h3"></path><circle cx="15" cy="7" r="2"></circle><path d="M4 17h3"></path><path d="M11 17h9"></path><circle cx="9" cy="17" r="2"></circle>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"></rect><path d="M9 2.5v3M15 2.5v3M9 18.5v3M15 18.5v3M2.5 9h3M2.5 15h3M18.5 9h3M18.5 15h3"></path>',
    "logout": '<path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4"></path><path d="m9 16-4-4 4-4"></path><path d="M5 12h11"></path>',
    "chevron-left": '<path d="m14.5 6-6 6 6 6"></path>',
    "chevron-down": '<path d="m6 9.5 6 6 6-6"></path>',
    "search": '<circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 4.5 4.5"></path>',
    "plus": '<path d="M12 5v14M5 12h14"></path>',
    "x": '<path d="M6 6l12 12M18 6 6 18"></path>',
    "tick": '<path d="m5 12.5 4.5 4.5L19 7.5"></path>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"></path><path d="M4 3.5V8h4.5"></path><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"></path><path d="M20 20.5V16h-4.5"></path>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"></rect><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"></path>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="m3.5 6.5 8.5 6.5 8.5-6.5"></path>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"></path><circle cx="12" cy="12" r="2.8"></circle>',
    "pencil": '<path d="M4 20h4L19.5 8.5a2.8 2.8 0 0 0-4-4L4 16z"></path>',
    "clock": '<circle cx="12" cy="12" r="9"></circle><path d="M12 7.5V12l3 2"></path>',
}


def icon(name: str, size: int = 16, color: str = "currentColor", stroke: float = 1.8) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
            f'style="flex-shrink: 0">{ICON_PATHS[name]}</svg>')


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def vn(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


# ------------------------------------------------------------------------------------------- components
def risk_badge(level: str, score: float | None = None, large: bool = False) -> str:
    color, label, ico = RISK[level]
    height, pad, font, isz = (40, 14, 15, 18) if large else (28, 10, 12.5, 15)
    score_html = (f'<span class="mono" style="color: {MUTED_FG}; font-weight: 500; font-size: {font - 1}px">'
                  f'{vn(score)}</span>') if score is not None else ""
    return (f'<span style="display: inline-flex; align-items: center; gap: 7px; height: {height}px; padding: 0 {pad}px; '
            f'border-radius: 999px; background: {rgba(color, .14)}; border: 1px solid {rgba(color, .45)}; '
            f'font-size: {font}px; font-weight: 700; color: {FG}; white-space: nowrap">'
            f'{icon(ico, isz, color, 2)}<span>{label}</span>{score_html}</span>')


def news2_chip(score: int | None) -> str:
    value = "—" if score is None else str(score)
    return (f'<span class="mono" style="display: inline-flex; align-items: baseline; gap: 6px; height: 28px; padding: 0 10px; '
            f'border-radius: var(--radius-lg); border: 1px solid {BORDER}; background: {SECONDARY}; align-items: center">'
            f'<span style="font-size: 10.5px; letter-spacing: 1.2px; color: {MUTED_FG}">NEWS2</span>'
            f'<span style="font-size: 14px; font-weight: 600; color: {FG}">{value}</span></span>')


def anomaly_chip(score: float | None, threshold: float = 0.99) -> str:
    if score is None:
        return (f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: {MUTED_FG}">'
                f'{icon("clock", 14, MUTED_FG)}Chưa đủ 16 giờ</span>')
    flagged = score >= threshold
    color = ANOMALY if flagged else MUTED_FG
    label = "Bất thường" if flagged else "Ổn định"
    border = rgba(ANOMALY, .5) if flagged else BORDER
    bg = rgba(ANOMALY, .14) if flagged else "transparent"
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 26px; padding: 0 9px; '
            f'border-radius: 999px; border: 1px solid {border}; background: {bg}; font-size: 12px; font-weight: 600">'
            f'{icon("pulse", 14, color, 2)}<span style="color: {FG}">{label}</span>'
            f'<span class="mono" style="color: {MUTED_FG}; font-weight: 500">{vn(score, 3)}</span></span>')


STATUS = {"OPEN": ("Mở", PRIMARY, PRIMARY_FG), "ACKNOWLEDGED": ("Đã xác nhận", "#86b6ef", BG),
          "RESOLVED": ("Đã xử lý", MUTED_FG, BG)}


def status_pill(status: str) -> str:
    label, color, _ = STATUS[status]
    return (f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 9px; '
            f'border-radius: 999px; border: 1px solid {rgba(color, .5)}; font-size: 12px; font-weight: 600; color: {FG}">'
            f'<span style="width: 6px; height: 6px; border-radius: 50%; background: {color}"></span>{label}</span>')


def alert_type(kind: str) -> str:
    if kind == "RISK":
        color, text, ico = RISK["CRITICAL"][0], "Rủi ro nguy kịch", "octagon"
    else:
        color, text, ico = ANOMALY, "Bất thường", "pulse"
    return (f'<span style="display: inline-flex; align-items: center; gap: 8px; font-weight: 600">'
            f'<span style="display: inline-flex; width: 28px; height: 28px; border-radius: var(--radius-lg); '
            f'align-items: center; justify-content: center; background: {rgba(color, .16)}">{icon(ico, 16, color, 2)}</span>'
            f'{text}</span>')


def realtime_indicator(connected: bool = True) -> str:
    color, text = (PRIMARY, "Realtime · đã kết nối") if connected else ("#fab219", "Đang kết nối lại…")
    return (f'<span class="mono" style="display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: {MUTED_FG}">'
            f'<span style="width: 8px; height: 8px; border-radius: 50%; background: {color}; '
            f'box-shadow: 0 0 0 4px {rgba(color, .15)}"></span>{text}</span>')


def logo() -> str:
    return (f'<div style="display: flex; align-items: center; gap: 10px">'
            f'<div style="width: 34px; height: 34px; border-radius: var(--radius-lg); background: {PRIMARY}; display: flex; '
            f'align-items: center; justify-content: center">{icon("pulse", 20, PRIMARY_FG, 2.4)}</div>'
            f'<div style="display: flex; flex-direction: column; line-height: 1.1">'
            f'<span style="font-weight: 800; font-size: 17px; letter-spacing: -.5px">RPM Monitor</span>'
            f'<span class="mono" style="font-size: 10.5px; letter-spacing: 1.5px; color: {MUTED_FG}">ICU · REALTIME</span>'
            f'</div></div>')


def nav_item(ico: str, label: str, active: bool = False, badge: int | None = None) -> str:
    bg = ACCENT if active else "transparent"
    color = ACCENT_FG if active else MUTED_FG
    badge_html = (f'<span class="mono" style="margin-left: auto; min-width: 22px; height: 20px; padding: 0 6px; '
                  f'border-radius: 999px; background: {RISK["CRITICAL"][0]}; color: {FG}; font-size: 11.5px; '
                  f'font-weight: 600; display: flex; align-items: center; justify-content: center">{badge}</span>'
                  if badge else "")
    return (f'<div style="display: flex; align-items: center; gap: 10px; height: 40px; padding: 0 12px; '
            f'border-radius: var(--radius-lg); background: {bg}; color: {color}; font-weight: {600 if active else 500}">'
            f'{icon(ico, 18, color)}<span>{label}</span>{badge_html}</div>')


def sidebar(role: str, active: str, name: str, open_alerts: int = 3) -> str:
    role_label = {"DOCTOR": "Bác sĩ", "NURSE": "Điều dưỡng", "ADMIN": "Quản trị viên"}[role]
    if role == "ADMIN":
        items = [("users", "Người dùng"), ("link", "Phân công"), ("sliders", "Ngưỡng cảnh báo"), ("cpu", "Giám sát mô hình")]
        nav = (f'<div class="mono" style="font-size: 10.5px; letter-spacing: 1.8px; color: {MUTED_FG}; '
               f'padding: 0 12px 6px">QUẢN TRỊ</div>'
               + "".join(nav_item(i, lbl, lbl == active) for i, lbl in items))
    else:
        nav = (nav_item("grid", "Bệnh nhân", active == "Bệnh nhân")
               + nav_item("bell", "Cảnh báo", active == "Cảnh báo", badge=open_alerts))
    initials = "".join(w[0] for w in name.replace(".", "").split()[-2:]).upper()
    return (f'<aside style="width: 248px; flex-shrink: 0; background: {CARD}; border-right: 1px solid {BORDER}; '
            f'display: flex; flex-direction: column; padding: 20px 14px; gap: 28px">'
            f'<div style="padding: 0 6px">{logo()}</div>'
            f'<nav style="display: flex; flex-direction: column; gap: 4px">{nav}</nav>'
            f'<div style="margin-top: auto; display: flex; align-items: center; gap: 10px; padding: 12px; '
            f'border-radius: var(--radius-xl); border: 1px solid {BORDER}; background: {BG}">'
            f'<div style="width: 34px; height: 34px; border-radius: 50%; background: {SECONDARY}; display: flex; '
            f'align-items: center; justify-content: center; font-weight: 700; font-size: 13px">{initials}</div>'
            f'<div style="display: flex; flex-direction: column; line-height: 1.25; min-width: 0">'
            f'<span style="font-weight: 600; font-size: 13px; white-space: nowrap">{name}</span>'
            f'<span class="mono" style="font-size: 11px; color: {MUTED_FG}">{role_label}</span></div>'
            f'<div style="margin-left: auto; color: {MUTED_FG}; display: flex" title="Đăng xuất">{icon("logout", 18)}</div>'
            f'</div></aside>')


def shell(role: str, active: str, name: str, content: str, height: int, open_alerts: int = 3) -> str:
    return (f'<div style="width: {W}px; min-height: {height}px; display: flex; background: {BG}">'
            f'{sidebar(role, active, name, open_alerts)}'
            f'<main style="flex-grow: 1; min-width: 0; padding: 28px 36px 36px; display: flex; flex-direction: column; '
            f'gap: 24px">{content}</main></div>')


def page_header(eyebrow: str, title: str, right: str = "", sub: str = "") -> str:
    sub_html = f'<p class="muted" style="margin: 0; max-width: 720px; text-wrap: pretty">{sub}</p>' if sub else ""
    return (f'<header style="display: flex; align-items: flex-end; justify-content: space-between; gap: 24px">'
            f'<div style="display: flex; flex-direction: column; gap: 10px"><div class="eyebrow">{eyebrow}</div>'
            f'<h1>{title}</h1>{sub_html}</div>'
            f'<div style="display: flex; align-items: center; gap: 12px">{right}</div></header>')


def segmented(options: list[tuple[str, str | None]], active: int = 0) -> str:
    parts = []
    for i, (label, count) in enumerate(options):
        on = i == active
        count_html = f'<span class="mono" style="color: {PRIMARY_FG if on else MUTED_FG}; opacity: .8">{count}</span>' if count else ""
        parts.append(f'<div style="display: flex; align-items: center; gap: 7px; height: 32px; padding: 0 12px; '
                     f'border-radius: var(--radius-md); font-size: 13px; font-weight: 600; '
                     f'background: {PRIMARY if on else "transparent"}; color: {PRIMARY_FG if on else MUTED_FG}">'
                     f'{label}{count_html}</div>')
    return (f'<div style="display: flex; gap: 2px; padding: 3px; border-radius: var(--radius-lg); '
            f'border: 1px solid {BORDER}; background: {CARD}">{"".join(parts)}</div>')


def document(title: str, body: str, extra_css: str = "") -> str:
    return ("<!doctype html>\n<html>\n<head>\n  <meta charset=\"utf-8\">\n  <script src=\"./support.js\"></script>\n"
            f"</head>\n<body>\n<x-dc>\n<helmet>\n  <title>{title}</title>\n  {FONTS}\n  <style>{BASE_CSS}{extra_css}</style>\n"
            f"</helmet>\n{body}\n</x-dc>\n</body>\n</html>\n")


# ------------------------------------------------------------------------------------------- dữ liệu mẫu
PATIENTS = [  # đã sắp theo rủi ro như API /patients trả về
    dict(name="BN-10069", age=76, gender="Nữ", mimic=10069, level="CRITICAL", risk=0.72, news2=9, hr=126, spo2=90,
         rr=26, bp="94/52", temp=38.4, anomaly=0.997, open=2, hour=65, ago="3 giây trước",
         strip="WWWWCCCCCCCC"),
    dict(name="BN-10074", age=68, gender="Nam", mimic=10074, level="CRITICAL", risk=0.39, news2=7, hr=112, spo2=93,
         rr=24, bp="101/60", temp=37.9, anomaly=None, open=1, hour=11, ago="3 giây trước",
         strip="WWWWWWCCCCC"),
    dict(name="BN-10056", age=81, gender="Nữ", mimic=10056, level="WARNING", risk=0.21, news2=5, hr=98, spo2=95,
         rr=21, bp="118/64", temp=37.6, anomaly=0.412, open=0, hour=23, ago="4 giây trước",
         strip="NNNNNNWWWWWW"),
    dict(name="BN-10032", age=88, gender="Nam", mimic=10032, level="WARNING", risk=0.18, news2=4, hr=103, spo2=96,
         rr=19, bp="102/55", temp=36.9, anomaly=0.866, open=0, hour=79, ago="4 giây trước",
         strip="WWWNNNNWWWWW"),
    dict(name="BN-10035", age=59, gender="Nam", mimic=10035, level="NORMAL", risk=0.04, news2=2, hr=84, spo2=97,
         rr=16, bp="126/71", temp=37.0, anomaly=0.195, open=0, hour=32, ago="5 giây trước",
         strip="NNNNNNNNNNNN"),
    dict(name="BN-10090", age=64, gender="Nữ", mimic=10090, level="NORMAL", risk=0.10, news2=1, hr=77, spo2=98,
         rr=15, bp="131/78", temp=36.8, anomaly=0.281, open=0, hour=40, ago="5 giây trước",
         strip="NNNWNNNNNNNN"),
]
STRIP_LEVEL = {"N": "NORMAL", "W": "WARNING", "C": "CRITICAL"}


# ------------------------------------------------------------------------------------------------ Đăng nhập
def login() -> str:
    body = f"""
<div style="width: {W}px; height: 900px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); background: {BG}">
  <section style="display: flex; flex-direction: column; justify-content: space-between; padding: 48px 56px; border-right: 1px solid {BORDER};
    background: radial-gradient(900px 520px at 0% 100%, {rgba(PRIMARY, .07)}, transparent 70%), {BG}">
    {logo()}
    <div style="display: flex; flex-direction: column; gap: 18px; max-width: 520px">
      <div class="eyebrow">Hệ thống giám sát bệnh nhân từ xa</div>
      <h1 style="font-size: 52px; letter-spacing: -2.4px">Cảnh báo sớm nguy kịch trong 4 giờ tới.</h1>
      <p class="muted" style="margin: 0; font-size: 15px; text-wrap: pretty">Vitals ICU được phát theo thời gian thực, dự báo rủi ro bằng mô hình học máy và phát hiện diễn biến bất thường so với baseline của chính bệnh nhân.</p>
    </div>
    <div style="display: flex; gap: 10px; flex-wrap: wrap">
      {risk_badge("NORMAL")}{risk_badge("WARNING")}{risk_badge("CRITICAL")}
    </div>
  </section>
  <section style="display: flex; align-items: center; justify-content: center">
    <div class="card" style="width: 420px; padding: 32px; display: flex; flex-direction: column; gap: 22px; background: {CARD}">
      <div style="display: flex; flex-direction: column; gap: 6px">
        <h2 style="font-size: 24px; font-weight: 800; letter-spacing: -.8px">Đăng nhập</h2>
        <span class="muted">Dành cho Bác sĩ, Điều dưỡng và Quản trị viên</span>
      </div>
      <label style="display: flex; flex-direction: column; gap: 8px">
        <span style="font-size: 13px; font-weight: 600">Email</span>
        <div class="input focus">{icon("mail", 16, MUTED_FG)}<span>bs.an@rpm.local</span></div>
      </label>
      <label style="display: flex; flex-direction: column; gap: 8px">
        <span style="font-size: 13px; font-weight: 600">Mật khẩu</span>
        <div class="input">{icon("lock", 16, MUTED_FG)}<span class="mono" style="letter-spacing: 3px">••••••••••</span>
          <span style="margin-left: auto; color: {MUTED_FG}; display: flex">{icon("eye", 16)}</span></div>
      </label>
      <div class="btn btn-primary" style="height: 42px; font-size: 14px">Đăng nhập</div>
      <div style="display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--radius-lg);
        background: {rgba(RISK['CRITICAL'][0], .12)}; border: 1px solid {rgba(RISK['CRITICAL'][0], .4)}; font-size: 13px">
        {icon("octagon", 16, RISK['CRITICAL'][0], 2)}<span>Email hoặc mật khẩu không đúng</span>
      </div>
    </div>
  </section>
</div>"""
    return document("Đăng nhập", body)


# ------------------------------------------------------------------------------------------------ Dashboard
def patient_card(p: dict) -> str:
    color = RISK[p["level"]][0]
    cells = "".join(
        f'<span style="flex-grow: 1; height: 8px; border-radius: 2px; background: {rgba(RISK[STRIP_LEVEL[c]][0], .85)}"></span>'
        for c in p["strip"].rjust(12, "-") if c != "-"
    )
    missing = 12 - len(p["strip"])
    pad = "".join(f'<span style="flex-grow: 1; height: 8px; border-radius: 2px; background: {SECONDARY}"></span>' for _ in range(missing))
    open_html = (f'<span style="display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600">'
                 f'{icon("bell", 15, RISK["CRITICAL"][0], 2)}{p["open"]} cảnh báo mở</span>'
                 if p["open"] else f'<span class="muted" style="font-size: 12.5px">Không có cảnh báo mở</span>')

    def vital(label: str, value: str, unit: str) -> str:
        return (f'<div style="display: flex; flex-direction: column; gap: 2px">'
                f'<span class="mono" style="font-size: 10.5px; letter-spacing: 1.3px; color: {MUTED_FG}">{label}</span>'
                f'<span class="mono" style="font-size: 20px; font-weight: 600; letter-spacing: -.5px">{value}'
                f'<span style="font-size: 11px; color: {MUTED_FG}; font-weight: 500; margin-left: 3px">{unit}</span></span></div>')

    return f"""
<article class="card" style="padding: 18px; display: flex; flex-direction: column; gap: 16px; border-bottom: 3px solid {color}">
  <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px">
    <div style="display: flex; flex-direction: column; gap: 3px">
      <span style="font-weight: 800; font-size: 18px; letter-spacing: -.5px">{p["name"]}</span>
      <span class="muted" style="font-size: 12.5px">{p["age"]} tuổi · {p["gender"]} · giờ thứ {p["hour"]}</span>
    </div>
    {risk_badge(p["level"], p["risk"])}
  </div>
  <div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px">
    {vital("HR", str(p["hr"]), "bpm")}{vital("SPO₂", str(p["spo2"]), "%")}{vital("RR", str(p["rr"]), "/ph")}{vital("HA", p["bp"], "")}
  </div>
  <div style="display: flex; flex-direction: column; gap: 6px">
    <div style="display: flex; justify-content: space-between; font-size: 11px" class="mono"><span class="muted">RỦI RO 12 GIỜ QUA</span><span class="muted">bây giờ</span></div>
    <div style="display: flex; gap: 2px">{pad}{cells}</div>
  </div>
  <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
    {news2_chip(p["news2"])}{anomaly_chip(p["anomaly"])}
  </div>
  <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 12px; border-top: 1px solid {BORDER}">
    {open_html}<span class="mono muted" style="font-size: 11.5px">{p["ago"]}</span>
  </div>
</article>"""


def dashboard() -> str:
    counts = {lvl: sum(p["level"] == lvl for p in PATIENTS) for lvl in RISK}
    header = page_header(
        f"Bệnh nhân được phân công · {len(PATIENTS)}", "Theo dõi bệnh nhân",
        right=f'{realtime_indicator()}{segmented([("Tất cả", str(len(PATIENTS))), ("Nguy kịch", str(counts["CRITICAL"])), ("Cảnh báo", str(counts["WARNING"]))])}',
    )
    toolbar = (f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 16px">'
               f'<div class="input" style="width: 320px">{icon("search", 16, MUTED_FG)}<span class="muted">Tìm theo mã bệnh nhân</span></div>'
               f'<span class="muted" style="font-size: 13px">Sắp xếp: rủi ro dự báo cao nhất lên đầu</span></div>')
    cards = "".join(patient_card(p) for p in PATIENTS)
    grid = f'<section style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px">{cards}</section>'
    return document("Dashboard bệnh nhân", shell("NURSE", "Bệnh nhân", "ĐD. Lê Văn Cường", header + toolbar + grid, 900))


# ---------------------------------------------------------------------------------------- Chi tiết bệnh nhân
def series_data():
    """48 giờ dữ liệu (hour_index 18–65) của BN-10069: ổn định rồi xấu dần từ giờ ~50."""
    rng = random.Random(7)
    hours = list(range(18, 66))

    def trend(h, start, end, onset=50):
        if h < onset:
            return start
        return start + (end - start) * ((h - onset) / (65 - onset)) ** 1.3

    hr = [round(trend(h, 86, 128) + rng.gauss(0, 2.2)) for h in hours]
    spo2 = [round(min(99, trend(h, 97, 90) + rng.gauss(0, .6))) for h in hours]
    rr = [round(trend(h, 17, 27) + rng.gauss(0, 1)) for h in hours]
    sbp = [round(trend(h, 122, 92) + rng.gauss(0, 3)) for h in hours]
    dbp = [round(trend(h, 68, 51) + rng.gauss(0, 2)) for h in hours]
    temp = [round(trend(h, 37.2, 38.5) + rng.gauss(0, .08), 1) if h % 4 == 2 else None for h in hours]
    for gap_hour in (33, 34):  # giờ không đo HR/SpO2: để trống, không nội suy
        idx = hours.index(gap_hour)
        hr[idx] = spo2[idx] = None
    level = ["NORMAL" if h < 51 else "WARNING" if h < 58 else "CRITICAL" for h in hours]
    level[hours.index(44)] = "WARNING"
    anomaly = [rng.uniform(.05, .6) if h < 40 else rng.uniform(.1, .85) for h in hours if h < 56]
    anomaly += [.93, .95, .972, .985, .991, .994, .989, .993, .995, .997]  # giờ 56–65, khớp thẻ 0,997 và cảnh báo giờ 64
    # Giá trị giờ cuối khớp thẻ bệnh nhân trên Dashboard (HR 126, SpO2 90, RR 26, HA 94/52, nhiệt độ 38,4)
    hr[-1], spo2[-1], rr[-1], sbp[-1], dbp[-1] = 126, 90, 26, 94, 52
    temp[hours.index(62)] = 38.4
    return hours, dict(hr=hr, spo2=spo2, rr=rr, sbp=sbp, dbp=dbp, temp=temp), level, anomaly


def vitals_chart() -> str:
    hours, s, level, anomaly = series_data()
    left, plot_w, strip_h, gap = 132, 860, 64, 16
    n = len(hours)
    step = plot_w / (n - 1)
    x = lambda i: left + i * step  # noqa: E731
    strips = [
        ("Nhịp tim", "bpm", [("hr", SERIES, "")], 60, 140, (51, 90)),
        ("SpO₂", "%", [("spo2", SERIES, "")], 86, 100, (96, 100)),
        ("Nhịp thở", "/phút", [("rr", SERIES, "")], 10, 32, (12, 20)),
        ("Huyết áp", "mmHg", [("sbp", SERIES, ""), ("dbp", SERIES_2, "5 4")], 40, 140, (111, 140)),
        ("Nhiệt độ", "°C", [("temp", SERIES, "")], 36, 39.5, (36.1, 38.0)),
    ]
    cross_i = hours.index(63)
    flagged = [i for i, a in enumerate(anomaly) if a >= .99]
    parts, y0 = [], 8
    for name, unit, lines, lo, hi, band in strips:
        top, bottom = y0, y0 + strip_h
        y = lambda v, lo=lo, hi=hi, top=top: top + (hi - v) / (hi - lo) * strip_h  # noqa: E731
        b_top, b_bot = y(min(band[1], hi)), y(max(band[0], lo))
        parts.append(f'<rect x="{left}" y="{b_top:.1f}" width="{plot_w}" height="{b_bot - b_top:.1f}" fill="#ffffff" fill-opacity=".045"></rect>')
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{bottom}" y2="{bottom}" stroke="{GRID}" stroke-width="1"></line>')
        for i in flagged:
            parts.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{top}" y2="{bottom}" stroke="{ANOMALY}" stroke-opacity=".35" stroke-width="1.5"></line>')
        first_key = lines[0][0]
        current = next(v for v in reversed(s[first_key]) if v is not None)  # giá trị đo gần nhất
        value_text = (f"{s['sbp'][-1]}/{s['dbp'][-1]}" if first_key == "sbp" else
                      vn(current, 1) if first_key == "temp" else str(current))
        parts.append(f'<text x="0" y="{top + 14}" fill="{MUTED_FG}" font-family="JetBrains Mono, monospace" font-size="11" letter-spacing="1">{name.upper()}</text>')
        parts.append(f'<text x="0" y="{top + 38}" fill="{FG}" font-family="JetBrains Mono, monospace" font-size="20" font-weight="600">{value_text}</text>')
        parts.append(f'<text x="0" y="{top + 54}" fill="{MUTED_FG}" font-family="JetBrains Mono, monospace" font-size="11">{unit}</text>')
        for tick in (lo, hi):
            label = vn(tick, 1) if isinstance(tick, float) and tick % 1 else str(int(tick))
            parts.append(f'<text x="{left - 8}" y="{y(tick) + 4:.1f}" fill="#6f7178" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="end">{label}</text>')
        for key, color, dash in lines:
            values = s[key]
            sparse = key == "temp"
            d, pen = [], False
            for i, v in enumerate(values):
                if v is None:
                    pen = pen and sparse
                    continue
                d.append(f'{"L" if pen else "M"}{x(i):.1f},{y(v):.1f}')
                pen = True
            dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
            parts.append(f'<path d="{" ".join(d)}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"{dash_attr}></path>')
            if sparse:
                for i, v in enumerate(values):
                    if v is not None:
                        parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="{color}" stroke="{CARD}" stroke-width="2"></circle>')
        if first_key == "sbp":
            parts.append(f'<text x="{left + plot_w + 8}" y="{y(s["sbp"][-1]) + 4:.1f}" fill="{MUTED_FG}" font-size="11">Tâm thu</text>')
            parts.append(f'<text x="{left + plot_w + 8}" y="{y(s["dbp"][-1]) + 4:.1f}" fill="{MUTED_FG}" font-size="11">Tâm trương</text>')
        y0 = bottom + gap

    # Làn điểm bất thường (0–1) với ngưỡng τ_anomaly = 0,99
    a_top, a_h = y0 + 6, 44
    parts.append(f'<text x="0" y="{a_top + 14}" fill="{MUTED_FG}" font-family="JetBrains Mono, monospace" font-size="11" letter-spacing="1">BẤT THƯỜNG</text>')
    parts.append(f'<text x="0" y="{a_top + 36}" fill="{FG}" font-family="JetBrains Mono, monospace" font-size="18" font-weight="600">{vn(anomaly[-1], 3)}</text>')
    bar_w = step - 3
    for i, a in enumerate(anomaly):
        h_bar = a * a_h
        color = ANOMALY if a >= .99 else "#4a4b52"
        parts.append(f'<rect x="{x(i) - bar_w / 2:.1f}" y="{a_top + a_h - h_bar:.1f}" width="{bar_w:.1f}" height="{h_bar:.1f}" rx="1.5" fill="{color}"></rect>')
    t_y = a_top + a_h - .99 * a_h
    parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{t_y:.1f}" y2="{t_y:.1f}" stroke="{ANOMALY}" stroke-dasharray="3 3" stroke-width="1"></line>')
    parts.append(f'<text x="{left + plot_w + 8}" y="{t_y + 4:.1f}" fill="{MUTED_FG}" font-size="11">τ 0,99</text>')
    y0 = a_top + a_h + 18

    # Risk-timeline: mức rủi ro dự báo mỗi giờ
    parts.append(f'<text x="0" y="{y0 + 13}" fill="{MUTED_FG}" font-family="JetBrains Mono, monospace" font-size="11" letter-spacing="1">RỦI RO 4 GIỜ TỚI</text>')
    for i, lvl in enumerate(level):
        parts.append(f'<rect x="{x(i) - step / 2 + 1:.1f}" y="{y0}" width="{step - 2:.1f}" height="18" rx="2" fill="{RISK[lvl][0]}" fill-opacity=".8"></rect>')
    y0 += 30

    # Trục x (giờ dữ liệu) + crosshair tại giờ 63
    for h in (18, 24, 30, 36, 42, 48, 54, 60, 65):
        i = hours.index(h)
        parts.append(f'<text x="{x(i):.1f}" y="{y0 + 8}" fill="#6f7178" font-family="JetBrains Mono, monospace" font-size="10.5" text-anchor="middle">{h}</text>')
    parts.append(f'<text x="{left + plot_w}" y="{y0 + 26}" fill="{MUTED_FG}" font-size="11" text-anchor="end">giờ dữ liệu kể từ khi vào ICU</text>')
    cx = x(cross_i)
    parts.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="4" y2="{y0 - 12}" stroke="{FG}" stroke-opacity=".55" stroke-width="1"></line>')
    total_h = y0 + 34
    svg = (f'<svg width="{left + plot_w + 80}" height="{total_h}" viewBox="0 0 {left + plot_w + 80} {total_h}" '
           f'font-family="Be Vietnam Pro, Segoe UI, sans-serif" role="img" aria-label="Biểu đồ vitals 48 giờ gần nhất">'
           f'{"".join(parts)}</svg>')

    def row(label, value):
        return (f'<div style="display: flex; justify-content: space-between; gap: 18px"><span class="muted">{label}</span>'
                f'<span class="mono" style="font-weight: 600">{value}</span></div>')

    hr_text, spo2_text = str(s["hr"][cross_i]) + " bpm", str(s["spo2"][cross_i]) + " %"
    rr_text, bp_text = str(s["rr"][cross_i]) + " /phút", str(s["sbp"][cross_i]) + "/" + str(s["dbp"][cross_i])
    tooltip = (f'<div style="position: absolute; left: {cx - 250:.0f}px; top: 36px; width: 214px; padding: 12px 14px; '
               f'border-radius: var(--radius-xl); background: {POPOVER}; border: 1px solid {BORDER}; '
               f'box-shadow: 0 12px 32px rgba(0, 0, 0, .45); display: flex; flex-direction: column; gap: 6px; font-size: 12.5px">'
               f'<span class="mono muted" style="font-size: 11px">GIỜ 63 · 05:31:25</span>'
               f'{row("Nhịp tim", hr_text)}{row("SpO₂", spo2_text)}{row("Nhịp thở", rr_text)}{row("Huyết áp", bp_text)}'
               f'<div style="height: 1px; background: {BORDER}; margin: 2px 0"></div>'
               f'<div style="display: flex; justify-content: space-between; align-items: center">{risk_badge("CRITICAL", 0.68)}</div>'
               f'{row("NEWS2", "9")}{row("Bất thường", vn(anomaly[cross_i], 3))}</div>')
    return f'<div style="position: relative">{svg}{tooltip}</div>'


def news2_breakdown() -> str:
    items = [("Nhịp thở", 3), ("SpO₂", 3), ("Huyết áp tâm thu", 1), ("Nhịp tim", 2), ("Nhiệt độ", 0)]
    rows = "".join(
        f'<div style="display: flex; align-items: center; gap: 10px"><span style="flex-grow: 1" class="muted">{label}</span>'
        f'<div style="display: flex; gap: 3px">'
        + "".join(f'<span style="width: 14px; height: 8px; border-radius: 2px; background: {FG if k < pts else SECONDARY}; opacity: {.85 if k < pts else 1}"></span>' for k in range(3))
        + f'</div><span class="mono" style="width: 14px; text-align: right; font-weight: 600">{pts}</span></div>'
        for label, pts in items)
    return rows


def detail_alert(kind: str, status: str, hour: int, time: str, detail: str, actions: str = "") -> str:
    return f"""
<div style="display: flex; flex-direction: column; gap: 10px; padding: 14px; border-radius: var(--radius-xl); border: 1px solid {BORDER}; background: {BG}">
  <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">{alert_type(kind)}{status_pill(status)}</div>
  <span class="muted" style="font-size: 12.5px">Giờ thứ {hour} · {time} · {detail}</span>
  {actions}
</div>"""


def patient_detail() -> str:
    back = (f'<div style="display: flex; align-items: center; gap: 6px; color: {MUTED_FG}; font-size: 13px; font-weight: 600">'
            f'{icon("chevron-left", 16)}Danh sách bệnh nhân</div>')
    hero = f"""
<section style="display: grid; grid-template-columns: 1.35fr 1fr 1fr; gap: 16px">
  <div class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 14px; border-bottom: 3px solid {RISK['CRITICAL'][0]};
    box-shadow: 0 0 0 1px {rgba(RISK['CRITICAL'][0], .25)}, 0 0 32px {rgba(RISK['CRITICAL'][0], .12)}">
    <span class="eyebrow">Rủi ro dự báo 4 giờ tới</span>
    <div style="display: flex; align-items: center; gap: 14px">{risk_badge("CRITICAL", large=True)}
      <span class="mono" style="font-size: 36px; font-weight: 600; letter-spacing: -1.5px">72<span style="font-size: 18px; color: {MUTED_FG}">%</span></span></div>
    <span class="muted" style="font-size: 12.5px">Xác suất nguy kịch trong 4 giờ tới · ngưỡng τ_critical 0,22 (model champion v2)</span>
  </div>
  <div class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 12px">
    <div style="display: flex; align-items: baseline; justify-content: space-between"><span class="eyebrow">NEWS2 hiện tại</span>
      <span class="mono" style="font-size: 30px; font-weight: 600; letter-spacing: -1px">9<span style="font-size: 14px; color: {MUTED_FG}"> /15</span></span></div>
    <div style="display: flex; flex-direction: column; gap: 6px; font-size: 12.5px">{news2_breakdown()}</div>
  </div>
  <div class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 12px">
    <span class="eyebrow">Diễn biến bất thường</span>
    <div>{anomaly_chip(0.997)}</div>
    <span class="muted" style="font-size: 12.5px; text-wrap: pretty">Hình dạng 12 giờ gần nhất lệch khỏi mẫu bình thường: lỗi tái tạo lớn hơn 99,7% cửa sổ bình thường. Ngưỡng gắn cờ 0,99.</span>
  </div>
</section>"""
    doctor_actions = (f'<div style="display: flex; gap: 8px"><div class="btn btn-primary">{icon("tick", 16, PRIMARY_FG, 2.2)}Xác nhận</div>'
                      f'<div class="btn btn-outline">Mở vitals giờ 64</div></div>')
    resolve_actions = f"""
<div style="display: flex; flex-direction: column; gap: 8px">
  <div class="input focus" style="height: auto; min-height: 60px; align-items: flex-start; padding: 10px 12px; font-size: 13px">Đã báo bác sĩ trực, tăng oxy qua mask, theo dõi mỗi 30 phút</div>
  <div style="display: flex; gap: 8px"><div class="btn btn-primary">Đã xử lý</div><div class="btn btn-ghost">Hủy</div></div>
</div>"""
    alerts = (detail_alert("ANOMALY", "OPEN", 64, "05:31:30", "điểm bất thường 0,995", doctor_actions)
              + detail_alert("RISK", "ACKNOWLEDGED", 58, "05:31:00", "NEWS2 8 · xác suất 0,61 · BS. Trần Thị Bình đã xác nhận", resolve_actions)
              + detail_alert("RISK", "RESOLVED", 31, "05:28:35", "“Đã xử trí, huyết động ổn định lại” — BS. Trần Thị Bình"))
    body = f"""
{back}
{page_header("Chi tiết bệnh nhân · MIMIC 10069 · đợt ICU 202115", "BN-10069", right=realtime_indicator(), sub="76 tuổi · Nữ · theo dõi từ 05:26 · giờ dữ liệu thứ 65")}
{hero}
<section style="display: flex; flex-direction: column; gap: 16px">
  <div class="card" style="padding: 20px 20px 12px; display: flex; flex-direction: column; gap: 14px">
    <div style="display: flex; align-items: center; justify-content: space-between">
      <h2>Vitals 48 giờ gần nhất</h2>
      <div style="display: flex; align-items: center; gap: 16px; font-size: 12px" class="muted">
        <span style="display: inline-flex; align-items: center; gap: 6px"><span style="width: 14px; height: 2px; background: {SERIES}"></span>Giá trị đo</span>
        <span style="display: inline-flex; align-items: center; gap: 6px"><span style="width: 14px; height: 8px; background: #ffffff; opacity: .12"></span>Vùng 0 điểm NEWS2</span>
        <span style="display: inline-flex; align-items: center; gap: 6px"><span style="width: 2px; height: 12px; background: {ANOMALY}"></span>Giờ bị gắn cờ bất thường</span>
        {segmented([("24 giờ", None), ("48 giờ", None), ("Cả đợt", None)], 1)}
      </div>
    </div>
    {vitals_chart()}
  </div>
  <div class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 12px">
    <div style="display: flex; align-items: center; justify-content: space-between"><h2>Cảnh báo của bệnh nhân</h2><span class="mono muted" style="font-size: 12px">3 cảnh báo · 1 đang mở</span></div>
    <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: start">{alerts}</div>
  </div>
</section>"""
    return document("Chi tiết bệnh nhân", shell("DOCTOR", "Bệnh nhân", "BS. Trần Thị Bình", body, 1300, open_alerts=2))


# ---------------------------------------------------------------------------------------- Trung tâm cảnh báo
ALERTS = [
    ("ANOMALY", "BN-10069", "OPEN", 64, "05:31:30", "0,995", "—", True),
    ("RISK", "BN-10074", "OPEN", 9, "05:31:25", "0,39", "7", True),
    ("RISK", "BN-10069", "ACKNOWLEDGED", 58, "05:31:00", "0,61", "8", False),
    ("RISK", "BN-10056", "OPEN", 17, "05:30:10", "0,27", "6", False),
    ("RISK", "BN-10032", "RESOLVED", 42, "05:29:05", "0,24", "7", False),
    ("ANOMALY", "BN-10032", "RESOLVED", 38, "05:28:45", "0,992", "—", False),
    ("RISK", "BN-10069", "RESOLVED", 31, "05:28:35", "0,33", "7", False),
]


def alerts_center() -> str:
    header = page_header("Cảnh báo của bệnh nhân được phân công", "Trung tâm cảnh báo", right=realtime_indicator())
    filters = (f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 16px">'
               f'{segmented([("Mở", "3"), ("Đã xác nhận", "1"), ("Đã xử lý", "3"), ("Tất cả", "7")], 3)}'
               f'{segmented([("Mọi loại", None), ("Rủi ro", None), ("Bất thường", None)], 0)}</div>')
    rows = []
    for kind, patient, status, hour, time, score, news2, new in ALERTS:
        highlight = f'background: {rgba(PRIMARY, .06)}' if new else ""
        new_tag = (f'<span class="mono" style="font-size: 10.5px; letter-spacing: 1px; padding: 2px 6px; border-radius: 4px; '
                   f'background: {PRIMARY}; color: {PRIMARY_FG}; font-weight: 600">MỚI</span>' if new else "")
        score_label = "Điểm bất thường" if kind == "ANOMALY" else "Xác suất nguy kịch"
        if status == "OPEN":
            action = f'<div class="btn btn-primary" style="height: 32px">{icon("tick", 15, PRIMARY_FG, 2.2)}Xác nhận</div>'
        elif status == "ACKNOWLEDGED":
            action = '<div class="btn btn-outline" style="height: 32px">Đã xử lý…</div>'
        else:
            action = '<span class="muted" style="font-size: 12.5px">BS. Trần Thị Bình</span>'
        rows.append(f"""
<tr style="{highlight}">
  <td><div style="display: flex; align-items: center; gap: 10px">{alert_type(kind)}{new_tag}</div></td>
  <td><span style="font-weight: 700">{patient}</span></td>
  <td><span class="mono">{time}</span><span class="muted" style="font-size: 12px"> · giờ {hour}</span></td>
  <td><span class="mono" style="font-weight: 600">{news2}</span></td>
  <td><div style="display: flex; flex-direction: column"><span class="mono" style="font-weight: 600">{score}</span><span class="muted" style="font-size: 11.5px">{score_label}</span></div></td>
  <td>{status_pill(status)}</td>
  <td style="text-align: right">{action}</td>
</tr>""")
    table = (f'<section class="card" style="overflow: hidden"><table><thead><tr><th>Loại</th><th>Bệnh nhân</th><th>Thời điểm</th>'
             f'<th>NEWS2</th><th>Điểm</th><th>Trạng thái</th><th style="text-align: right">Thao tác</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></section>')
    return document("Trung tâm cảnh báo", shell("DOCTOR", "Cảnh báo", "BS. Trần Thị Bình", header + filters + table, 900, open_alerts=3))


# ------------------------------------------------------------------------------------------------ Quản trị
def admin_tabs(active: str) -> str:
    tabs = ["Người dùng", "Phân công", "Ngưỡng cảnh báo", "Giám sát mô hình"]
    return (f'<div style="display: flex; gap: 4px; border-bottom: 1px solid {BORDER}">'
            + "".join(f'<div style="padding: 10px 14px; font-weight: 600; font-size: 13.5px; '
                      f'color: {FG if t == active else MUTED_FG}; border-bottom: 2px solid {PRIMARY if t == active else "transparent"}; '
                      f'margin-bottom: -1px">{t}</div>' for t in tabs) + '</div>')


def role_pill(role: str) -> str:
    label = {"ADMIN": "Quản trị viên", "DOCTOR": "Bác sĩ", "NURSE": "Điều dưỡng"}[role]
    return (f'<span class="chip" style="height: 24px; font-size: 12px">{label}</span>')


def switch(on: bool) -> str:
    return (f'<span style="display: inline-flex; width: 36px; height: 20px; border-radius: 999px; padding: 2px; '
            f'background: {PRIMARY if on else INPUT}; justify-content: {"flex-end" if on else "flex-start"}">'
            f'<span style="width: 16px; height: 16px; border-radius: 50%; background: {PRIMARY_FG if on else MUTED_FG}"></span></span>')


def admin_users() -> str:
    users = [("Quản trị viên", "admin@rpm.local", "ADMIN", True, "—"),
             ("BS. Nguyễn Văn An", "bs.an@rpm.local", "DOCTOR", True, "10"),
             ("BS. Trần Thị Bình", "bs.binh@rpm.local", "DOCTOR", True, "10"),
             ("ĐD. Lê Văn Cường", "dd.cuong@rpm.local", "NURSE", True, "20"),
             ("ĐD. Phạm Thu Dung", "dd.dung@rpm.local", "NURSE", False, "0")]
    rows = "".join(
        f'<tr><td><span style="font-weight: 600">{n}</span></td><td><span class="mono" style="font-size: 13px">{e}</span></td>'
        f'<td>{role_pill(r)}</td><td><div style="display: flex; align-items: center; gap: 10px">{switch(a)}'
        f'<span class="{"" if a else "muted"}" style="font-size: 13px">{"Hoạt động" if a else "Đã khóa"}</span></div></td>'
        f'<td><span class="mono">{c}</span></td>'
        f'<td style="text-align: right"><div class="btn btn-ghost" style="height: 32px">{icon("pencil", 15)}Sửa</div></td></tr>'
        for n, e, r, a, c in users)
    header = page_header("Quản trị hệ thống", "Người dùng", right=f'<div class="btn btn-primary">{icon("plus", 16, PRIMARY_FG, 2.2)}Thêm tài khoản</div>')
    table = (f'<section class="card" style="overflow: hidden"><table><thead><tr><th>Họ tên</th><th>Email</th><th>Vai trò</th>'
             f'<th>Trạng thái</th><th>Bệnh nhân phụ trách</th><th></th></tr></thead><tbody>{rows}</tbody></table></section>')
    note = '<p class="muted" style="margin: 0; font-size: 12.5px">Không xóa cứng tài khoản: khóa để giữ lịch sử xác nhận/xử lý cảnh báo. Không thể tự khóa hoặc tự bỏ quyền Quản trị của chính mình.</p>'
    return document("Quản trị · Người dùng", shell("ADMIN", "Người dùng", "Quản trị viên", header + admin_tabs("Người dùng") + table + note, 900))


def admin_assignments() -> str:
    patients = [("BN-10032", 2, False), ("BN-10035", 2, False), ("BN-10056", 2, False), ("BN-10069", 2, True),
                ("BN-10074", 1, False), ("BN-10090", 0, False), ("BN-10093", 2, False), ("BN-10094", 2, False),
                ("BN-10111", 1, False), ("BN-10112", 2, False)]
    items = "".join(
        f'<div style="display: flex; align-items: center; justify-content: space-between; height: 44px; padding: 0 12px; '
        f'border-radius: var(--radius-lg); background: {ACCENT if sel else "transparent"}">'
        f'<span style="font-weight: {700 if sel else 500}; color: {ACCENT_FG if sel else FG}">{name}</span>'
        f'<span class="mono" style="font-size: 12px; color: {RISK["WARNING"][0] if cnt == 0 else MUTED_FG}">'
        f'{"chưa có người phụ trách" if cnt == 0 else str(cnt) + " người"}</span></div>'
        for name, cnt, sel in patients)
    staff = [("BS. Trần Thị Bình", "bs.binh@rpm.local", "DOCTOR", "10/09 12:28"), ("ĐD. Lê Văn Cường", "dd.cuong@rpm.local", "NURSE", "10/09 12:28")]
    staff_rows = "".join(
        f'<div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: var(--radius-xl); border: 1px solid {BORDER}; background: {BG}">'
        f'<div style="width: 34px; height: 34px; border-radius: 50%; background: {SECONDARY}; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px">'
        f'{"".join(w[0] for w in n.replace(".", "").split()[-2:]).upper()}</div>'
        f'<div style="display: flex; flex-direction: column; line-height: 1.3"><span style="font-weight: 600">{n}</span>'
        f'<span class="mono muted" style="font-size: 12px">{e}</span></div>{role_pill(r)}'
        f'<span class="mono muted" style="margin-left: auto; font-size: 12px">phân công {t}</span>'
        f'<div class="btn btn-ghost" style="height: 32px">{icon("x", 15)}Gỡ</div></div>'
        for n, e, r, t in staff)
    body = f"""
{page_header("Quản trị hệ thống · UC13", "Phân công", sub="Bác sĩ và Điều dưỡng chỉ xem và nhận cảnh báo của bệnh nhân được phân công. Một bệnh nhân có thể có nhiều người phụ trách.")}
{admin_tabs("Phân công")}
<section style="display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 16px; align-items: start">
  <div class="card" style="padding: 12px; display: flex; flex-direction: column; gap: 4px">
    <div class="input" style="margin-bottom: 8px">{icon("search", 16, MUTED_FG)}<span class="muted">Tìm bệnh nhân</span></div>
    {items}
  </div>
  <div class="card" style="padding: 22px; display: flex; flex-direction: column; gap: 18px">
    <div style="display: flex; align-items: flex-start; justify-content: space-between">
      <div style="display: flex; flex-direction: column; gap: 4px"><h2 style="font-size: 22px; font-weight: 800">BN-10069</h2>
        <span class="muted" style="font-size: 13px">76 tuổi · Nữ · MIMIC 10069 · đợt ICU 202115</span></div>
      {risk_badge("CRITICAL", 0.72)}
    </div>
    <div style="display: flex; flex-direction: column; gap: 10px"><span class="eyebrow">Đang phụ trách</span>{staff_rows}</div>
    <div style="display: flex; flex-direction: column; gap: 10px; padding-top: 16px; border-top: 1px solid {BORDER}">
      <span class="eyebrow">Thêm người phụ trách</span>
      <div style="display: flex; gap: 10px">
        <div class="input focus" style="flex-grow: 1; justify-content: space-between"><span>BS. Nguyễn Văn An · Bác sĩ</span>{icon("chevron-down", 16, MUTED_FG)}</div>
        <div class="btn btn-primary" style="height: 38px">{icon("plus", 16, PRIMARY_FG, 2.2)}Phân công</div>
      </div>
      <span class="muted" style="font-size: 12.5px">Danh sách chỉ gồm tài khoản Bác sĩ / Điều dưỡng đang hoạt động.</span>
    </div>
  </div>
</section>"""
    return document("Quản trị · Phân công", shell("ADMIN", "Phân công", "Quản trị viên", body, 900))


def admin_thresholds() -> str:
    def field(label: str, hint: str, control: str) -> str:
        return (f'<div style="display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 24px; padding: 20px 0; border-bottom: 1px solid {BORDER}">'
                f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 700">{label}</span>'
                f'<span class="muted" style="font-size: 12.5px; text-wrap: pretty">{hint}</span></div>{control}</div>')

    tau_control = f"""
<div style="display: flex; flex-direction: column; gap: 10px">
  <div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: var(--radius-lg); border: 1px solid {PRIMARY}; background: {rgba(PRIMARY, .06)}">
    <span style="width: 16px; height: 16px; border-radius: 50%; border: 5px solid {PRIMARY}"></span>
    <span style="font-weight: 600">Dùng ngưỡng khuyến nghị của model champion</span><span class="mono" style="margin-left: auto; font-weight: 600">0,22</span>
  </div>
  <div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: var(--radius-lg); border: 1px solid {BORDER}">
    <span style="width: 16px; height: 16px; border-radius: 50%; border: 1.5px solid {INPUT}"></span>
    <span>Tự đặt ngưỡng</span><div class="input" style="margin-left: auto; width: 110px; height: 32px; opacity: .5"><span class="mono">0,30</span></div>
  </div>
</div>"""
    anomaly_control = (f'<div style="display: flex; align-items: center; gap: 12px"><div class="input" style="width: 140px">'
                       f'<span class="mono">0,99</span></div><span class="muted" style="font-size: 12.5px">≈ 1% cửa sổ bình thường bị gắn cờ nhầm</span></div>')
    cooldown_control = (f'<div style="display: flex; align-items: center; gap: 12px"><div class="input" style="width: 140px">'
                        f'<span class="mono">4</span><span class="muted" style="margin-left: auto">giờ</span></div>'
                        f'<span class="muted" style="font-size: 12.5px">tính theo giờ dữ liệu, không phải giờ đồng hồ</span></div>')
    history = [("11/09 12:28", "Hệ thống (giá trị mặc định)", "champion 0,22 · 0,99 · 4 giờ")]
    history_rows = "".join(f'<div style="display: flex; gap: 16px; font-size: 13px"><span class="mono muted">{t}</span><span>{w}</span>'
                           f'<span class="mono muted" style="margin-left: auto">{v}</span></div>' for t, w, v in history)
    body = f"""
{page_header("Quản trị hệ thống · UC08", "Ngưỡng cảnh báo", right='<div class="btn btn-outline">Hủy</div><div class="btn btn-primary">Lưu thay đổi</div>')}
{admin_tabs("Ngưỡng cảnh báo")}
<section class="card" style="padding: 4px 24px">
  {field("Ngưỡng rủi ro nguy kịch (τ_critical)", "Bệnh nhân được gắn mức Nguy kịch và tạo cảnh báo khi xác suất nguy kịch trong 4 giờ tới ≥ ngưỡng.", tau_control)}
  {field("Ngưỡng bất thường (τ_anomaly)", "Cảnh báo bất thường khi điểm bất thường ≥ ngưỡng (0–1).", anomaly_control)}
  <div style="display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 24px; padding: 20px 0">
    <div style="display: flex; flex-direction: column; gap: 4px"><span style="font-weight: 700">Thời gian chờ giữa 2 cảnh báo</span>
      <span class="muted" style="font-size: 12.5px; text-wrap: pretty">Cùng bệnh nhân, cùng loại: không tạo cảnh báo mới khi còn cảnh báo đang mở hoặc chưa hết thời gian chờ.</span></div>
    {cooldown_control}
  </div>
</section>
<section class="card" style="padding: 18px 24px; display: flex; flex-direction: column; gap: 10px">
  <span class="eyebrow">Lịch sử thay đổi</span>{history_rows}
  <span class="muted" style="font-size: 12.5px">Thay đổi có hiệu lực với stream consumer trong vòng 30 giây.</span>
</section>"""
    return document("Quản trị · Ngưỡng cảnh báo", shell("ADMIN", "Ngưỡng cảnh báo", "Quản trị viên", body, 900))


def drift_chart() -> str:
    rng = random.Random(3)
    psi = [round(rng.uniform(.02, .07), 3) for _ in range(18)] + [0.12, 0.31, 0.44, 0.47, 0.09, 0.05]
    left, width, top, height = 44, 1000, 14, 170
    n = len(psi)
    step = width / (n - 1)
    ymax = 0.5
    y = lambda v: top + (ymax - v) / ymax * height  # noqa: E731
    parts = []
    for tick in (0, 0.1, 0.25, 0.5):
        parts.append(f'<text x="{left - 8}" y="{y(tick) + 4:.1f}" fill="#6f7178" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="end">{vn(tick, 2)}</text>')
    parts.append(f'<line x1="{left}" x2="{left + width}" y1="{y(0)}" y2="{y(0)}" stroke="{AXIS}"></line>')
    for thr, label, color in ((0.1, "0,10 · lệch trung bình", RISK["WARNING"][0]), (0.25, "0,25 · lệch đáng kể → retrain", RISK["CRITICAL"][0])):
        parts.append(f'<line x1="{left}" x2="{left + width}" y1="{y(thr):.1f}" y2="{y(thr):.1f}" stroke="{color}" stroke-opacity=".7" stroke-dasharray="4 4"></line>')
        parts.append(f'<text x="{left + 8}" y="{y(thr) - 6:.1f}" fill="{MUTED_FG}" font-size="11">{label}</text>')
    d = " ".join(f'{"L" if i else "M"}{left + i * step:.1f},{y(v):.1f}' for i, v in enumerate(psi))
    parts.append(f'<path d="{d}" fill="none" stroke="{SERIES}" stroke-width="2" stroke-linejoin="round"></path>')
    for i, v in enumerate(psi):
        big = v >= .25
        parts.append(f'<circle cx="{left + i * step:.1f}" cy="{y(v):.1f}" r="{5 if big else 3.5}" fill="{RISK["CRITICAL"][0] if big else SERIES}" stroke="{CARD}" stroke-width="2"></circle>')
    first = psi.index(0.31)
    parts.append(f'<text x="{left + first * step - 10:.1f}" y="{y(0.31) - 10:.1f}" fill="{FG}" font-size="11.5" text-anchor="end" font-weight="600">Kích hoạt retrain tự động</text>')
    for i in range(0, n, 4):
        parts.append(f'<text x="{left + i * step:.1f}" y="{top + height + 18}" fill="#6f7178" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">{11 + i // 6:02d}:{(i * 10) % 60:02d}</text>')
    total = top + height + 30
    return (f'<svg width="{left + width + 12}" height="{total}" viewBox="0 0 {left + width + 12} {total}" '
            f'font-family="Be Vietnam Pro, Segoe UI, sans-serif" role="img" aria-label="Max PSI theo từng lần kiểm tra drift">{"".join(parts)}</svg>')


def admin_models() -> str:
    def metric(label: str, value: str, ref: str = "") -> str:
        ref_html = f'<span class="mono muted" style="font-size: 11.5px">{ref}</span>' if ref else ""
        return (f'<div style="display: flex; flex-direction: column; gap: 2px"><span class="mono muted" style="font-size: 10.5px; letter-spacing: 1.2px">{label}</span>'
                f'<span class="mono" style="font-size: 22px; font-weight: 600; letter-spacing: -.5px">{value}</span>{ref_html}</div>')

    champion_tag = (f'<span class="mono" style="font-size: 11px; letter-spacing: 1px; padding: 3px 8px; border-radius: 4px; '
                    f'background: {PRIMARY}; color: {PRIMARY_FG}; font-weight: 600">CHAMPION</span>')
    cards = f"""
<section style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px">
  <div class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 16px">
    <div style="display: flex; align-items: center; justify-content: space-between"><div style="display: flex; flex-direction: column; gap: 2px">
      <h2>Dự báo rủi ro 4 giờ tới</h2><span class="mono muted" style="font-size: 12px">risk_classifier v2 · Random Forest · τ 0,22</span></div>{champion_tag}</div>
    <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px">
      {metric("MACRO F1", "0,623", "persistence 0,547")}{metric("RECALL CRITICAL", "0,790", "persistence 0,308")}{metric("AUROC", "0,836")}
    </div>
  </div>
  <div class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 16px">
    <div style="display: flex; align-items: center; justify-content: space-between"><div style="display: flex; flex-direction: column; gap: 2px">
      <h2>Phát hiện bất thường</h2><span class="mono muted" style="font-size: 12px">anomaly_detector v3 · LSTM-Autoencoder · τ 0,99</span></div>{champion_tag}</div>
    <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px">
      {metric("AUROC", "0,864", "ngưỡng gate 0,75")}{metric("PRECISION", "0,727")}{metric("GẮN CỜ NHẦM", "0,7%")}
    </div>
  </div>
</section>"""
    versions = [("risk_classifier", "v2", "PROMOTED", "INITIAL", "Macro F1 0,623 · Recall 0,790", "Đạt gate", True),
                ("risk_classifier", "v1", "REJECTED", "INITIAL", "Macro F1 0,639 · Recall 0,730", "Recall CRITICAL 0,730 < 0,80", False),
                ("anomaly_detector", "v3", "PROMOTED", "MANUAL", "AUROC 0,864", "Đóng gói lại v2, điểm trùng khít", True),
                ("anomaly_detector", "v1", "REJECTED", "INITIAL", "AUROC 0,850", "Precision 0,226 < 0,70; Recall 0,146 < 0,70", False)]
    def gate_cell(gate: str) -> str:
        ico, label = (icon("check", 15, RISK["NORMAL"][0], 2), "Promoted") if gate == "PROMOTED" else (icon("x", 15, RISK["CRITICAL"][0], 2.2), "Từ chối")
        return f'<span style="display: inline-flex; align-items: center; gap: 6px; font-weight: 600">{ico}{label}</span>'

    rows = "".join(
        f'<tr><td><span class="mono" style="font-size: 13px">{m}</span></td><td><span class="mono" style="font-weight: 600">{v}</span></td>'
        f'<td>{gate_cell(g)}</td>'
        f'<td><span class="chip" style="height: 22px; font-size: 11.5px">{t}</span></td><td><span class="mono" style="font-size: 12.5px; white-space: nowrap">{met}</span></td>'
        f'<td><span class="muted" style="font-size: 12.5px">{reason}</span></td><td>{champion_tag if champ else ""}</td></tr>'
        for m, v, g, t, met, reason, champ in versions)
    table = (f'<section class="card" style="overflow: hidden"><table><thead><tr><th>Mô hình</th><th>Version</th><th>Quality gate</th>'
             f'<th>Kích hoạt</th><th>Metric trên test</th><th>Lý do</th><th></th></tr></thead><tbody>{rows}</tbody></table></section>')
    drift = f"""
<section class="card" style="padding: 20px; display: flex; flex-direction: column; gap: 12px">
  <div style="display: flex; align-items: center; justify-content: space-between"><div style="display: flex; flex-direction: column; gap: 2px">
    <h2>Drift dữ liệu</h2><span class="muted" style="font-size: 12.5px">Max PSI của 7 đặc trưng mỗi lần kiểm tra (24 giờ dữ liệu gần nhất) so với phân phối huấn luyện của champion</span></div>
    <div class="btn btn-outline" style="height: 32px">Xem PSI/KS từng đặc trưng</div></div>
  {drift_chart()}
</section>"""
    retrain = f"""
<div style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: var(--radius-xl); border: 1px solid {BORDER}; background: {CARD}">
  <span style="display: flex; animation: none">{icon("refresh", 16, PRIMARY, 2)}</span>
  <div style="display: flex; flex-direction: column; line-height: 1.3"><span style="font-weight: 600; font-size: 13px">Đang huấn luyện lại…</span>
    <span class="mono muted" style="font-size: 11.5px">manual__20260911T0535 · running · 2 phút</span></div>
</div>
<div class="btn btn-primary">{icon("refresh", 16, PRIMARY_FG, 2.2)}Kích hoạt huấn luyện lại</div>"""
    body = (page_header("Quản trị hệ thống · UC09 · UC10", "Giám sát mô hình", right=retrain) + admin_tabs("Giám sát mô hình")
            + cards + drift + table)
    return document("Quản trị · Giám sát mô hình", shell("ADMIN", "Giám sát mô hình", "Quản trị viên", body, 1100))


# ------------------------------------------------------------------------------------------ Thành phần
def kit() -> str:
    def group(title: str, content: str, note: str) -> str:
        return (f'<div class="card" style="padding: 22px; display: flex; flex-direction: column; gap: 14px">'
                f'<span class="eyebrow">{title}</span><div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">{content}</div>'
                f'<span class="muted" style="font-size: 12.5px; text-wrap: pretty">{note}</span></div>')

    body = f"""
<div style="width: {W}px; min-height: 900px; background: {BG}; padding: 40px 48px; display: flex; flex-direction: column; gap: 20px">
  {page_header("Design system · CS:GO dark + màu lâm sàng", "Thành phần giao diện")}
  <section style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px">
    {group("Rủi ro dự báo 4 giờ tới (model)", risk_badge("NORMAL", .04) + risk_badge("WARNING", .21) + risk_badge("CRITICAL", .72) + risk_badge("CRITICAL", large=True),
           "Badge chính của bệnh nhân. Luôn gồm icon + nhãn chữ + xác suất; nền là màu trạng thái 14%, chữ giữ màu foreground để đủ tương phản.")}
    {group("NEWS2 hiện tại (luật)", news2_chip(2) + news2_chip(9) + news2_chip(None),
           "Điểm lâm sàng tại thời điểm hiện tại, trình bày trung tính (không tô màu rủi ro) để không bị nhầm với dự báo của model.")}
    {group("Điểm bất thường (LSTM-Autoencoder)", anomaly_chip(0.195) + anomaly_chip(0.997) + anomaly_chip(None),
           "Màu tím riêng (--anomaly-flag), không trùng các màu rủi ro. 16 giờ đầu chưa có điểm (baseline 6 giờ + cửa sổ 12 giờ).")}
    {group("Trạng thái cảnh báo", status_pill("OPEN") + status_pill("ACKNOWLEDGED") + status_pill("RESOLVED") + alert_type("RISK") + alert_type("ANOMALY"),
           "Vòng đời Mở → Đã xác nhận → Đã xử lý. Loại cảnh báo luôn có icon riêng.")}
    {group("Nút", '<div class="btn btn-primary">Xác nhận</div><div class="btn btn-outline">Đã xử lý…</div><div class="btn btn-ghost">Hủy</div><div class="btn btn-primary focus">Focus</div>',
           "Một accent lime duy nhất cho hành động chính; focus-visible viền lime offset 3–5px.")}
    {group("Kết nối realtime", realtime_indicator(True) + realtime_indicator(False),
           "WebSocket mất kết nối thì hiển thị trạng thái đang kết nối lại, dữ liệu trên màn hình giữ nguyên cho tới khi có sự kiện mới.")}
  </section>
</div>"""
    return document("Thành phần giao diện", body)


# ------------------------------------------------------------------------------------------------ canvas
def main() -> None:
    boards = {
        "Login.dc.html": login(),
        "Main.dc.html": dashboard(),
        "PatientDetail.dc.html": patient_detail(),
        "AlertsCenter.dc.html": alerts_center(),
        "AdminUsers.dc.html": admin_users(),
        "AdminAssignments.dc.html": admin_assignments(),
        "AdminThresholds.dc.html": admin_thresholds(),
        "AdminModels.dc.html": admin_models(),
        "Components.dc.html": kit(),
    }
    for name, html in boards.items():
        (OUT / name).write_text(html, encoding="utf-8")

    gap_x, gap_y = 120, 200
    canvas = {
        "pages": [{"id": "page-1", "name": "Bác sĩ · Điều dưỡng"}, {"id": "page-2", "name": "Quản trị"},
                  {"id": "page-3", "name": "Thành phần"}],
        "artboards": [
            {"file": "Login.dc.html", "title": "Đăng nhập (UC01)", "x": 0, "y": 0, "w": W, "h": 900, "page": "page-1"},
            {"file": "Main.dc.html", "title": "Dashboard bệnh nhân (UC04) — Điều dưỡng", "x": W + gap_x, "y": 0, "w": W, "h": 900, "page": "page-1"},
            {"file": "PatientDetail.dc.html", "title": "Chi tiết bệnh nhân (UC05–07) — Bác sĩ", "x": 0, "y": 900 + gap_y, "w": W, "h": 1300, "page": "page-1"},
            {"file": "AlertsCenter.dc.html", "title": "Trung tâm cảnh báo (UC06–07) — Bác sĩ", "x": W + gap_x, "y": 900 + gap_y, "w": W, "h": 900, "page": "page-1"},
            {"file": "AdminUsers.dc.html", "title": "Người dùng (UC03)", "x": 0, "y": 0, "w": W, "h": 900, "page": "page-2"},
            {"file": "AdminAssignments.dc.html", "title": "Phân công (UC13)", "x": W + gap_x, "y": 0, "w": W, "h": 900, "page": "page-2"},
            {"file": "AdminThresholds.dc.html", "title": "Ngưỡng cảnh báo (UC08)", "x": 0, "y": 900 + gap_y, "w": W, "h": 900, "page": "page-2"},
            {"file": "AdminModels.dc.html", "title": "Giám sát mô hình (UC09–10)", "x": W + gap_x, "y": 900 + gap_y, "w": W, "h": 1100, "page": "page-2"},
            {"file": "Components.dc.html", "title": "Thành phần", "x": 0, "y": 0, "w": W, "h": 900, "page": "page-3"},
        ],
        "annotations": [
            {"id": "note-data", "x": 0, "y": -250, "w": 420, "page": "page-1",
             "text": "Mọi số liệu trên mockup là số liệu MẪU, cùng định dạng với API backend (Giai đoạn E). Bệnh nhân BN-xxxxx là mã MIMIC nhóm stream."},
            {"id": "note-badge", "x": W + gap_x, "y": -250, "w": 460, "page": "page-1",
             "text": "Phân tích: badge chính = RỦI RO DỰ BÁO 4 GIỜ TỚI (model), luôn có icon + nhãn + xác suất. NEWS2 hiện tại (luật) hiển thị riêng, màu trung tính, để hai khái niệm không bị gộp làm một.\n\nViền dưới 3px theo màu rủi ro = motif 'tier' của design system CS:GO. Dải 12 ô = rủi ro 12 giờ qua, giúp thấy xu hướng mà không cần mở chi tiết."},
            {"id": "note-chart", "x": W * 2 + gap_x + 60, "y": 900 + gap_y, "w": 420, "page": "page-1",
             "text": "Phân tích biểu đồ chi tiết (theo skill dataviz): 5 vitals có đơn vị khác nhau nên tách thành 5 dải xếp chồng dùng chung trục thời gian, KHÔNG dùng 2 trục y.\n\nVùng xám = khoảng 0 điểm NEWS2. Giờ không đo để trống (không nội suy, giống lúc train). Nhiệt độ đo 4 giờ/lần nên vẽ điểm. Vạch tím = giờ bị gắn cờ bất thường; làn 'Bất thường' là điểm 0–1 với ngưỡng 0,99; dải màu dưới cùng = rủi ro dự báo mỗi giờ.\n\nTooltip + crosshair minh họa trạng thái hover."},
            {"id": "note-alerts", "x": W * 2 + gap_x + 60, "y": 900 + gap_y + 700, "w": 420, "page": "page-1",
             "text": "Cảnh báo mới vào qua WebSocket: nền lime nhạt + tag MỚI trong vài giây rồi mờ dần (một chuyển động, không nhấp nháy liên tục).\n\nChỉ Bác sĩ có thao tác Xác nhận / Đã xử lý (kèm ghi chú). Điều dưỡng xem cùng danh sách nhưng không có cột Thao tác."},
            {"id": "note-admin", "x": 0, "y": -220, "w": 460, "page": "page-2",
             "text": "Admin không theo dõi bệnh nhân: sidebar chỉ có mục Quản trị, 4 tab ứng với UC03, UC13, UC08, UC09–10."},
            {"id": "note-drift", "x": W * 2 + gap_x + 60, "y": 900 + gap_y, "w": 420, "page": "page-2",
             "text": "Biểu đồ drift: đường max PSI mỗi lần chạy drift_check, 2 đường ngưỡng 0,10 / 0,25. Điểm vượt 0,25 tô đỏ = đã tự động kích hoạt retrain. Phần drift_check chưa hiện thực (Giai đoạn G) nên số liệu chỉ để minh họa.\n\nBảng version hiện đúng lịch sử thật: v1 bị từ chối kèm lý do gate."},
        ],
        "launch": {"view": "canvas", "page": "page-1"},
    }
    (OUT / "canvas.json").write_text(json.dumps(canvas, ensure_ascii=False, indent=2), encoding="utf-8")
    print("đã sinh", len(boards), "artboard vào", OUT)


if __name__ == "__main__":
    main()
