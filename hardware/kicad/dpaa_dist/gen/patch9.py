# -*- coding: utf-8 -*-
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
p = open('place.py', encoding='utf-8').read()
rep = [
 ("W, H = 100.0, 160.0", "W, H = 100.0, 180.0"),
 # IDC: нумерация гребёнок платы расширения 1-15/16-30 -> зигзаг футпринта (прямой шлейф контакт в контакт)
 ('''def idc(ref, x, y, sig):
    nets = dict(PWR); nets.update(sig)
    return place("Connector_IDC", "IDC-Header_2x15_P2.54mm_Vertical", ref, x, y, 0, "IDC 2x15", nets,
                 "вилка IDC 2x15 с ключом")''',
  '''def dip2k(d):
    """Контакт гребёнки платы расширения (1-15 один ряд, 16-30 другой, 30 напротив 1) -> контакт
    вилки IDC по зигзагу футпринта (1,2 в первой колонке...). Прямой шлейф соединяет контакты по положению."""
    return 2 * d - 1 if d <= 15 else 2 * (31 - d)

def idc(ref, x, y, sig, rot=0):
    nets = {dip2k(d): n for d, n in list(PWR.items()) + list(sig.items())}
    return place("Connector_IDC", "IDC-Header_2x15_P2.54mm_Vertical", ref, x, y, rot, "IDC 2x15", nets,
                 "вилка IDC 2x15 с ключом")'''),
 ('for ref, xj in (("J26", gu(53)), ("J27", gu(75))):', 'for ref, xj in (("J26", gu(92)), ("J27", gu(114))):'),
 ('ref, xj, gu(242), 0, "3.5mm",', 'ref, xj, gu(273), 0, "3.5mm",'),
 ('"J18", gu(138), gu(246), 270,', '"J18", gu(138), gu(278), 270,'),
 ('(("F1", "5V_A", gu(12), gu(226)), ("F2", "5V_B", gu(4), gu(226)),\n                           ("F3", "5V_C", gu(150), gu(224)), ("F4", "5V_D", gu(150), gu(235)))',
  '(("F1", "5V_A", gu(12), gu(258)), ("F2", "5V_B", gu(4), gu(258)),\n                           ("F3", "5V_C", gu(150), gu(256)), ("F4", "5V_D", gu(150), gu(267)))'),
 ('"J17", gu(22), gu(236), 0, "RJ45",', '"J17", gu(22), gu(268), 0, "RJ45",'),
 ('text("ЗОНД RJ45", gu(22) + 6, gu(226), size=1.0)', 'text("ЗОНД RJ45", gu(22) + 6, gu(258), size=1.0)'),
]
for a, b in rep:
    assert a in p, a[:60]; p = p.replace(a, b)
# блок Ethernet
p = p.replace("    audio()\n    power()\n    misc()", "    audio()\n    power()\n    misc()\n    ethernet()")
p += '''

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
    # встроенной терминации Боба Смита (75 Ом + 1000 пФ 2 кВ внутри), SH — экран (chassis). Пары 2 и 4
    # подключены с обратной полярностью (так нет пересечений; PHY исправляет полярность автоматически).
    nets = {"R1": "ETH_CT", "R2": "ETH1_1P", "R3": "ETH1_1N", "R4": "ETH1_2N", "R5": "ETH1_2P",
            "R6": "ETH1_3P", "R7": "ETH1_3N", "R8": "ETH1_4N", "R9": "ETH1_4P", "R10": "GND", "SH": "CHASSIS"}
    place("Connector_RJ", "RJ45_UDE_RB1-125B8G1A", "J29", JACK_X, JACK_Y, 0, "RB1-125B8G1A", nets,
          "RJ45 MagJack 1000BASE-T с трансформаторами (UDE RB1-125B8G1A)")
    text("ETH", JACK_X + 5.0, JACK_Y - 4.5, size=1.2)
    # центральный отвод: 100 нФ на землю; R301 0 Ом (не ставить) — к 3,3 В, если PHY с токовым выходом
    c0603("C301", gu(44), gu(251), "GND", "ETH_CT", 90, "100n")
    r = r0603("R301", gu(44), gu(246), "3V3L", "ETH_CT", 90, "0R DNP")
    r.SetDNP(True)
    # chassis <-> GND: 1 МОм || 1 нФ 2 кВ
    place("Capacitor_SMD", "C_1812_4532Metric", "C306", gu(73), gu(246), 0, "1n 2kV", {1: "CHASSIS", 2: "GND"}, "конденсатор 1812 1 нФ 2 кВ")
    r0603("R306", gu(80), gu(246), "CHASSIS", "GND", 0, "1M")
'''
open('place.py', 'w', encoding='utf-8').write(p)

m = open('make_board.py', encoding='utf-8').read()
rep = [
 # шина +5V ниже; под MagJack — обход у самого края
 ("YB = 145.65", "YB = place.gu(261)      # 165,735: нижние площадки F1/F2"),
 ('''pre([fuse_pads["F2"][1], (97.79, YB), (97.79, fuse_pads["F4"][1][1]), fuse_pads["F4"][1]], "+5V", "F", PWR2)''',
  '''YB = fuse_pads["F2"][1][1]
YDIP = 177.5                                    # обход MagJack по самому краю
pre([fuse_pads["F2"][1], (27.5, YB), (27.5, YDIP), (49.0, YDIP), (49.0, YB), (97.79, YB), (97.79, fuse_pads["F4"][1][1]), fuse_pads["F4"][1]], "+5V", "F", PWR2)'''),
 ('''pre([fuse_pads["F1"][0], (fuse_pads["F1"][0][0], 139.9), (2.54, 139.9), (2.54, place.HDR_Y0), padxy("J1", 1)], "5V_A", "F", PWR2)''',
  '''pre([fuse_pads["F1"][0], (fuse_pads["F1"][0][0], 159.4), (2.54, 159.4), (2.54, place.HDR_Y0), padxy("J1", 1)], "5V_A", "F", PWR2)'''),
]
for a, b in rep:
    assert a in m, a[:60]; m = m.replace(a, b)
# цепи Ethernet вручную; трассировщику — запрет
a = "# 3V3_MIC: по низу"
assert a in m
m = m.replace(a, '''# ---------------------------------------------------------------- Ethernet: пары вручную, одним слоем, 45°
ETH_SKIP = {"ETH1_1P", "ETH1_1N", "ETH1_2P", "ETH1_2N", "ETH1_3P", "ETH1_3N", "ETH1_4P", "ETH1_4N", "CHASSIS", "ETH_CT"}
ETH_W, ETH_NECK = 0.25, 0.2
def jpad(num):
    return place.padpos(board.FindFootprintByReference("J29"), num)
def j19(dip):
    return place.padpos(board.FindFootprintByReference("J19"), place.dip2k(dip))
def eth_line(nm, pts, L, neck_from=None):
    """ломаная (точки) на слое L; участок от neck_from до конца — шейка 0,2 мм (проход между площадками)"""
    lay = 0 if L == "F" else 1
    length = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        w = ETH_NECK if (neck_from is not None and y1 >= neck_from - 1e-6) else ETH_W
        add_track(x1, y1, x2, y2, lay, nm, w)
        length += math.hypot(x2 - x1, y2 - y1)
        grid.block_rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), (0, 1), -1, clr=1.0, via_clr=1.2)
    return length
YU, YL = place.ETH_Y0, place.ETH_Y0 + 2.54           # ряды J19: верхний (1-15), нижний (16-30)
G1, G2 = YL - 1.27, YL + 1.5                          # уровень прохода между нижними контактами, выход из него
YN = place.JACK_Y - 1.2                               # начало шейки перед внутренним рядом площадок
xg = lambda dip: j19(dip)[0]
eth_len = {}
# пара 1 (F, верхний ряд): 1P -> R2 (внешний ряд, через проход 33,65), 1N -> R3 (внутренний, прямо через проход)
x1p, x1n = xg(4), xg(3)
eth_len["ETH1_1P"] = eth_line("ETH1_1P", [(x1p, YU), (x1p - 1.27, G1), (x1p - 1.27, G2), (x1p, G2 + 1.27), (x1p, YN), jpad("R2")], "F", YN)
eth_len["ETH1_1N"] = eth_line("ETH1_1N", [(x1n, YU), (x1n - 1.27, G1), jpad("R3")], "F")
# пара 2 (F, обратная полярность): 2N -> R4 (внешний), 2P -> R5 (внутренний)
x2p, x2n = xg(1), xg(2)
eth_len["ETH1_2N"] = eth_line("ETH1_2N", [(x2n, YU), (x2n - 1.27, G1), (x2n - 1.27, G2), (x2n - 2.54, G2 + 1.27), (x2n - 2.54, YN), jpad("R4")], "F", YN)
eth_len["ETH1_2P"] = eth_line("ETH1_2P", [(x2p, YU), (x2p - 1.27, G1), (x2p - 1.27, G2), (x2p - 3.81, G2 + 2.54), jpad("R5")], "F")
# пара 3 (B, нижний ряд): 3P -> R6 (внешний), 3N -> R7 (внутренний)
x3p, x3n = xg(27), xg(28)
r6, r7 = jpad("R6"), jpad("R7")
eth_len["ETH1_3P"] = eth_line("ETH1_3P", [(x3p, YL), (x3p, G2 - 0.6), (r6[0], G2 - 0.6 + (r6[0] - x3p)), (r6[0], YN), r6], "B", YN)
eth_len["ETH1_3N"] = eth_line("ETH1_3N", [(x3n, YL), (x3n, G2 - 0.6), (r7[0], G2 - 0.6 + (r7[0] - x3n)), r7], "B")
# пара 4 (B, обратная полярность): 4N -> R8 (внешний), 4P -> R9 (внутренний)
x4p, x4n = xg(30), xg(29)
r8, r9 = jpad("R8"), jpad("R9")
eth_len["ETH1_4N"] = eth_line("ETH1_4N", [(x4n, YL), (x4n, G2 - 0.6), (r8[0], G2 - 0.6 + (r8[0] - x4n)), (r8[0], YN), r8], "B", YN)
eth_len["ETH1_4P"] = eth_line("ETH1_4P", [(x4p, YL), (x4p, G2 - 0.6), (r9[0], G2 - 0.6 + (r9[0] - x4p)), r9], "B")
# центральный отвод R1 -> C301 -> R301; земля R10 — вверх к полигону
r1 = jpad("R1"); c301 = place.padpos(board.FindFootprintByReference("C301"), 2); r301 = place.padpos(board.FindFootprintByReference("R301"), 2)
eth_line("ETH_CT", [r1, (c301[0] + 1.1, r1[1]), (c301[0] + 0.8, c301[1]), c301, (c301[0] - 1.0, c301[1]), (c301[0] - 1.0, r301[1] + 1.0), r301], "F")
r10 = jpad("R10")
pre([r10, (r10[0] + 0.635, r10[1] - 0.635), (r10[0] + 0.635, place.JACK_Y - 3.0)], "GND", "F", TRK)
open(os.path.join(HERE, "eth_lengths.txt"), "w", encoding="utf-8").write(
    "\\n".join("%s %.2f мм" % (k, v) for k, v in sorted(eth_len.items())) + "\\n")
print("Ethernet: длины пар", {k: round(v, 1) for k, v in sorted(eth_len.items())})
# зона корпуса под MagJack — запрет для трассировщика (и земли): всё, кроме своих площадок
grid.block_rect(place.JACK_X - 4.0, place.JACK_Y - 2.6, place.JACK_X + 15.4, H, (0, 1), -1, clr=0.0, via_clr=0.3)

# 3V3_MIC: по низу''')
a = "queue = [n for n in names if n != 'GND']      # земля — после всех перекладок"
assert a in m
m = m.replace(a, "queue = [n for n in names if n != 'GND' and n not in ETH_SKIP]      # земля — после всех перекладок; Ethernet — вручную")
# зона CHASSIS под MagJack (оба слоя, приоритет выше земли)
a = '''for L in (F, B):
    zone([(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)], "GND", L)'''
assert a in m
m = m.replace(a, '''for L in (F, B):
    zone([(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)], "GND", L)
JX, JY = place.JACK_X, place.JACK_Y
c306 = place.padpos(board.FindFootprintByReference("C306"), 1); r306 = place.padpos(board.FindFootprintByReference("R306"), 1)
for L in (F, B):
    z = zone([(JX - 3.9, JY - 2.3), (JX + 15.3, JY - 2.3), (JX + 15.3, 176.3), (JX - 3.9, 176.3)], "CHASSIS", L)
    z.SetAssignedPriority(1)
z = zone([(c306[0] - 0.9, c306[1] - 1.1), (r306[0] + 0.6, c306[1] - 1.1), (r306[0] + 0.6, c306[1] + 1.1), (JX + 15.3, c306[1] + 1.1),
          (JX + 15.3, JY - 2.3), (c306[0] - 0.9, JY - 2.3)], "CHASSIS", F)
z.SetAssignedPriority(1)''')
m = m.replace('''        pass
    board.Add(z)
for L in (F, B):''', '''        pass
    board.Add(z)
    return z
for L in (F, B):''')
open('make_board.py', 'w', encoding='utf-8').write(m)
print("patched")
