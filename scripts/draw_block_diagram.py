"""Структурная схема установки (SVG) -> docs/img/structure.svg.

Запуск:  python scripts/draw_block_diagram.py
PNG для просмотра:  rsvg-convert -w 2400 docs/img/structure.svg -o docs/img/structure.png
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[1] / "docs" / "img" / "structure.svg"
W, H = 1520, 1010

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


def header():
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


def draw():
    header()
    text(W / 2, 38, "Акустическая ЦАФАР: структурная схема установки", 24, "bold")
    text(W / 2, 62, "16 приёмопередающих элементов · ПЛИС Lattice ECP5 · шаг 40 мм · 1.5–4.3 кГц",
         14, color=C["muted"])

    # ---------------- операторы ----------------
    box(30, 110, 180, 80, "Планшет", ["посетителя: кнопки", "сценариев, «руль» луча"], FILL["user"])
    box(30, 600, 180, 96, "Ноутбук", ["отладка, dpaa_ctl.py,", "прошивка ПЛИС,", "моделирование"], FILL["user"])

    # ---------------- ESP32 ----------------
    box(250, 100, 180, 110, "ESP32-S3 DevKit", ["Wi‑Fi-точка доступа", "веб-пульт", "расчёт задержек и весов"],
        FILL["esp"], C["ctrl"])
    wire([(210, 150), (250, 150)], C["ctrl"], dash="6 4")
    label(230, 140, "Wi‑Fi", C["ctrl"])

    # ---------------- плата ПЛИС ----------------
    bx, by, bw, bh = 460, 90, 450, 720
    box(bx, by, bw, bh, None, (), FILL["board"], "#6f7f95", rx=12, lw=1.8)
    text(bx + bw / 2, by + 24, "Colorlight i9 + плата расширения", 15, "bold")
    fx, fy, fw, fh = 475, 125, 420, 585
    box(fx, fy, fw, fh, None, (), FILL["fpga"], C["i2s"], rx=10, lw=1.6)
    text(fx + fw / 2, fy + 22, "ПЛИС Lattice ECP5 LFE5U-45F · 50 МГц", 14, "bold", C["i2s"])

    L, R, bw2 = 490, 700, 180
    box(L, 160, bw2, 62, "UART-команды", ["регистры, commit"], size=12)
    box(R, 160, bw2, 62, "PLL", ["25 → 50 МГц"], size=12)
    box(L, 250, bw2, 72, "Генераторы ×2", ["синус · шум · ЛЧМ", "пачки · огибающая"], size=12)
    box(R, 250, bw2, 72, "ДОС передачи", ["2 луча → 16 каналов", "дробн. задержка + вес"], size=12)
    box(L, 350, bw2, 84, "Общий такт I2S", ["BCLK 3.125 МГц", "LRCLK 48 828 Гц", "для всех 33 каналов"],
        size=11.5)
    box(R, 424, bw2, 58, "I2S-передатчик", ["16 линий → усилители"], size=12)
    box(L, 512, bw2, 72, "ДОС приёма", ["16 микрофонов → 2 луча", "дробн. задержка + вес"], size=12)
    box(R, 512, bw2, 58, "I2S-приёмник", ["16 микрофонов + зонд"], size=12)
    box(L, 612, bw2, 58, "I2S монитора", ["луч 0 → Л, луч 1 → П"], size=12)
    box(R, 612, bw2, 58, "Измерители уровня", ["17 каналов, по UART"], size=12)
    box(560, 730, 250, 58, "DAPLink (плата расширения)", ["USB: JTAG-прошивка + UART"], FILL["blk"],
        C["ctrl"], size=12, title_size=13)

    # команды: UART -> генераторы, ДОС передачи, ДОС приёма
    wire([(580, 222), (580, 248)], C["ctrl"], 1.6)
    wire([(L + bw2, 206), (690, 206), (690, 272), (R, 272)], C["ctrl"], 1.6)
    wire([(L, 206), (482, 206), (482, 548), (L, 548)], C["ctrl"], 1.6)
    label(628, 238, "регистры", C["ctrl"], 10.5)
    # передача
    wire([(L + bw2, 300), (R, 300)], C["i2s"], 2.2)
    wire([(790, 322), (790, 422)], C["i2s"], 2.2)
    # общий такт -> все I2S-блоки
    wire([(L + bw2, 392), (692, 392), (692, 641)], C["i2s"], 1.4, arrow_end=False)
    for yy in (446, 527):
        wire([(692, yy), (R, yy)], C["i2s"], 1.4)
    wire([(692, 641), (L + bw2, 641)], C["i2s"], 1.4)
    # приём
    wire([(R, 556), (L + bw2, 556)], C["i2s"], 2.2)
    wire([(790, 570), (790, 610)], C["i2s"], 1.6)
    wire([(580, 584), (580, 610)], C["i2s"], 2.2)

    # связь с ESP32 и ноутбуком
    wire([(430, 155), (455, 155), (455, 191), (L, 191)], C["ctrl"], 2.2, arrow_start=True)
    label(420, 232, "UART 1 Мбод", C["ctrl"])
    wire([(210, 648), (380, 648), (380, 759), (560, 759)], C["ctrl"], 2.2, arrow_start=True)
    label(300, 638, "USB", C["ctrl"])
    wire([(685, 730), (685, 712)], C["ctrl"], 2.2, dash="5 3")
    label(760, 722, "JTAG + UART", C["ctrl"], 10.5)

    # ---------------- распределительная плата ----------------
    hx, hy, hw, hh = 955, 90, 200, 720
    box(hx, hy, hw, hh, None, (), FILL["hub"], "#9c8f6a", rx=12, lw=1.8)
    text(hx + hw / 2, hy + 24, "Распределительная", 15, "bold")
    text(hx + hw / 2, hy + 42, "плата", 15, "bold")
    HX, HW = 968, 174
    box(HX, 170, HW, 70, "Буферы тактов", ["74LVC244 ×4", "BCLK, LRCLK → 16 шлейфов"], size=11.5)
    box(HX, 258, HW, 56, "Буферы TXD", ["74LVC244 ×2, 33 Ом"], size=11.5)
    box(HX, 332, HW, 56, "Буферы RXD", ["74LVC244 ×2, 100 кОм↓"], size=11.5)
    box(HX, 406, HW, 56, "16 разъёмов IDC", ["2×5 к элементам"], size=11.5)
    box(HX, 480, HW, 70, "Питание 5 В", ["защита, TVS, 1000 мкФ", "PTC 1.5 А ×4 группы"], FILL["pwr"],
        C["pwr"], size=11.5)
    box(HX, 570, HW, 64, "ЦАП PCM5102A", ["→ усилитель наушников"], FILL["ana"], C["ana"], size=11.5)
    box(HX, 652, HW, 56, "Разъём зонда", ["RJ45 + буфер 74LVC244"], size=11.5)
    # буферы -> разъёмы (внутри платы)
    wire([(1149, 205), (1149, 430), (1142, 430)], C["i2s"], 1.6)
    wire([(1142, 205), (1149, 205)], C["i2s"], 1.6, arrow_end=False)
    wire([(1142, 286), (1149, 286)], C["i2s"], 1.6, arrow_end=False)
    wire([(1142, 360), (1149, 360)], C["i2s"], 1.6, arrow_end=False, arrow_start=True)
    wire([(1055, 480), (1055, 464)], C["pwr"], 2.4)

    # ПЛИС <-> распределительная плата (шлейфы PMOD)
    wire([(880, 453), (938, 453), (938, 205), (HX, 205)], C["i2s"], 3)
    wire([(938, 286), (HX, 286)], C["i2s"], 3)
    wire([(HX, 360), (924, 360), (924, 534), (880, 534)], C["i2s"], 3)
    wire([(HX, 680), (914, 680), (914, 560), (880, 560)], C["i2s"], 1.8)
    label(926, 150, "шлейфы PMOD", C["i2s"], 11)
    wire([(580, 670), (580, 700), (948, 700), (948, 598), (HX, 598)], C["i2s"], 2.2)
    label(862, 700, "MON", C["i2s"], 10)

    # ---------------- элементы ----------------
    ex, ew = 1200, 215
    box(ex, 100, ew, 250, None, (), FILL["elem"], C["ana"], rx=10, lw=1.6)
    text(ex + ew / 2, 124, "Элемент 1 («ППМ»)", 14, "bold")
    text(ex + ew / 2, 142, "3D-печатная плитка 40×40 мм", 11.5, color=C["muted"])
    box(ex + 12, 154, ew - 24, 78, "Плата усилителя", ["74LVC1G17 ×2, LDO 3.3 В", "MAX98357A: ЦАП + класс D"],
        size=11, title_size=12.5)
    box(ex + 12, 246, 88, 44, "Динамик", ["CE32A-8"], FILL["ana"], C["ana"], size=11, title_size=12)
    box(ex + 110, 246, ew - 122, 44, "Микрофон", ["ICS-43434"], size=11, title_size=12)
    text(ex + ew / 2, 312, "микрофон: АЦП 24 бит внутри", 11, color=C["muted"])
    text(ex + ew / 2, 330, "динамик: 2 Вт, 8 Ом", 11, color=C["muted"])
    wire([(ex + 56, 232), (ex + 56, 244)], C["ana"], 2)
    wire([(ex + 150, 246), (ex + 150, 234)], C["i2s"], 1.6)
    for i, yy in enumerate((362, 396, 430)):
        box(ex, yy, ew, 28, ["Элемент 2", "…  элементы 3–15  …", "Элемент 16"][i], [], FILL["elem"], C["ana"],
            size=11, title_size=12, rx=6)
    wire([(HX + HW, 434), (1178, 434)], C["i2s"], 3, arrow_end=False)
    wire([(1178, 444), (1178, 190), (ex, 190)], C["i2s"], 3)
    for yy in (376, 410, 444):
        wire([(1178, yy), (ex, yy)], C["i2s"], 1.8)
    text(ex + ew / 2, 476, "×16 шлейфов IDC 10 жил:", 11, "bold", C["i2s"])
    text(ex + ew / 2, 491, "5 В, GND, BCLK, LRCLK, TXD, RXD", 11, color=C["i2s"])

    # звуковое поле
    for r in (22, 40, 58):
        out.append(f'<path d="M {ex + ew + 8},{200 - r} A {r} {r * 1.6} 0 0 1 {ex + ew + 8},{200 + r}" '
                   f'fill="none" stroke="{C["ac"]}" stroke-width="2" opacity="{1 - r / 90:.2f}"/>')
    text(1470, 285, "луч", 12, "bold", C["ac"])
    text(1470, 300, "(слышат", 11, color=C["ac"])
    text(1470, 314, "зрители)", 11, color=C["ac"])

    # наушники и зонд
    box(ex, 566, ew, 64, "Наушники ×2", ["левое ухо — луч приёма 0", "правое ухо — луч приёма 1"],
        FILL["ana"], C["ana"], size=11, title_size=13)
    wire([(HX + HW, 598), (ex, 598)], C["ana"], 2.2)
    box(ex, 646, ew, 84, "Калибровочный зонд", ["ICS-43434 на стойке", "в 2–3 м от решётки", "кабель CAT5"],
        FILL["blk"], "#9aa3b0", size=11, title_size=13)
    wire([(HX + HW, 680), (ex, 680)], C["i2s"], 2.2, arrow_start=True)

    # ---------------- питание ----------------
    box(HX, 850, HW, 64, "БП 5 В 6 А", ["закрытый, настольный"], FILL["pwr"], C["pwr"], size=11.5)
    wire([(HX + HW, 882), (1150, 882), (1150, 515), (HX + HW, 515)], C["pwr"], 2.6)
    label(1055, 836, "до 5 А на 16 усилителей", C["pwr"], 10.5)
    box(560, 850, 250, 64, "USB-зарядник 5 В 2 А", ["плата ПЛИС и ESP32"], FILL["pwr"], C["pwr"], size=11.5)
    wire([(685, 850), (685, 812)], C["pwr"], 2.2)
    wire([(560, 882), (340, 882), (340, 212)], C["pwr"], 2.2)

    # ---------------- легенда ----------------
    lx, ly = 30, 760
    text(lx, ly, "Обозначения", 14, "bold", anchor="start")
    items = [("i2s", "цифровые сигналы I2S (3.3 В)", None), ("ctrl", "управление и прошивка", "6 4"),
             ("pwr", "питание 5 В", None), ("ana", "аналоговый звук", None), ("ac", "звуковое поле", None)]
    for i, (k, s, dash) in enumerate(items):
        y = ly + 24 + i * 24
        wire([(lx, y - 4), (lx + 44, y - 4)], C[k], 2.6, dash=dash)
        text(lx + 54, y, s, 12.5, anchor="start")
    text(lx, ly + 170, "ДОС — диаграммообразующая схема (цифровая)", 11.5, color=C["muted"], anchor="start")
    text(lx, ly + 188, "ППМ — приёмопередающий модуль", 11.5, color=C["muted"], anchor="start")
    text(lx, ly + 206, "Подробности: docs/hardware/", 11.5, color=C["muted"], anchor="start")

    out.append("</svg>")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print("saved", OUT)


if __name__ == "__main__":
    draw()
