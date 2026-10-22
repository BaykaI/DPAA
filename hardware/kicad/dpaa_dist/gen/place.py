# -*- coding: utf-8 -*-
"""Распределительная плата DPAA: компоновка и цепи (pcbnew API KiCad 10).
Все корпуса ставятся началом координат в узел сетки 0,635 мм (под трассировщик)."""
import os
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm

LIB = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
W, H = 100.0, 180.0
G = 0.635
F, B = pcbnew.F_Cu, pcbnew.B_Cu

board = pcbnew.BOARD()
_nets = {}
def net(name):
    if name not in _nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); _nets[name] = n
    return _nets[name]

def P(x, y):
    return VECTOR2I(mm(x), mm(y))

def gu(k):            # координата по сетке
    return round(k * G, 3)

PARTS = []            # (ref, value, lcsc/описание) для BOM

def place(lib, name, ref, x, y, rot=0, value="", nets=None, desc=""):
    fp = pcbnew.FootprintLoad(os.path.join(LIB, lib + ".pretty"), name)
    assert fp is not None, (lib, name)
    fp.SetReference(ref); fp.SetValue(value or name); board.Add(fp)
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    fp.Value().SetVisible(False)
    fp.Reference().SetTextSize(VECTOR2I(mm(0.8), mm(0.8))); fp.Reference().SetTextThickness(mm(0.12))
    if nets:
        for num, nn in nets.items():
            pad_net(fp, num, nn)
    PARTS.append((ref, value or name, lib + ":" + name, desc))
    return fp

def pad_net(fp, num, netname):
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            p.SetNet(net(netname))

def padpos(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            return p.GetPosition().x / 1e6, p.GetPosition().y / 1e6

def r0603(ref, x, y, a, b, rot=0, value="33"):
    return place("Resistor_SMD", "R_0603_1608Metric", ref, x, y, rot, value, {1: a, 2: b}, "резистор 0603")
def c0603(ref, x, y, a, b, rot=0, value="100n"):
    return place("Capacitor_SMD", "C_0603_1608Metric", ref, x, y, rot, value, {1: a, 2: b}, "конденсатор 0603")
def c0805(ref, x, y, a, b, rot=0, value="10u"):
    return place("Capacitor_SMD", "C_0805_2012Metric", ref, x, y, rot, value, {1: a, 2: b}, "конденсатор 0805")

def text(s, x, y, layer=pcbnew.F_SilkS, size=1.0, rot=0, thick=0.15):
    t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(thick)); t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---------------------------------------------------------------- контур и отверстия
def outline():
    pts = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(x1, y1)); s.SetEnd(P(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    for i, (x, y) in enumerate([(3.81, 3.81), (W - 3.81, 3.81), (3.81, H - 3.81), (W - 3.81, H - 3.81)]):
        place("MountingHole", "MountingHole_3.2mm_M3", "H%d" % (i + 1), x, y, 0, "M3", None, "отверстие M3")

# ---------------------------------------------------------------- буфер 74LVC244 (SOIC-20W)
# пары вход -> выход: 1A1(2)->1Y1(18) ... 2A4(17)->2Y4(3)
BUF_PAIRS = [(2, 18), (4, 16), (6, 14), (8, 12), (11, 9), (13, 7), (15, 5), (17, 3)]

def buffer(ref, x, y, ins, outs, cref):
    """ins/outs — списки из 8 имён цепей (None — вход на GND, выход свободен)."""
    nets = {1: "GND", 19: "GND", 10: "GND", 20: "3V3L"}
    for (pi, po), a, b in zip(BUF_PAIRS, ins, outs):
        nets[pi] = a if a else "GND"
        if b:
            nets[po] = b
    fp = place("Package_SO", "SOIC-20W_7.5x12.8mm_P1.27mm", ref, x, y, 0, "74LVC244A", nets, "буфер 8 каналов, SOIC-20W")
    c0603(cref, x - gu(2), y - gu(13), "3V3L", "GND", 0)      # над корпусом, снизу от 10 контакта
    return fp

# ---------------------------------------------------------------- элементы J1..J16
HDR_Y0, HDR_DY = gu(24), gu(26)          # 15,24 мм, шаг 16,51 мм
HDR_XL, HDR_XR = gu(8), gu(148)          # 5,08 и 81,28
RES_XL, RES_XR = gu(34), gu(122)         # колонки резисторов элемента: 22,86 и 77,47 (справа — зеркально)

def grp5v(n):
    return "5V_%s" % "ABCD"[(n - 1) // 4]

def element(n):
    left = n <= 8
    row = (n - 1) % 8
    y = HDR_Y0 + row * HDR_DY
    x = HDR_XL if left else HDR_XR
    nets = {1: grp5v(n), 2: "3V3_MIC", 3: "GND", 4: "GND", 11: "GND", 12: "GND",
            5: "BCLK_A%d" % n, 6: "BCLK_M%d" % n, 7: "LRC_A%d" % n, 8: "LRC_M%d" % n,
            9: "TXD_%d" % n, 10: "MIC_%d" % n}
    # 2x6 повернуть на -90: 6 контактов вдоль x, нечётный ряд (усилитель) ближе к краю? ряд 1 — верхний
    place("Connector_PinHeader_2.54mm", "PinHeader_2x06_P2.54mm_Vertical", "J%d" % n, x, y, 90 if left else 270, "2x6", nets,
          "гребёнка 2x6 элемента")
    rx = RES_XL if left else RES_XR
    pairs = [("BA%d" % n, "BCLK_A%d" % n, "33"), ("BM%d" % n, "BCLK_M%d" % n, "33"),
             ("LA%d" % n, "LRC_A%d" % n, "33"), ("LM%d" % n, "LRC_M%d" % n, "33"),
             ("TX%d" % n, "TXD_%d" % n, "33"), ("MIC_%d" % n, "GND", "100k"),
             ("MO%d" % n, "MIC%d" % (n - 1), "33")]
    for k, (a, b, v) in enumerate(pairs):
        ry = y - gu(18) + k * gu(3)
        if left:
            r0603("R%d" % (n * 10 + k + 1), rx, ry, b, a, 0, v)       # контакт 1 слева — к гребёнке
        else:
            r0603("R%d" % (n * 10 + k + 1), rx, ry, a, b, 0, v)       # контакт 2 справа — к гребёнке
    text("J%d" % n, x + (6.35 if left else -6.35), y + (2.2 if left else -2.2), size=1.0)

# ---------------------------------------------------------------- шлейфы к ПЛИС J20 (P2), J21 (P3)
P2 = {3: "TXD0", 4: "TXD1", 5: "TXD2", 6: "TXD3", 7: "TXD4", 9: "TXD5", 12: "TXD6", 13: "TXD7", 14: "TXD8",
      15: "TXD9", 16: "TXD10", 17: "TXD11", 18: "TXD12", 19: "TXD13", 22: "TXD14", 24: "TXD15",
      25: "BCLK", 26: "LRCLK", 27: "MON_SD"}
P3 = {3: "MIC0", 4: "MIC1", 5: "MIC2", 6: "MIC3", 7: "MIC4", 9: "MIC5", 12: "MIC6", 13: "MIC7", 14: "MIC8",
      15: "MIC9", 16: "MIC10", 17: "MIC11", 18: "MIC12", 19: "MIC13", 22: "MIC14", 24: "MIC15",
      25: "CAL", 26: "BTN_TEST", 27: "ESP_RX", 28: "ESP_TX"}
PWR = {2: "GND", 8: "GND", 11: "GND", 20: "GND", 29: "GND"}     # 1,10,21,30 (3V3) и 23 (5V) не подключаются

def dip2k(d):
    """Контакт гребёнки платы расширения (1-15 один ряд, 16-30 другой, 30 напротив 1) -> контакт
    вилки IDC по зигзагу футпринта (1,2 в первой колонке...). Прямой шлейф соединяет контакты по положению."""
    return 2 * d - 1 if d <= 15 else 2 * (31 - d)

def idc(ref, x, y, sig, rot=0):
    nets = {dip2k(d): n for d, n in list(PWR.items()) + list(sig.items())}
    return place("Connector_IDC", "IDC-Header_2x15_P2.54mm_Vertical", ref, x, y, rot, "IDC 2x15", nets,
                 "вилка IDC 2x15 с ключом")

# ---------------------------------------------------------------- сборка
def build():
    outline()
    for n in range(1, 17):
        element(n)
    # буферы — рядом со своими элементами: U1,U3,U5,U7 (слева) и U2,U4,U6,U8 (справа) — такты пары соседних
    # элементов (по 4 выхода на элемент); U9/U11 (слева), U10/U12 (справа) — TXD и MIC четырёх элементов.
    XL, XR = gu(49), gu(107)
    def chip_y(k):                                   # ряды чипов: между элементами, шаг = шагу элементов
        return HDR_Y0 + (k + 0.5) * HDR_DY
    for side, x, n0, uclk, utm in (("L", XL, 1, (1, 3, 5, 7), (9, 11)), ("R", XR, 9, (2, 4, 6, 8), (10, 12))):
        for k, u in enumerate(uclk):                 # пара элементов a, b
            a, b = n0 + 2 * k, n0 + 2 * k + 1
            ins = ["BCLK", "BCLK", "LRCLK", "LRCLK", "BCLK", "BCLK", "LRCLK", "LRCLK"]
            outs = ["BA%d" % a, "BM%d" % a, "LA%d" % a, "LM%d" % a, "BA%d" % b, "BM%d" % b, "LA%d" % b, "LM%d" % b]
            buffer("U%d" % u, x, chip_y(2 * k), ins, outs, "C%d" % u)
        for k, u in enumerate(utm):                  # четвёрка элементов
            els = list(range(n0 + 4 * k, n0 + 4 * k + 4))
            ins = ["MIC_%d" % n for n in els] + ["TXD%d" % (n - 1) for n in els]
            outs = ["MO%d" % n for n in els] + ["TX%d" % n for n in els]
            buffer("U%d" % u, x, chip_y(4 * k + 1), ins, outs, "C%d" % u)
    idc("J20", gu(66), gu(16), P2)
    idc("J21", gu(86), gu(16), P3)
    text("P2", gu(66) + 1.27, gu(16) - 7.0, size=1.2); text("P3", gu(86) + 1.27, gu(16) - 7.0, size=1.2)
    # U13: BCLK/LRCLK/MON_SD -> ЦАП, CAL с зонда, BCLK/LRCLK -> зонд
    buffer("U13", gu(78), gu(96), ["BCLK", "LRCLK", "MON_SD", "CAL_IN", "BCLK", "LRCLK", None, None],
           ["BCK_DAC", "LRCK_DAC", "DIN_DAC", "CAL_B", "BCLK_PB", "LRC_PB", None, None], "C13")
    r0603("R201", gu(70), gu(108), "CAL_B", "CAL", 0, "33")
    r0603("R202", gu(70), gu(111), "BCLK_PB", "BCLK_P", 0, "33")
    r0603("R203", gu(70), gu(114), "LRC_PB", "LRC_P", 0, "33")
    r0603("R204", gu(86), gu(108), "CAL_IN", "GND", 0, "100k")
    audio()
    power()
    misc()
    ethernet()

def audio():
    # ЦАП PCM5102A (TSSOP-20, выводы вдоль y) и драйвер наушников TDA1308
    x, y = gu(78), gu(140) + 0.3175
    nets = {1: "CAPP", 2: "CAPM", 3: "GND", 4: "VNEG", 5: "OUTL", 6: "OUTR", 7: "GND", 8: "3V3L", 9: "LDOO",
            10: "GND", 11: "GND", 12: "GND", 13: "BCK_DAC", 14: "DIN_DAC", 15: "LRCK_DAC", 16: "GND",
            17: "3V3L", 18: "GND", 19: "3V3L", 20: "3V3L"}
    place("Package_SO", "TSSOP-20_4.4x6.5mm_P0.65mm", "U31", x, y, 0, "PCM5102A", nets, "ЦАП I2S, TSSOP-20")
    c0805("C31", x - gu(13), y - gu(8), "CAPP", "CAPM", 90, "2u2")
    c0805("C32", x - gu(13), y - gu(2), "VNEG", "GND", 90, "2u2")
    c0805("C33", x + gu(13), y + gu(3), "LDOO", "GND", 90, "2u2")
    c0603("C34", x + gu(13), y - gu(2), "3V3L", "GND", 90, "100n")
    c0805("C35", x + gu(13), y - gu(7), "3V3L", "GND", 90, "10u")
    c0603("C36", x + gu(17), y - gu(2), "3V3L", "GND", 90, "100n")
    c0603("C37", x + gu(17), y - gu(7), "3V3L", "GND", 90, "100n")
    # TDA1308: повторители, вход через 1 мкФ, смещение VREF
    x2, y2 = gu(78), gu(170)
    place("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "U32", x2, y2, 0, "TDA1308",
          {1: "HP_L_O", 2: "HP_L_O", 3: "HP_L_IN", 4: "GND", 5: "HP_R_IN", 6: "HP_R_O", 7: "HP_R_O", 8: "+5V"},
          "драйвер наушников, SO-8")
    c0805("C41", x2 - gu(8), y2 - gu(8), "OUTL", "HP_L_IN", 0, "1u")
    c0805("C42", x2 + gu(8), y2 - gu(8), "OUTR", "HP_R_IN", 0, "1u")
    r0603("R43", x2 - gu(8), y2 - gu(12), "HP_L_IN", "VREF", 0, "10k")
    r0603("R44", x2 + gu(8), y2 - gu(12), "HP_R_IN", "VREF", 0, "10k")
    r0603("R41", x2 - gu(8), y2 + gu(10), "+5V", "VREF", 0, "10k")
    r0603("R42", x2 + gu(8), y2 + gu(10), "VREF", "GND", 0, "10k")
    c0805("C43", x2, y2 - gu(8), "VREF", "GND", 0, "10u")
    c0603("C46", x2 + gu(8), y2 + gu(14), "+5V", "GND", 0, "100n")
    place("Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm", "C44", x2 - gu(14), y2 + gu(2), 90, "220u",
          {1: "HP_L_O", 2: "HP_L"}, "электролит 220 мкФ 6,3 В")
    place("Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm", "C45", x2 + gu(14), y2 + gu(2), 90, "220u",
          {1: "HP_R_O", 2: "HP_R"}, "электролит 220 мкФ 6,3 В")
    for ref, xj in (("J26", gu(92)), ("J27", gu(114))):
        place("Connector_Audio", "Jack_3.5mm_CUI_SJ1-3523N_Horizontal", ref, xj, gu(273), 0, "3.5mm",
              {"T": "HP_L", "R": "HP_R", "S": "GND"}, "гнездо 3,5 мм стерео")
        fpj = board.FindFootprintByReference(ref)
        for it in list(fpj.GraphicalItems()):
            if it.GetLayer() == pcbnew.Edge_Cuts:
                fpj.Remove(it)

def power():
    # вход 5 В у правого нижнего края, защита, накопитель; предохранители и стабилизаторы — над ним
    place("Connector_BarrelJack", "BarrelJack_Horizontal", "J18", gu(138), gu(278), 270, "5.5/2.1",
          {1: "VIN", 2: "GND", 3: "GND"}, "гнездо питания 5,5/2,1")
    place("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "Q1", gu(120), gu(238), 0, "AO4407A",
          {1: "+5V", 2: "+5V", 3: "+5V", 4: "GND", 5: "VIN", 6: "VIN", 7: "VIN", 8: "VIN"}, "P-MOSFET, защита от переполюсовки")
    d1 = place("Diode_SMD", "D_SMB", "D1", gu(110), gu(238), 90, "SMBJ5.0A", None, "TVS 5 В, SMB")
    dp = sorted(d1.Pads(), key=lambda q: q.GetPosition().y)
    dp[1].SetNet(net("+5V")); dp[0].SetNet(net("GND"))      # катод снизу (к шине +5V у нижнего края), анод к земле
    place("Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", "C101", gu(94), gu(238), 0, "1000u",
          {1: "+5V", 2: "GND"}, "электролит 1000 мкФ 10 В")
    c0805("C102", gu(122), gu(245), "+5V", "GND", 0, "10u")
    # предохранители у краёв: F1 (5V_A: J1-J4) и F2 (5V_B: J5-J8) слева внизу, F3 (5V_C), F4 (5V_D) справа внизу
    for ref, grp, x, y in (("F1", "5V_A", gu(12), gu(258)), ("F2", "5V_B", gu(4), gu(258)),
                           ("F3", "5V_C", gu(150), gu(256)), ("F4", "5V_D", gu(150), gu(267))):
        fp = place("Fuse", "Fuse_1812_4532Metric", ref, x, y, 90, "PTC 1.5A", None, "самовосстанавливающийся предохранитель 1812")
        pads = sorted(fp.Pads(), key=lambda q: q.GetPosition().y)
        pads[0].SetNet(net(grp)); pads[1].SetNet(net("+5V"))         # верхняя площадка — к гребёнкам, нижняя — шина +5V
    # LDO логики
    place("Package_TO_SOT_SMD", "SOT-23-5", "U20", gu(72), gu(196) + 0.16, 0, "AP2112K-3.3",
          {1: "+5V", 2: "GND", 3: "+5V", 5: "3V3L"}, "LDO 3,3 В 600 мА")
    c0805("C21", gu(66), gu(196), "+5V", "GND", 90, "1u")
    c0805("C22", gu(72), gu(201), "3V3L", "GND", 0, "1u")
    # чистое 3,3 В микрофонов
    place("Inductor_SMD", "L_0805_2012Metric", "FB1", gu(66), gu(203), 0, "600R", {1: "+5V", 2: "5V_MIC"}, "феррит 0805 600 Ом")
    place("Package_TO_SOT_SMD", "SOT-23-5", "U21", gu(72), gu(210) + 0.16, 0, "AP2112K-3.3",
          {1: "5V_MIC", 2: "GND", 3: "5V_MIC", 5: "3V3_MIC"}, "LDO 3,3 В 600 мА (микрофоны)")
    c0805("C23", gu(66), gu(210), "5V_MIC", "GND", 90, "1u")
    c0805("C24", gu(80), gu(210), "3V3_MIC", "GND", 90, "1u")
    # индикация
    place("LED_SMD", "LED_0603_1608Metric", "LED1", gu(84), gu(215), 0, "LED", {1: "GND", 2: "LED1"}, "светодиод 0603")
    r0603("R207", gu(90), gu(215), "LED1", "+5V", 0, "1k")
    place("LED_SMD", "LED_0603_1608Metric", "LED2", gu(96), gu(215), 0, "LED", {1: "GND", 2: "LED2"}, "светодиод 0603")
    r0603("R208", gu(102), gu(215), "LED2", "3V3L", 0, "1k")
    text("5V", gu(84), gu(212), size=1.0, thick=0.15); text("3V3", gu(96), gu(212), size=1.0, thick=0.15)

def misc():
    # J17 — RJ45 зонда у нижнего края слева; J25 — ESP32; SW1 — кнопка «тест»
    place("Connector_RJ", "RJ45_Amphenol_54602-x08_Horizontal", "J17", gu(22), gu(268), 0, "RJ45",
          {1: "BCLK_P", 2: "GND", 3: "LRC_P", 4: "3V3_MIC", 5: "3V3_MIC", 6: "GND", 7: "CAL_IN", 8: "GND"},
          "RJ45 зонда")
    place("Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical", "J25", gu(66), gu(118), 0, "ESP32",
          {1: "ESP_TX_J", 2: "ESP_RX_J", 3: "GND"}, "гребёнка 1x3 к ESP32")
    r0603("R205", gu(76), gu(116), "ESP_TX", "ESP_TX_J", 0, "100")
    r0603("R206", gu(76), gu(119), "ESP_RX", "ESP_RX_J", 0, "100")
    place("Button_Switch_SMD", "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", "SW1", gu(88), gu(122), 0, "кнопка",
          {1: "BTN_TEST", 2: "3V3L"}, "кнопка тактовая 6x6")
    text("TEST", gu(88), gu(130), size=1.0)
    text("ESP32 TX RX GND", gu(66) - 3.0, gu(120), size=0.8, thick=0.12, rot=90)
    text("DPAA dist. board v1  2026-10", gu(36), gu(220), size=1.2)
    text("ЗОНД RJ45", gu(22) + 6, gu(258), size=1.0)


# ---------------------------------------------------------------- Ethernet: гребёнка P1 платы расширения -> MagJack
# P1: пары MDI после PHY B50612D (ETH1), контакты по схеме платы расширения (нумерация 1-15/16-30)
P1 = {1: "ETH1_2P", 2: "ETH1_2N", 3: "ETH1_1N", 4: "ETH1_1P", 27: "ETH1_3P", 28: "ETH1_3N", 29: "ETH1_4N", 30: "ETH1_4P",
      5: "GND", 14: "GND", 17: "GND", 23: "GND", 26: "GND"}        # 6/15/16/25 (3V3), 8 (5V), 7/9/22/24 (NC), 10-13/18-21 (ETH2) не подключены
ETH_X0, ETH_Y0 = gu(65), gu(232)       # J19: контакт 1 справа (rot 270): ряд 1-15 сверху (y0), ряд 16-30 снизу (y0+2,54)
JACK_X, JACK_Y = gu(51), 160.5         # J29: начало футпринта (R1), лицевая сторона — к нижнему краю

def ethernet():
    idc("J19", ETH_X0, ETH_Y0, P1, 270)
    text("P1 (ETH)", ETH_X0 - 17.0, ETH_Y0 - 6.0, size=1.2)
    # MagJack UDE RB1-125B8G1A: R1 — общий центральный отвод (сторона PHY), R2..R9 — TD1..TD4, R10 — земля
    # встроенной терминации Боба Смита (75 Ом + 1000 пФ 2 кВ внутри) — на chassis, SH — экран (chassis). Пары 2 и 4
    # подключены с обратной полярностью (так нет пересечений; PHY исправляет полярность автоматически).
    nets = {"R1": "ETH_CT", "R2": "ETH1_1P", "R3": "ETH1_1N", "R4": "ETH1_2N", "R5": "ETH1_2P",
            "R6": "ETH1_3P", "R7": "ETH1_3N", "R8": "ETH1_4N", "R9": "ETH1_4P", "R10": "CHASSIS", "SH": "CHASSIS"}
    place("Connector_RJ", "RJ45_UDE_RB1-125B8G1A", "J29", JACK_X, JACK_Y, 0, "RB1-125B8G1A", nets,
          "RJ45 MagJack 1000BASE-T с трансформаторами (UDE RB1-125B8G1A)")
    text("ETH", JACK_X + 5.0, JACK_Y - 4.5, size=1.2)
    # центральный отвод: 100 нФ на землю; R301 0 Ом (не ставить) — к 3,3 В, если PHY с токовым выходом
    c0603("C301", gu(44), gu(251), "ETH_CT", "GND", 90, "100n")
    r = r0603("R301", gu(44), gu(246), "ETH_CT", "3V3L", 90, "0R DNP")
    r.SetDNP(True)
    # chassis <-> GND: 1 МОм || 1 нФ 2 кВ
    place("Capacitor_SMD", "C_1812_4532Metric", "C306", gu(73), gu(245), 0, "1n 2kV", {1: "GND", 2: "CHASSIS"}, "конденсатор 1812 1 нФ 2 кВ")
    r0603("R306", gu(82), gu(245), "CHASSIS", "GND", 0, "1M")
