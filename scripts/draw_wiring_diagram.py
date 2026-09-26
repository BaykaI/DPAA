"""Схема соединений установки (уровень плат, разъёмов и кабелей) -> docs/img/wiring.svg.

Запуск:  python scripts/draw_wiring_diagram.py
PNG для просмотра:  rsvg-convert -w 2400 docs/img/wiring.svg -o docs/img/wiring.png
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgdraw import C, FILL, box, header, label, out, save, text, wire  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "img" / "wiring.svg"
W, H = 1600, 1118

CONN = "#fdf6d8"  # заливка разъёмов


def conn(x, y, w, h, name, size=10.5):
    """Разъём: маленький прямоугольник на краю платы."""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{CONN}" '
               f'stroke="#8a7a3a" stroke-width="1.1"/>')
    text(x + w / 2, y + h / 2 + size * 0.36, name, size, "bold")


def tag(x, y, s, color, size=11):
    """Обозначение кабеля (W…) в рамке."""
    wdt = len(s) * size * 0.6 + 10
    out.append(f'<rect x="{x - wdt / 2:.1f}" y="{y - size - 1}" width="{wdt:.1f}" height="{size * 1.6:.1f}" '
               f'rx="3" fill="#ffffff" stroke="{color}" stroke-width="1"/>')
    text(x, y + 1, s, size, "bold", color)


def cable(pts, color, width=2.2, dash=None):
    """Кабель на схеме соединений — без стрелок (соединение, а не направление сигнала)."""
    wire(pts, color, width, dash=dash, arrow_end=False)


def draw():
    header(W, H)
    text(W / 2, 38, "Акустическая ЦАФАР: схема соединений", 24, "bold")
    text(W / 2, 62, "устройства, разъёмы и кабели · обозначения — по перечню ниже и в docs/hardware/wiring.md",
         13.5, color=C["muted"])

    # ---------------- питание и управление сверху слева ----------------
    box(40, 92, 260, 70, "G2  USB-зарядник 5 В 2 А", ["2 порта USB · при отладке",
        "вместо него — ноутбук"], FILL["pwr"], C["pwr"], size=11, title_size=13)
    box(580, 88, 250, 64, "A2  ESP32-S3 DevKitC-1", ["Wi‑Fi-пульт"], FILL["esp"], C["ctrl"],
        size=11, title_size=13)
    conn(600, 152, 70, 18, "гребёнка")
    conn(560, 109, 42, 22, "USB")
    box(1010, 92, 200, 56, "Планшет посетителя", ["браузер"], FILL["user"], C["ctrl"], size=11, title_size=12.5)
    cable([(1010, 120), (832, 120)], C["ctrl"], 1.8, dash="6 4")
    label(920, 112, "Wi‑Fi (радио)", C["ctrl"], 10.5)

    # ---------------- A1: плата ПЛИС ----------------
    box(40, 240, 250, 330, None, (), FILL["board"], "#6f7f95", rx=10, lw=1.8)
    text(165, 290, "A1  Плата ПЛИС", 15, "bold")
    text(165, 312, "Colorlight i9 (LFE5U-45F)", 12, color=C["muted"])
    text(165, 330, "+ плата расширения", 12, color=C["muted"])
    text(165, 348, "с отладчиком DAPLink", 12, color=C["muted"])
    conn(135, 228, 60, 22, "XS1 USB-C")
    for i in range(6):
        conn(262, 380 + i * 30, 56, 22, f"P{i + 1}")
    text(165, 395, "сдвоенные PMOD 2×6:", 11, color=C["muted"])
    text(165, 411, "8 сигналов + 2 GND", 11, color=C["muted"])
    text(165, 427, "+ 2 × 3.3 В (не подключать)", 11, color=C["muted"])

    # G2 -> A1, G2 -> A2
    cable([(165, 162), (165, 226)], C["ctrl"], 2.4)
    tag(165, 200, "W26 USB-C", C["ctrl"])
    cable([(300, 120), (558, 120)], C["ctrl"], 2.4)
    tag(430, 112, "W27 USB-C (питание A2)", C["ctrl"])

    # ---------------- A3: распределительная плата ----------------
    hx, hy, hw, hh = 520, 210, 380, 520
    box(hx, hy, hw, hh, None, (), FILL["hub"], "#9c8f6a", rx=12, lw=1.8)
    text(hx + hw / 2 - 20, 262, "A3  Распределительная плата", 15, "bold")
    conn(635, 199, 70, 22, "J25 ESP")
    conn(740, 199, 80, 22, "J28 UART")
    text(780, 237, "резерв: USB-UART", 9.5, color=C["muted"])
    for i in range(6):
        conn(502, 380 + i * 30, 56, 22, f"J{19 + i}")
    conn(502, 640, 56, 22, "J18 5 В")
    # внутреннее содержимое (для справки)
    box(575, 270, 200, 44, "буферы 74LVC244 ×9", [], "#ffffff", "#c9c1a8", size=11, title_size=11.5, dash="4 3")
    box(575, 322, 200, 44, "питание: Q1, D1, F1–F4", [], FILL["pwr"], "#e0a39b", size=11, title_size=11.5,
        dash="4 3")
    box(575, 374, 200, 44, "A4 ЦАП PCM5102A", [], FILL["ana"], "#9fd0b3", size=11, title_size=11.5, dash="4 3")
    box(575, 426, 200, 44, "A5 усилитель наушников", [], FILL["ana"], "#9fd0b3", size=11, title_size=11.5,
        dash="4 3")
    box(575, 478, 200, 44, "SW1 кнопка «тест»", [], "#ffffff", "#c9c1a8", size=11, title_size=11.5, dash="4 3")
    box(575, 530, 200, 44, "U10 стабилизатор 3.3 В", [], "#ffffff", "#c9c1a8", size=11, title_size=11.5,
        dash="4 3")

    # A1 P1..P6 -> A3 J19..J24
    for i in range(6):
        y = 391 + i * 30
        cable([(318, y), (500, y)], C["i2s"], 3.2)
    tag(409, 372, "W1–W6", C["i2s"])
    text(409, 578, "6 шлейфов 12 жил", 11, "bold", C["i2s"])
    text(409, 593, "(PMOD 2×6), 0.3 м", 11, color=C["i2s"])
    # A3 J25 -> A2
    cable([(670, 199), (670, 186), (635, 186), (635, 172)], C["ctrl"], 2.2)
    tag(708, 186, "W7", C["ctrl"])
    text(760, 190, "3 провода: TX, RX, GND", 10.5, color=C["ctrl"], anchor="start")

    # правый край A3: 16 разъёмов элементов + зонд + наушники
    ys = [236 + i * 24 for i in range(16)]
    for i, y in enumerate(ys):
        conn(872, y, 46, 19, f"J{i + 1}", 10)
    conn(872, 634, 60, 20, "J17 RJ45", 10)
    conn(872, 672, 60, 20, "J26 ⌀3.5", 10)
    conn(872, 700, 60, 20, "J27 ⌀3.5", 10)

    # ---------------- элементы A6…A21 ----------------
    ex, ew = 1060, 190
    for i, y in enumerate(ys):
        out.append(f'<rect x="{ex}" y="{y}" width="{ew}" height="19" rx="3" fill="{FILL["elem"]}" '
                   f'stroke="{C["ana"]}" stroke-width="1.1"/>')
        text(ex + 36, y + 14, f"A{6 + i}  элемент {i + 1}", 10.5, anchor="start")
        conn(ex - 2, y, 30, 19, "X1", 9.5)
        cable([(918, y + 9.5), (ex - 4, y + 9.5)], C["i2s"], 1.8)
    tag(990, 226, "W8–W23", C["i2s"])
    text(990, 204, "16 шлейфов IDC 2×5, 0.5 м", 10.5, "bold", C["i2s"])

    # зонд и наушники
    box(ex, 628, ew, 34, "A22  калибровочный зонд", [], FILL["blk"], "#9aa3b0", size=10.5, title_size=11.5)
    cable([(932, 644), (ex, 644)], C["i2s"], 2.2)
    tag(996, 644, "W24 CAT5 3 м", C["i2s"], 10)
    box(ex, 670, 92, 24, "BF1", [], FILL["ana"], C["ana"], size=10.5, title_size=11)
    box(ex + 98, 700, 92, 24, "BF2", [], FILL["ana"], C["ana"], size=10.5, title_size=11)
    cable([(932, 682), (ex, 682)], C["ana"], 2)
    cable([(932, 710), (ex + 98, 710)], C["ana"], 2)
    text(ex + ew / 2 + 48, 690, "наушники", 10.5, color=C["ana"], anchor="start")

    # ---------------- устройство элемента ----------------
    dx, dy, dw, dh = 1290, 210, 280, 400
    box(dx, dy, dw, dh, None, (), FILL["elem"], C["ana"], rx=10, lw=1.6)
    text(dx + dw / 2, dy + 24, "Элемент A6…A21 (одинаковые)", 13.5, "bold")
    text(dx + dw / 2, dy + 42, "в 3D-печатном держателе 40×40 мм", 11, color=C["muted"])
    box(dx + 18, dy + 60, dw - 36, 110, "A6.1  Плата усилителя", ["MAX98357A (ЦАП + класс D)",
        "LDO 3.3 В, 74LVC1G17 ×2"], "#ffffff", "#9aa3b0", size=10.5, title_size=12)
    conn(dx + 20, dy + 52, 90, 18, "X1 IDC 2×5", 9.5)
    conn(dx + 40, dy + 162, 64, 18, "X2 JST", 9.5)
    conn(dx + 176, dy + 162, 72, 18, "X3 5 конт.", 9.5)
    box(dx + 18, dy + 250, 110, 64, "BA1", ["динамик", "CE32A-8"], FILL["ana"], C["ana"], size=10.5,
        title_size=12)
    box(dx + 150, dy + 250, 112, 64, "A6.2", ["микроплата", "ICS-43434"], "#ffffff", "#9aa3b0", size=10.5,
        title_size=12)
    cable([(dx + 72, dy + 180), (dx + 72, dy + 248)], C["ana"], 2)
    text(dx + 78, dy + 222, "2 провода", 10, color=C["ana"], anchor="start")
    cable([(dx + 206, dy + 248), (dx + 206, dy + 180)], C["i2s"], 2)
    text(dx + 212, dy + 222, "5 проводов", 10, color=C["i2s"], anchor="start")
    text(dx + 212, dy + 236, "30 AWG", 10, color=C["i2s"], anchor="start")
    text(dx + dw / 2, dy + 342, "X1: 5 В, 5 В, GND, BCLK, GND,", 10.5, color=C["muted"])
    text(dx + dw / 2, dy + 358, "LRCLK, GND, TXD, GND, RXD", 10.5, color=C["muted"])
    text(dx + dw / 2, dy + 380, "X3: 3.3 В, GND, SCK, WS, SD", 10.5, color=C["muted"])
    cable([(ex + ew, 245), (dx, 245)], C["muted"], 1.2, dash="3 3")

    # ---------------- G1: блок питания ----------------
    box(300, 620, 170, 60, "G1  БП 5 В 6 А", ["закрытый, настольный"], FILL["pwr"], C["pwr"], size=11,
        title_size=13)
    cable([(470, 651), (500, 651)], C["pwr"], 2.8)
    tag(485, 700, "W25 DC 5.5/2.1", C["pwr"], 10)

    # ---------------- перечень кабелей ----------------
    ty = 770
    text(40, ty, "Перечень соединений", 15, "bold", anchor="start")
    cols = [(40, "Обозн."), (130, "Откуда"), (330, "Куда"), (560, "Тип"), (900, "Жил"), (960, "Длина"),
            (1050, "Сигналы")]
    rows = [
        ("W1–W6", "A1: P1–P6", "A3: J19–J24", "шлейф IDC 2×6 (PMOD)", "12", "0.3 м", "см. раскладку PMOD"),
        ("W7", "A3: J25", "A2: гребёнка", "провода Dupont", "3", "0.2 м", "UART TX, RX, GND"),
        ("W8–W23", "A3: J1–J16", "A6–A21: X1", "шлейф IDC 2×5", "10", "0.5 м", "5 В, GND, BCLK, LRCLK, TXD, RXD"),
        ("W24", "A3: J17", "A22: RJ45", "CAT5, RJ45 (T568B)", "8", "3 м", "BCLK, LRCLK, SD, 5 В, GND"),
        ("W25", "G1", "A3: J18", "шнур DC 5.5/2.1 мм", "2", "1.5 м", "+5 В, GND (до 5 А)"),
        ("W26", "G2 или ноутбук", "A1: XS1", "USB-C", "—", "1 м", "питание, JTAG, UART (DAPLink)"),
        ("W27", "G2", "A2: USB", "USB-C", "—", "1 м", "питание ESP32"),
        ("—", "A6.1: X2", "BA1", "провод 0.35 мм²", "2", "0.1 м", "выход усилителя"),
        ("—", "A6.1: X3", "A6.2", "провод 30 AWG", "5", "0.1 м", "3.3 В, GND, SCK, WS, SD"),
        ("—", "A3: J26, J27", "BF1, BF2", "штекер 3.5 мм", "3", "—", "левое ухо — луч 0, правое — луч 1"),
        ("(W28)", "A3: J28", "адаптер CP2102", "провода Dupont", "3", "0.2 м", "резерв: UART к ноутбуку"),
    ]
    rh = 25
    top = ty + 14
    out.append(f'<rect x="36" y="{top}" width="{W - 72}" height="{rh * (len(rows) + 1) + 6}" fill="#fafbfc" '
               f'stroke="#c8ced8" stroke-width="1"/>')
    for x, h in cols:
        text(x, top + 18, h, 12, "bold", anchor="start")
    for r, row in enumerate(rows):
        y = top + 18 + rh * (r + 1)
        out.append(f'<line x1="36" y1="{y - 17}" x2="{W - 36}" y2="{y - 17}" stroke="#e1e5eb" stroke-width="1"/>')
        for (x, _), v in zip(cols, row):
            text(x, y, v, 11.5, "bold" if x == 40 else "normal", anchor="start")

    save(OUT)


if __name__ == "__main__":
    draw()
