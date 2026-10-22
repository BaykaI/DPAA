# -*- coding: utf-8 -*-
"""Распределительная плата DPAA: компоновка (place.py) + трассировка (router.py) + полигоны земли + скос углов.
Запуск: "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" -I make_board.py"""
import os, sys, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
from pcbnew import VECTOR2I, FromMM as mm
import place
from place import board, net, P, F, B, W, H
from router import Grid, Router, G

OUT = os.path.join(HERE, "..", "dpaa_dist.kicad_pcb")
TRK, PWR, PWR2 = 0.25, 0.5, 1.0
VIA_D, VIA_DRL = 0.6, 0.3

place.build()

# ---------------------------------------------------------------- сетка и препятствия
grid = Grid(W, H)
netid = {}
def nid(name):
    if name not in netid:
        netid[name] = len(netid) + 1
    return netid[name]

terms = {}          # имя цепи -> список (ix, iy, L|None)
stubs = []          # ручные отрезки: (x1,y1,x2,y2,layer,netname)

def pad_rect(pad):
    bb = pad.GetBoundingBox()
    return bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6

def pad_layers(pad):
    ls = []
    if pad.IsOnLayer(F):
        ls.append(0)
    if pad.IsOnLayer(B):
        ls.append(1)
    return ls

NOROUTE = set()           # земля тоже трассируется (деревом, последней) и дополнительно заливается полигонами
pads_by_net = {}
for fp in board.GetFootprints():
    fx, fy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    for pad in fp.Pads():
        nm = pad.GetNetname()
        x1, y1, x2, y2 = pad_rect(pad)
        ls = pad_layers(pad)
        if not ls or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:                      # NPTH
            grid.block_rect(x1, y1, x2, y2, (0, 1), -1, clr=0.45, via_clr=1.2)    # NPTH: отверстие-отверстие >= 0,5
            continue
        own = nid(nm) if nm and nm not in NOROUTE else -1
        grid.block_rect(x1, y1, x2, y2, ls, own)
        if nm and nm not in NOROUTE:
            pads_by_net.setdefault(nm, []).append((pad, fp, (x1, y1, x2, y2), ls))

def cells_in_rect(x1, y1, x2, y2, shrink=0.05):
    out = []
    ix1, ix2 = int(math.ceil((x1 + shrink) / G)), int(math.floor((x2 - shrink) / G))
    iy1, iy2 = int(math.ceil((y1 + shrink) / G)), int(math.floor((y2 - shrink) / G))
    for ix in range(ix1, ix2 + 1):
        for iy in range(iy1, iy2 + 1):
            out.append((ix, iy))
    return out

# терминалы: ячейка внутри площадки; иначе — отвод наружу от корпуса до узла сетки
escape_n = 0
used_cells = set()
for nm, lst in pads_by_net.items():
    tl = []
    for pad, fp, (x1, y1, x2, y2), ls in lst:
        L = None if len(ls) == 2 else ls[0]
        cells = cells_in_rect(x1, y1, x2, y2)
        if cells:
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            cells.sort(key=lambda c: (c[0] * G - cx) ** 2 + (c[1] * G - cy) ** 2)
            tl.append((cells[0][0], cells[0][1], L))
            continue
        # отвод: от центра площадки наружу (от центра корпуса) вдоль длинной стороны площадки,
        # длина — три уровня по номеру вывода, затем малый поперечный сдвиг до узла сетки
        px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
        fx, fy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
        num = int(pad.GetNumber()) if pad.GetNumber().isdigit() else 0
        ext = 0.9 + 1.0 * (num % 3)
        if (x2 - x1) >= (y2 - y1):
            dx = 1 if px > fx else -1
            ex = px + dx * ((x2 - x1) / 2 + ext)
            ix = int(round(ex / G))
            if (ix * G - ex) * dx < 0:
                ix += dx
            iy = int(round(py / G))
        else:
            dy = 1 if py > fy else -1
            ey = py + dy * ((y2 - y1) / 2 + ext)
            iy = int(round(ey / G))
            if (iy * G - ey) * dy < 0:
                iy += dy
            ix = int(round(px / G))
        pts = [(px, py), (ix * G, iy * G)]          # прямой (чуть наклонный) отвод до узла сетки
        key = (ix, iy, ls[0])
        assert key not in used_cells, ("совпали узлы отводов", fp.GetReference(), pad.GetNumber())
        used_cells.add(key)
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            stubs.append((ax, ay, bx, by, ls[0], nm))
            grid.block_rect(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), (ls[0],), nid(nm), clr=0.45, via_clr=0.6)
        tl.append((ix, iy, ls[0]))
        escape_n += 1
    terms[nm] = tl

print("цепей", len(terms), "отводов", escape_n)

# ---------------------------------------------------------------- порядок и ширины
WIDE2 = set()
WIDE1 = {"VIN", "+5V", "5V_A", "5V_B", "5V_C", "5V_D", "3V3L", "3V3_MIC", "5V_MIC"}
def width_of(nm):
    return TRK                      # все дорожки трассировщика 0,25; силовые шины проложены вручную (1,0 мм)

def order_key(nm):
    t = terms[nm]
    if nm in WIDE2:
        return (0, -len(t))
    if nm in WIDE1:
        return (1, -len(t))
    if nm in ("BCLK", "LRCLK"):
        return (2, -len(t))
    if nm == "GND":
        return (9, 0)
    # короткие локальные цепи раньше, затем длинные (BCLK/LRCLK последними)
    xs = [a for a, b, _ in t]; ys = [b for a, b, _ in t]
    span = (max(xs) - min(xs)) + (max(ys) - min(ys))
    return (3, span)

names = sorted(terms, key=order_key)
from router import column_penalty
from place import RES_XL, RES_XR, gu
BAN = 10 ** 6
# колонки резисторов: со стороны гребёнки — весь коридор (только горизонтали), со стороны буферов — 2 ячейки
column_penalty(grid, 0, 0, (0,), BAN, 3.0, 134.0, xa=RES_XL - 2.6, xb=RES_XL + 3.9)
column_penalty(grid, 0, 0, (0,), BAN, 3.0, 134.0, xa=RES_XR - 3.9, xb=RES_XR + 2.6)
# колонки выводов SOIC-20W: площадки и коридор снаружи от них, только в полосе выводов каждого корпуса
def chip_bans(cx, cy):
    column_penalty(grid, 0, 0, (0,), BAN, cy - 6.6, cy + 6.6, xa=cx - 4.6 - 1.6, xb=cx - 4.6 + 0.7)
    column_penalty(grid, 0, 0, (0,), BAN, cy - 6.6, cy + 6.6, xa=cx + 4.6 - 0.7, xb=cx + 4.6 + 1.6)
for k in range(7):
    for cx in (gu(49), gu(107)):
        chip_bans(cx, place.HDR_Y0 + (k + 0.5) * place.HDR_DY)
chip_bans(gu(78), gu(96))
# колонки переходных в коридорах: по нижнему слою только поперёк (выходы переходных вверх/вниз остаются свободны)
for vx in (RES_XL - 3 * G, RES_XL + 3 * G, RES_XL + 5 * G, RES_XR - 5 * G, RES_XR - 3 * G, RES_XR + 3 * G, gu(58), gu(98)):
    column_penalty(grid, vx, 0.1, (1,), BAN, 3.0, 134.0)
for dx in (-2.9, 2.9):                                    # U31 TSSOP: отводы идут горизонтально
    column_penalty(grid, gu(78) + dx, 2.2, (0,), BAN, 85.0, 93.0)
for ix in (gu(66), gu(66) + 2.54, gu(86), gu(86) + 2.54):   # колонки IDC
    column_penalty(grid, ix, 0.7, (0, 1))
for xm in (gu(66) + 1.27, gu(86) + 1.27):                 # середина между рядами J20/J21: по нижнему слою только поперёк,
    column_penalty(grid, xm, 0.1, (1,), BAN, 9.0, 47.0)   # чтобы заливка земли под вилкой оставалась связной
for nm, tl in terms.items():
    for ix, iy, L in tl:
        for LL in ((0, 1) if L is None else (L,)):
            i = grid.idx(ix, iy)
            if grid.occ[LL][i] == 0:
                grid.occ[LL][i] = nid(nm)
def add_track(x1, y1, x2, y2, L, nm, w):
    if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
        return
    t = pcbnew.PCB_TRACK(board); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(mm(w))
    t.SetLayer(F if L == 0 else B); t.SetNet(net(nm)); board.Add(t)

rt = Router(grid)

PRE = {}            # имя цепи -> ячейки предварительно проложенных шин
def pre(points, nm, L, w):
    """Шина вручную: дорожки в плату + занятие ячеек сетки (с запасом под ширину)."""
    lay = 0 if L == "F" else 1
    cells = set()
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        add_track(x1, y1, x2, y2, lay, nm, w)
        grid.block_rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), (lay,), nid(nm), clr=w / 2 + 0.33, via_clr=w / 2 + 0.6, fat_clr=w / 2 + 0.75)
        for ix, iy in cells_in_rect(min(x1, x2) - w / 2, min(y1, y2) - w / 2, max(x1, x2) + w / 2, max(y1, y2) + w / 2, 0.0):
            if 0 <= ix < grid.nx and 0 <= iy < grid.ny:
                cells.add((ix, iy, lay)); grid.occ[lay][grid.idx(ix, iy)] = nid(nm)
    PRE.setdefault(nm, set()).update(cells)

def pre_via(x, y, nm):
    v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRL))
    v.SetLayerPair(F, B); v.SetNet(net(nm)); board.Add(v)
    grid.block_rect(x - 0.35, y - 0.35, x + 0.35, y + 0.35, (0, 1), nid(nm), clr=0.33, via_clr=0.7)
    ix, iy = grid.cell(x, y)
    for L in (0, 1):
        grid.occ[L][grid.idx(ix, iy)] = nid(nm); PRE.setdefault(nm, set()).add((ix, iy, L))

def padxy(ref, num):
    return place.padpos(board.FindFootprintByReference(ref), num)

# шина +5V вдоль нижнего края (1,0 мм), от F2 до F4; исток Q1 — к шине
YB = place.gu(261)      # 165,735: нижние площадки F1/F2
fuse_pads = {}
for ref in ("F1", "F2", "F3", "F4"):
    fp = board.FindFootprintByReference(ref)
    ps = sorted(fp.Pads(), key=lambda q: q.GetPosition().y)
    fuse_pads[ref] = [(q.GetPosition().x / 1e6, q.GetPosition().y / 1e6) for q in ps]
YB = fuse_pads["F2"][1][1]
YDIP = 177.5                                    # обход MagJack по самому краю
pre([fuse_pads["F2"][1], (27.5, YB), (27.5, YDIP), (49.0, YDIP), (49.0, YB), (78.0, YB)], "+5V", "F", PWR2)
for vx in (77.0, 78.0, 82.0, 83.0):                 # пересечение с VIN: шина ныряет на нижний слой (по 2 переходных с каждой стороны)
    pre_via(vx, YB, "+5V")
pre([(77.0, YB), (83.0, YB)], "+5V", "B", PWR2)
pre([(82.0, YB), (97.79, YB), (97.79, fuse_pads["F4"][1][1]), fuse_pads["F4"][1]], "+5V", "F", PWR2)
pre([fuse_pads["F3"][1], (97.79, fuse_pads["F3"][1][1]), (97.79, YB)], "+5V", "F", PWR2)
q1 = padxy("Q1", 2)
pre([q1, (72.0, q1[1]), (72.0, YB)], "+5V", "F", PWR2)
for ref in ("C101", "D1", "C102"):                      # накопитель, TVS, керамика — к шине +5V широкой дорожкой
    fp = board.FindFootprintByReference(ref)
    for q in fp.Pads():
        if q.GetNetname() == "+5V":
            x, y = q.GetPosition().x / 1e6, q.GetPosition().y / 1e6
            pre([(x, y), (x, YB)], "+5V", "F", PWR2)
# VIN: гнездо J18 -> сток Q1 (1,0 мм)
j18 = padxy("J18", 1); q7 = padxy("Q1", 7)
pre([j18, (80.0, j18[1]), (80.0, q7[1]), q7], "VIN", "F", PWR2)
# 5V_A: F1 -> верхний слой x = 2,54 до J1; 5V_B: F2 -> переходное -> нижний слой x = 1,905 до J5
pre([fuse_pads["F1"][0], (fuse_pads["F1"][0][0], 159.4), (2.54, 159.4), (2.54, place.HDR_Y0), padxy("J1", 1)], "5V_A", "F", PWR2)
pre_via(fuse_pads["F2"][0][0], fuse_pads["F2"][0][1], "5V_B")
pre([fuse_pads["F2"][0], (1.905, fuse_pads["F2"][0][1]), (1.905, place.HDR_Y0 + 4 * place.HDR_DY)], "5V_B", "B", PWR2)
# 5V_C: F3 -> верхний слой x = 97,79 до J9; 5V_D: F4 -> переходное -> нижний слой x = 98,42 до J13
pre([fuse_pads["F3"][0], (97.79, fuse_pads["F3"][0][1]), (97.79, place.HDR_Y0), padxy("J9", 1)], "5V_C", "F", PWR2)
pre_via(fuse_pads["F4"][0][0], fuse_pads["F4"][0][1], "5V_D")
pre([fuse_pads["F4"][0], (98.42, fuse_pads["F4"][0][1]), (98.42, place.HDR_Y0 + 4 * place.HDR_DY)], "5V_D", "B", PWR2)
VIA_TERMS = {}      # имя цепи -> список терминалов-переходных (обе стороны)
CORR_VIAS = []      # (x, y, nm, via, stub_track)
def pre_via2(x, y, nm):
    """переходное коридора: ячейка — за цепью, соседние ячейки доступны дорожкам"""
    v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRL))
    v.SetLayerPair(F, B); v.SetNet(net(nm)); board.Add(v)
    ix, iy = grid.cell(x, y)
    for L in (0, 1):
        grid.occ[L][grid.idx(ix, iy)] = nid(nm)
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        jx, jy = ix + dx, iy + dy
        if 0 <= jx < grid.nx and 0 <= jy < grid.ny:
            grid.via_ok[grid.idx(jx, jy)] = False
    for dy in (-1, 1):                     # выходы переходного вверх/вниз по нижнему слою — за цепью
        j = grid.idx(ix, iy + dy)
        if grid.occ[1][j] == 0:
            grid.occ[1][j] = nid(nm)
    VIA_TERMS.setdefault(nm, []).append((ix, iy, None))
    return v

def corridor_vias():
    n = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference(); fx = fp.GetPosition().x / 1e6
        is_res = ref.startswith("R") and ref[1:].isdigit() and int(ref[1:]) < 200 and min(abs(fx - RES_XL), abs(fx - RES_XR)) < 0.1
        is_buf = fp.GetValue() == "74LVC244A" and ref != "U13"
        if not (is_res or is_buf):
            continue
        left = fx < W / 2
        for q in fp.Pads():
            nm = q.GetNetname()
            if not nm:
                continue
            px, py = q.GetPosition().x / 1e6, q.GetPosition().y / 1e6
            if is_res:
                chip_side = (px > fx) if left else (px < fx)
                if chip_side:
                    vx = RES_XL + 3 * G if left else RES_XR - 3 * G
                elif nm.startswith("MIC") and "_" not in nm:          # MIC<n> к шлейфу — через нижний слой
                    vx = RES_XL - 3 * G if left else RES_XR + 3 * G
                else:
                    continue
            else:
                corridor_side = (px < fx) if left else (px > fx)
                if corridor_side:
                    vx = RES_XL + 5 * G if left else RES_XR - 5 * G
                else:                                                # выводы со стороны центра — переходное у края корпуса
                    vx = gu(58) if left else gu(98)
            iy = int(round(py / G)); vy = iy * G
            # отвод от площадки к переходному (не в PRE: это отдельный островок цепи)
            t = pcbnew.PCB_TRACK(board); t.SetStart(P(px, py)); t.SetEnd(P(vx, vy)); t.SetWidth(mm(TRK)); t.SetLayer(F); t.SetNet(net(nm)); board.Add(t)
            grid.block_rect(min(px, vx), min(py, vy), max(px, vx), max(py, vy), (0,), nid(nm), clr=0.33, via_clr=0.5)
            v = pre_via2(vx, vy, nm); n += 1
            CORR_VIAS.append((vx, vy, nm, v, t))
            # терминал площадки заменить терминалом переходного
            x1, y1, x2, y2 = pad_rect(q)
            cells = cells_in_rect(x1, y1, x2, y2)
            if cells:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                cells.sort(key=lambda c: (c[0] * G - cx) ** 2 + (c[1] * G - cy) ** 2)
                tcell = (cells[0][0], cells[0][1], 0)
                if tcell in terms.get(nm, []):
                    terms[nm].remove(tcell)
    for nm, lst in VIA_TERMS.items():
        terms.setdefault(nm, []).extend(lst)
    print("переходных в коридорах", n)
corridor_vias()

# ---------------------------------------------------------------- Ethernet: пары вручную, одним слоем, 45°
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
r1 = jpad("R1"); c301 = place.padpos(board.FindFootprintByReference("C301"), 1); r301 = place.padpos(board.FindFootprintByReference("R301"), 1)
d = r1[1] - c301[1]
eth_line("ETH_CT", [r1, (c301[0] + d, r1[1]), c301, (c301[0] - 0.94, c301[1] - 0.94), (c301[0] - 0.94, r301[1] + 0.94), r301], "F")
open(os.path.join(HERE, "eth_lengths.txt"), "w", encoding="utf-8").write(
    "\n".join("%s %.2f мм" % (k, v) for k, v in sorted(eth_len.items())) + "\n")
print("Ethernet: длины пар", {k: round(v, 1) for k, v in sorted(eth_len.items())})
# зона корпуса под MagJack — запрет для трассировщика (и земли): всё, кроме своих площадок
grid.block_rect(place.JACK_X - 4.0, place.JACK_Y - 2.6, place.JACK_X + 15.4, H, (0, 1), -1, clr=0.0, via_clr=0.3)
_c306 = place.padpos(board.FindFootprintByReference("C306"), 2); _r306 = place.padpos(board.FindFootprintByReference("R306"), 1)
grid.block_rect(_c306[0] - 0.9, _c306[1] - 1.3, _r306[0] + 0.6, place.JACK_Y + 2.5, (0, 1), -1, clr=0.0, via_clr=0.3)

# развязка буферов: площадка земли каждого C1..C13 — сразу на переходное к нижнему слою
for n in range(1, 14):
    fp = board.FindFootprintByReference("C%d" % n)
    cx, cy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    for q in fp.Pads():
        if q.GetNetname() == "GND":
            px, py = q.GetPosition().x / 1e6, q.GetPosition().y / 1e6
            vx = cx + 3 * G if px > cx else cx - 3 * G
            pre([(px, py), (vx, py)], "GND", "F", TRK)
            pre_via2(vx, py, "GND")

# земляные контакты вилок IDC: объединить дорожкой вдоль ряда (чтобы на полигон вышел любой из них)
def idc_gnd_bus(ref):
    fp = board.FindFootprintByReference(ref)
    pads = {int(p.GetNumber()): (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetNetname()) for p in fp.Pads()}
    ax, ay = pads[1][0], pads[1][1]; bx, by = pads[2][0], pads[2][1]
    ux, uy = (ax - bx) / 2.54, (ay - by) / 2.54          # от ряда B к ряду A (единичный)
    cx, cy = pads[3][0] - ax, pads[3][1] - ay            # шаг колонок (вектор 2,54)
    cols = sorted({(w + 1) // 2 for w, (x, y, n) in pads.items() if n == "GND"})
    def col_pos(c, row):
        base = pads[1] if row == "A" else pads[2]
        return (base[0] + (c - 1) * cx, base[1] + (c - 1) * cy)
    # магистраль на 1,27 снаружи ряда A, от первой до последней земляной колонки
    p0 = col_pos(cols[0], "A"); p1 = col_pos(cols[-1], "A")
    off = (ux * 1.27, uy * 1.27)
    pre([(p0[0] + off[0], p0[1] + off[1]), (p1[0] + off[0], p1[1] + off[1])], "GND", "F", TRK)
    for c in cols:
        wa, wb = 2 * c - 1, 2 * c
        pa, pb = col_pos(c, "A"), col_pos(c, "B")
        if pads[wa][2] == "GND":
            pre([pa, (pa[0] + off[0], pa[1] + off[1])], "GND", "F", TRK)
            if pads[wb][2] == "GND":
                pre([pb, pa], "GND", "F", TRK)
        elif pads[wb][2] == "GND":                        # только внутренний ряд: наискось в зазор и сквозь ряд A
            gx, gy = pb[0] + cx / 2 + ux * 1.27, pb[1] + cy / 2 + uy * 1.27
            pre([pb, (gx, gy), (gx + off[0] * 2, gy + off[1] * 2)], "GND", "F", TRK)
for ref in ("J19",):
    idc_gnd_bus(ref)

# земля справа от MagJack (между chassis-зоной и J26) — сшить с нижним слоем
for (vx, vy) in ((53.5, 160.0), (56.0, 162.0)):
    pre_via(vx, vy, "GND")

# 3V3_MIC: по низу — верхний слой y = 138,9 (нижний слой под ним свободен для пересечений), вверх вдоль краёв — нижний слой
Y3 = 138.9
pre([(3.81, Y3), (96.52, Y3)], "3V3_MIC", "F", PWR)
pre_via(3.81, Y3, "3V3_MIC"); pre_via(96.52, Y3, "3V3_MIC")
pre([(3.81, Y3), (3.175, Y3), (3.175, place.HDR_Y0 - 2.54), padxy("J1", 2)], "3V3_MIC", "B", PWR)
pre([(96.52, Y3), (96.52, place.HDR_Y0 + 2.54), padxy("J9", 2)], "3V3_MIC", "B", PWR)
t0 = time.time()
rt.freeze_base()
id2name = {v: k for k, v in netid.items()}
def route_one(nm, maxexp=1500000):
    pre_cells = PRE.get(nm, set())
    tl = [t for t in terms[nm] if (t[0], t[1], 0) not in pre_cells and (t[0], t[1], 1) not in pre_cells] or terms[nm][:1]
    cx = sum(a for a, b, _ in tl) / len(tl); cy = sum(b for a, b, _ in tl) / len(tl)
    tl = sorted(tl, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
    for ix, iy, L in tl:
        for LL in ((0, 1) if L is None else (L,)):
            i = grid.idx(ix, iy)
            if grid.occ[LL][i] in (0, nid(nm)):
                grid.occ[LL][i] = nid(nm)
    preset = set(PRE.get(nm, ()))
    if nm == "GND":
        preset |= set(rt.net_cells.get(nid(nm), ()))
    return rt.route_net(nid(nm), tl, width=width_of(nm), maxexp=maxexp, preset=preset)

# земля выводов вилок IDC — заранее, пока плата пустая: деревом к переходным развязки буферов
idc_gnd = []
for ref in ("J19", "J20", "J21"):
    fp = board.FindFootprintByReference(ref)
    for q in fp.Pads():
        if q.GetNetname() == "GND":
            ix, iy = grid.cell(q.GetPosition().x / 1e6, q.GetPosition().y / 1e6)
            idc_gnd.append((ix, iy, None))
queue = [n for n in names if n != 'GND' and n not in ETH_SKIP]      # земля — после всех перекладок; Ethernet — вручную
failed_final = []
iters = 0
ripped_count = {}
while queue and iters < 1400:
    nm = queue.pop(0); iters += 1
    rt.ripup(nid(nm))
    if route_one(nm):
        continue
    # перекладка: снять мешающие цепи вокруг неудачных терминалов, проложить заново, снятые — в конец очереди
    fails = [f for f in rt.fail if f[0] == nid(nm)]
    blk = set()
    for f in fails:
        blk |= rt.blockers(f[1], r=3)
    blk.discard(nid(nm))
    blk = [b for b in blk if ripped_count.get(b, 0) < 14 and len(terms[id2name[b]]) <= 10]
    if not blk:
        failed_final.append(nm); continue
    for b in blk:
        rt.ripup(b); ripped_count[b] = ripped_count.get(b, 0) + 1
    rt.ripup(nid(nm))
    ok = route_one(nm)
    for b in blk:
        if id2name[b] not in queue:
            queue.append(id2name[b])
    if not ok:
        queue.append(nm) if ripped_count.get(nid(nm), 0) < 14 else failed_final.append(nm)
        ripped_count[nid(nm)] = ripped_count.get(nid(nm), 0) + 1
# остаток очереди (если упёрлись в предел итераций) — проложить без перекладки
for nm in queue:
    rt.ripup(nid(nm)); route_one(nm)
# финальные проходы: все неудачные цепи пробуем ещё раз (к концу пути часто освобождаются)
for _pass in range(4):
    redo = sorted({id2name[nd] for nd, t, _ in rt.fail} | set(failed_final))
    if not redo:
        break
    failed_final = []
    for nm in redo:
        rt.ripup(nid(nm))
        if not route_one(nm, maxexp=3000000):
            failed_final.append(nm)
    print("финальный проход %d: осталось %d" % (_pass + 1, len(failed_final)))
# земля: деревом по остаткам свободного места (остальное доберут полигоны и сшивающие переходные)
gnd_ok = route_one("GND", maxexp=3000000)        # без снятия: ранняя часть дерева остаётся
print("земля: проложена полностью" if gnd_ok else "земля: часть площадок — только через полигоны")
# непроложенные площадки земли: переходное в ближайшей свободной ячейке + короткая дорожка к нему
gnd_fix = 0
for nd, t, why in list(rt.fail):
    if id2name[nd] != "GND":
        continue
    ix0, iy0, L0 = t
    cands = sorted(((abs(dx) + abs(dy), ix0 + dx, iy0 + dy) for dx in range(-8, 9) for dy in range(-8, 9) if (dx or dy)), key=lambda c: c[0])
    for _, jx, jy in cands:
        if not (0 <= jx < grid.nx and 0 <= jy < grid.ny):
            continue
        j = grid.idx(jx, jy)
        if not grid.via_ok[j] or grid.occ[0][j] != 0 or grid.occ[1][j] != 0:
            continue
        # на нижнем слое вокруг должна быть открытая земля (радиус 2 ячейки свободен), иначе переходное попадёт в островок
        if any(grid.occ[1][grid.idx(jx + ex, jy + ey)] not in (0, nid("GND")) for ex in range(-2, 3) for ey in range(-2, 3)
               if 0 <= jx + ex < grid.nx and 0 <= jy + ey < grid.ny):
            continue
        v = pre_via2(jx * G, jy * G, "GND")
        rt.fail = [f for f in rt.fail if f[1] != t]
        if rt.route_net(nid("GND"), [(jx, jy, None), t], width=TRK, maxexp=200000):
            gnd_fix += 1
            break
        rt.fail = [f for f in rt.fail if f[1] != t]
        board.Remove(v)                                   # не вышло — переходное убрать, ячейки освободить
        for L in (0, 1):
            if grid.occ[L][j] == nid("GND"):
                grid.occ[L][j] = 0
print("земля: доработано площадок переходными", gnd_fix)
bad = sorted({id2name[nd] for nd, t, _ in rt.fail if id2name[nd] != "GND"} | set(failed_final))
print("трассировка %.0f с, итераций %d, не удалось: %d %s" % (time.time() - t0, iters, len(bad), bad[:20]))

# ---------------------------------------------------------------- уборка неиспользованных переходных коридора
ends_b = set(); ends_f = set()
for (x1, y1, x2, y2, L, nd, w) in rt.tracks:
    for (x, y) in ((x1, y1), (x2, y2)):
        (ends_b if L == 1 else ends_f).add((round(x, 2), round(y, 2)))
n_rm = 0
for (vx, vy, nm, v, t) in CORR_VIAS:
    k = (round(vx, 2), round(vy, 2))
    if k not in ends_b:
        board.Remove(v); n_rm += 1
        if k not in ends_f:
            board.Remove(t)
print("убрано лишних переходных", n_rm)

# ---------------------------------------------------------------- перенос в плату
for (x1, y1, x2, y2, L, nd, w) in rt.tracks:
    add_track(x1, y1, x2, y2, L, id2name[nd], w)
for (x, y, nd) in rt.vias:
    v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRL))
    v.SetLayerPair(F, B); v.SetNet(net(id2name[nd])); board.Add(v)
for (x1, y1, x2, y2, L, nm) in stubs:
    add_track(x1, y1, x2, y2, L, nm, TRK)

# ---------------------------------------------------------------- сшивающие переходные земли
nst = 0
for ix in range(4, grid.nx - 4, 12):
    for iy in range(4, grid.ny - 4, 12):
        i = grid.idx(ix, iy)
        if grid.via_ok[i] and grid.occ[0][i] == 0 and grid.occ[1][i] == 0:
            ok = True
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    j = grid.idx(ix + dx, iy + dy)
                    if grid.occ[0][j] not in (0,) or grid.occ[1][j] not in (0,):
                        ok = False
            if ok:
                v = pcbnew.PCB_VIA(board); v.SetPosition(P(ix * G, iy * G)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRL))
                v.SetLayerPair(F, B); v.SetNet(net("GND")); board.Add(v); nst += 1
print("сшивающих переходных", nst)

# ---------------------------------------------------------------- полигоны земли
def zone(points, netname, layer):
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(net(netname)); z.Outline().NewOutline()
    for (x, y) in points:
        z.Outline().Append(mm(x), mm(y))
    z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.5)); z.SetZoneName(netname + ("_F" if layer == F else "_B"))
    try:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    except Exception:
        pass
    board.Add(z)
    return z
for L in (F, B):
    zone([(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)], "GND", L)
JX, JY = place.JACK_X, place.JACK_Y
c306 = place.padpos(board.FindFootprintByReference("C306"), 2); r306 = place.padpos(board.FindFootprintByReference("R306"), 1)
z = zone([(JX - 3.9, JY - 2.3), (JX + 15.3, JY - 2.3), (JX + 15.3, 176.3), (JX - 3.9, 176.3)], "CHASSIS", B)
z.SetAssignedPriority(1)
z = zone([(JX - 3.9, JY - 2.3), (c306[0] - 0.9, JY - 2.3), (c306[0] - 0.9, c306[1] - 1.1), (r306[0] + 0.6, c306[1] - 1.1),
          (r306[0] + 0.6, JY + 2.5), (JX + 15.3, JY + 2.5), (JX + 15.3, 176.3), (JX - 3.9, 176.3)], "CHASSIS", F)   # c306 = площадка 2 (CHASSIS)
z.SetAssignedPriority(1)
for fp in board.GetFootprints():
    if fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE:
        fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

# ---------------------------------------------------------------- скос прямых углов (45°)
def merge_collinear():
    """объединить последовательные коллинеарные отрезки одной цепи/слоя (после трассировщика их нет, но после скоса — проверка)."""
    pass

def miter_corners(cmax=0.3, cmax_pwr=0.45):
    def key(v):
        return (round(v.x / 1e6, 2), round(v.y / 1e6, 2))
    vias = {key(t.GetPosition()) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"}
    pads = set()
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            pads.add(key(pd.GetPosition()))
    segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    ends = {}
    for t in segs:
        for e in (0, 1):
            ends.setdefault((key(t.GetStart() if e == 0 else t.GetEnd()), t.GetLayer()), []).append((t, e))
    n_done = 0
    for (k, layer), lst in list(ends.items()):
        if len(lst) != 2 or k in vias or k in pads:
            continue
        (t1, e1), (t2, e2) = lst
        if t1.GetNetCode() != t2.GetNetCode():
            continue
        def far(t, e):
            return t.GetEnd() if e == 0 else t.GetStart()
        c0 = t1.GetStart() if e1 == 0 else t1.GetEnd()
        a, b = far(t1, e1), far(t2, e2)
        d1 = (a.x - c0.x, a.y - c0.y); d2 = (b.x - c0.x, b.y - c0.y)
        L1, L2 = math.hypot(*d1), math.hypot(*d2)
        if L1 < 1 or L2 < 1:
            continue
        cosang = (d1[0] * d2[0] + d1[1] * d2[1]) / (L1 * L2)
        if abs(cosang) > 0.05:
            continue
        w = min(t1.GetWidth(), t2.GetWidth())
        c = min(mm(cmax_pwr if w >= mm(0.45) else cmax), L1 / 2, L2 / 2)
        p1 = VECTOR2I(int(c0.x + d1[0] / L1 * c), int(c0.y + d1[1] / L1 * c))
        p2 = VECTOR2I(int(c0.x + d2[0] / L2 * c), int(c0.y + d2[1] / L2 * c))
        if e1 == 0:
            t1.SetStart(p1)
        else:
            t1.SetEnd(p1)
        if e2 == 0:
            t2.SetStart(p2)
        else:
            t2.SetEnd(p2)
        d = pcbnew.PCB_TRACK(board); d.SetStart(p1); d.SetEnd(p2); d.SetWidth(w); d.SetLayer(t1.GetLayer())
        d.SetNetCode(t1.GetNetCode()); board.Add(d); n_done += 1
    return n_done

n_miter = miter_corners()
# оставшиеся прямые стыки двух дорожек (без via/площадки) — в журнал
def right_angles_left():
    def key(v):
        return (round(v.x / 1e6, 2), round(v.y / 1e6, 2))
    vias = {key(t.GetPosition()) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"}
    pads = set()
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            pads.add(key(pd.GetPosition()))
    ends = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK":
            for e in (0, 1):
                ends.setdefault((key(t.GetStart() if e == 0 else t.GetEnd()), t.GetLayer()), []).append((t, e))
    out = []
    for (k, layer), lst in ends.items():
        if len(lst) != 2 or k in vias or k in pads:
            continue
        (t1, e1), (t2, e2) = lst
        c0 = t1.GetStart() if e1 == 0 else t1.GetEnd()
        a = t1.GetEnd() if e1 == 0 else t1.GetStart(); b = t2.GetEnd() if e2 == 0 else t2.GetStart()
        d1 = (a.x - c0.x, a.y - c0.y); d2 = (b.x - c0.x, b.y - c0.y)
        L1, L2 = math.hypot(*d1), math.hypot(*d2)
        if L1 and L2 and abs((d1[0] * d2[0] + d1[1] * d2[1]) / (L1 * L2)) < 0.05:
            out.append(k)
    return out
left = right_angles_left()
open(os.path.join(HERE, "miter_log.txt"), "w", encoding="utf-8").write(
    "скошено углов: %d" % n_miter + chr(10) + "осталось прямых стыков двух дорожек: %d" % len(left) + chr(10) + chr(10).join("%.2f %.2f" % k for k in left) + chr(10))
print("скошено углов", n_miter, "осталось прямых", len(left))
board.SetFileName(os.path.abspath(OUT))
pcbnew.SaveBoard(os.path.abspath(OUT), board)
open(os.path.join(HERE, "route_log.txt"), "w", encoding="utf-8").write(
    "цепей %d, не удалось %d: %s\nдорожек %d, переходных %d\n" % (len(terms), len(bad), bad, len(rt.tracks), len(rt.vias)))
# BOM для схемы и фабрики
import json
json.dump(place.PARTS, open(os.path.join(HERE, "parts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", OUT)

import pickle
pickle.dump({"occ": grid.occ, "via_ok": grid.via_ok, "vcost": grid.vcost, "nx": grid.nx, "ny": grid.ny, "id2": id2name,
             "fail": rt.fail}, open(os.path.join(HERE, "grid_state.pkl"), "wb"))
# отладка неудач
id2 = id2name
for nd, (ix, iy, L), why in rt.fail:
    print("FAIL", id2[nd], why, "cell", round(ix * G, 2), round(iy * G, 2), "L", L)
