"""Общие функции для рисования схем в SVG (структурная схема, схема соединений)."""
from pathlib import Path
from xml.sax.saxutils import escape

C = {
    "i2s": "#1f63b0",      # цифровые сигналы I2S
    "ctrl": "#7a3fa0",     # управление, команды
    "pwr": "#c0392b",      # питание
    "ana": "#2e8b57",      # аналоговый звук
    "ac": "#8a8a8a",       # акустика
    "text": "#1d1d1f",
    "muted": "#5b6270",
}
FILL = {
    "user": "#f3f0f8", "esp": "#efe7f6", "board": "#f4f7fb", "fpga": "#e6eef8",
    "blk": "#ffffff", "hub": "#f6f4ee", "elem": "#eef6f0", "pwr": "#fbecea", "ana": "#eaf5ee",
}
FONT = "DejaVu Sans, Arial, Helvetica, sans-serif"
out = []


def text(x, y, s, size=13, weight="normal", color=None, anchor="middle", style=""):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
               f'fill="{color or C["text"]}" text-anchor="{anchor}" {style}>{escape(s)}</text>')


def box(x, y, w, h, title=None, lines=(), fill="#fff", stroke="#9aa3b0", rx=8, size=12.5,
        title_size=14, dash=None, title_color=None, lw=1.4):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="{lw}"{d}/>')
    n = len(lines) + (1 if title else 0)
    lh = size * 1.35
    cy = y + h / 2 - (n - 1) * lh / 2 + size * 0.35
    if title:
        text(x + w / 2, cy, title, title_size, "bold", title_color)
        cy += lh + (title_size - size) * 0.5
    for ln in lines:
        text(x + w / 2, cy, ln, size, color=C["muted"])
        cy += lh


def label(x, y, s, color, size=11.5, anchor="middle", bg=True):
    if bg:
        wdt = len(s) * size * 0.56 + 8
        x0 = x - wdt / 2 if anchor == "middle" else (x - 4 if anchor == "start" else x - wdt + 4)
        out.append(f'<rect x="{x0:.1f}" y="{y - size}" width="{wdt:.1f}" height="{size * 1.45:.1f}" '
                   f'rx="3" fill="#ffffff" opacity="0.92"/>')
    text(x, y, s, size, "bold", color, anchor)


def wire(pts, color, width=2.2, dash=None, arrow_end=True, arrow_start=False):
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
    key = [k for k, v in C.items() if v == color][0]
    m = (f' marker-end="url(#a_{key})"' if arrow_end else "") + \
        (f' marker-start="url(#s_{key})"' if arrow_start else "")
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"'
               f' stroke-linejoin="round"{ds}{m}/>')


def header(W, H):
    out.clear()
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}" font-family="{FONT}">')
    out.append("<defs>")
    for k, v in C.items():
        out.append(f'<marker id="a_{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                   f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{v}"/></marker>')
        out.append(f'<marker id="s_{k}" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" '
                   f'markerHeight="7" orient="auto"><path d="M10,0 L0,5 L10,10 z" fill="{v}"/></marker>')
    out.append("</defs>")
    out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')


def save(path, W=None, H=None):
    """Закрыть документ и записать SVG."""
    out.append("</svg>")
    Path(path).write_text("\n".join(out), encoding="utf-8")
    print("saved", path)
