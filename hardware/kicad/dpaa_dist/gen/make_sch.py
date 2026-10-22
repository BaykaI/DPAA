# -*- coding: utf-8 -*-
"""Схема KiCad для распределительной платы DPAA, строится из платы (dpaa_dist.kicad_pcb):
каждый корпус — прямоугольный символ с номерами выводов как у посадочного места, цепи — глобальные метки на выводах.
Запуск: "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" -I make_sch.py"""
import os, sys, uuid, json
HERE = os.path.dirname(os.path.abspath(__file__))
import pcbnew

PCB = os.path.join(HERE, "..", "dpaa_dist.kicad_pcb")
OUT = os.path.join(HERE, "..", "dpaa_dist.kicad_sch")
board = pcbnew.LoadBoard(PCB)

def U():
    return str(uuid.uuid4())

# ---------------------------------------------------------------- сбор компонентов
comps = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref.startswith("H"):
        continue
    pads = []
    for p in fp.Pads():
        num = p.GetNumber()
        if not num:
            continue
        if any(q[0] == num for q in pads):
            continue
        pads.append((num, p.GetNetname()))
    comps.append({"ref": ref, "value": fp.GetValue(), "fp": str(fp.GetFPID().GetUniStringLibId()), "pads": pads,
                  "desc": ""})
parts = {r: d for r, v, f, d in json.load(open(os.path.join(HERE, "parts.json"), encoding="utf-8"))}
for c in comps:
    c["desc"] = parts.get(c["ref"], "")

# ---------------------------------------------------------------- имена выводов
PIN_NAMES = {
 "74LVC244A": {"1": "~OE1", "19": "~OE2", "10": "GND", "20": "VCC", "2": "1A1", "4": "1A2", "6": "1A3", "8": "1A4",
               "11": "2A1", "13": "2A2", "15": "2A3", "17": "2A4", "18": "1Y1", "16": "1Y2", "14": "1Y3", "12": "1Y4",
               "9": "2Y1", "7": "2Y2", "5": "2Y3", "3": "2Y4"},
 "PCM5102A": {"1": "CAPP", "2": "CAPM", "3": "CPGND", "4": "VNEG", "5": "OUTL", "6": "OUTR", "7": "AGND", "8": "AVDD",
              "9": "LDOO", "10": "DEMP", "11": "FLT", "12": "SCK", "13": "BCK", "14": "DIN", "15": "LRCK", "16": "FMT",
              "17": "XSMT", "18": "DGND", "19": "DVDD", "20": "CPVDD"},
 "TDA1308": {"1": "OUTA", "2": "-INA", "3": "+INA", "4": "VSS", "5": "+INB", "6": "-INB", "7": "OUTB", "8": "VDD"},
 "AO4407A": {"1": "S", "2": "S", "3": "S", "4": "G", "5": "D", "6": "D", "7": "D", "8": "D"},
 "AP2112K-3.3": {"1": "VIN", "2": "GND", "3": "EN", "4": "NC", "5": "VOUT"},
 "5.5/2.1": {"1": "+", "2": "-", "3": "SW"},
 "3.5mm": {"T": "TIP", "R": "RING", "S": "SLEEVE"},
 "LED": {"1": "K", "2": "A"},
 "RB1-125B8G1A": {"R1": "CT", "R2": "TD1+", "R3": "TD1-", "R4": "TD2+", "R5": "TD2-", "R6": "TD3+", "R7": "TD3-", "R8": "TD4+",
                  "R9": "TD4-", "R10": "BS GND", "SH": "SHIELD", "L1": "LED Y-", "L2": "LED Y+", "L3": "LED G-", "L4": "LED G+"},
 "SMBJ5.0A": {"1": "K", "2": "A"},
}
# подписи контактов гребёнок элементов и шлейфов
J_EL = {"1": "+5V", "2": "+3V3 mic", "3": "GND", "4": "GND", "5": "BCLK amp", "6": "SCK mic", "7": "LRC amp",
        "8": "WS mic", "9": "DIN amp", "10": "SD mic", "11": "GND", "12": "GND (L/R)"}
EL_SIDE = {"1": "L", "3": "L", "5": "L", "7": "L", "9": "L", "11": "L"}

def pin_layout(c):
    """-> список (num, name, side) и размеры символа."""
    v = c["value"]; ref = c["ref"]; pads = c["pads"]
    names = PIN_NAMES.get(v, {})
    if ref.startswith("J") and ref not in ("J17", "J18", "J25", "J26", "J27", "J29"):
        out = []
        for num, nn in pads:
            nm = J_EL.get(num, "") if ref not in ("J19", "J20", "J21") else ""
            out.append((num, nm, "L" if int(num) % 2 == 1 else "R"))
        return out
    if len(pads) == 2 or ref.startswith(("R", "C", "F", "FB", "LED", "D", "SW")):
        return [(pads[0][0], names.get(pads[0][0], ""), "L"), (pads[1][0], names.get(pads[1][0], ""), "R")]
    n = len(pads)
    half = (n + 1) // 2
    def key(p):
        try:
            return int(p[0])
        except ValueError:
            return 0
    ps = sorted(pads, key=key)
    return [(num, names.get(num, ""), "L" if i < half else "R") for i, (num, nn) in enumerate(ps)]

# ---------------------------------------------------------------- генерация символов (прямоугольник + выводы)
P = 2.54
def sym_def(name, layout, width):
    nl = [p for p in layout if p[2] == "L"]; nr = [p for p in layout if p[2] == "R"]
    h = max(len(nl), len(nr)) * P + P
    s = ['(symbol "dpaa:%s" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)' % name,
         '(property "Reference" "U" (at 0 %.2f 0) (effects (font (size 1.27 1.27))))' % (h / 2 + 1.5),
         '(property "Value" "%s" (at 0 %.2f 0) (effects (font (size 1.27 1.27))))' % (name, -h / 2 - 1.5),
         '(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
         '(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
         '(symbol "%s_0_1" (rectangle (start %.2f %.2f) (end %.2f %.2f) (stroke (width 0.254) (type default)) (fill (type background))))' % (name, -width / 2, h / 2, width / 2, -h / 2),
         '(symbol "%s_1_1"' % name]
    pins = {}
    for side, lst in (("L", nl), ("R", nr)):
        for i, (num, nm, _) in enumerate(lst):
            y = h / 2 - P - i * P
            if side == "L":
                x, rot = -width / 2 - P, 0
            else:
                x, rot = width / 2 + P, 180
            pins[num] = (x, y)
            s.append('(pin passive line (at %.2f %.2f %d) (length %.2f) (name "%s" (effects (font (size 1.0 1.0)))) (number "%s" (effects (font (size 1.0 1.0)))))'
                     % (x, y, rot, P, nm or "~", num))
    s.append(')'); s.append(')')
    return "\n".join(s), pins, h

# ---------------------------------------------------------------- размещение на листе A2 (594 x 420)
SHEET_W, SHEET_H = 841.0, 594.0
groups = {}
for c in comps:
    r = c["ref"]
    if r.startswith("U") and c["value"] == "74LVC244A":
        g = "buf"
    elif r in ("U31", "U32") or r.startswith("C3") or r.startswith("C4") or r.startswith("R4") or r in ("J26", "J27"):
        g = "audio"
    elif r.startswith("J") and r not in ("J17", "J18", "J20", "J21", "J25"):
        g = "elem"
    elif r in ("J20", "J21", "J17", "J25", "SW1", "R201", "R202", "R203", "R204", "R205", "R206"):
        g = "fpga"
    elif r in ("J19", "J29", "C301", "R301", "C306", "R306"):
        g = "eth"
    elif r.startswith("R") and len(r) <= 4 and r[1:].isdigit() and int(r[1:]) < 200:
        g = "elem"
    elif r.startswith("C") and r[1:].isdigit() and int(r[1:]) <= 13:
        g = "buf"
    else:
        g = "power"
    groups.setdefault(g, []).append(c)

def refkey(c):
    r = c["ref"]
    import re
    m = re.match(r"([A-Z]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)

sym_defs = {}
instances = []     # (c, name, pins, x, y)
labels = []        # (x, y, rot, net)
nocon = []         # (x, y)
texts = []

def place_group(cs, x0, y0, x1, colw):
    """колонками сверху вниз."""
    x, y = x0, y0
    maxh = 0
    for c in sorted(cs, key=refkey):
        layout = pin_layout(c)
        w = 15.24 if len(layout) > 2 else 7.62
        if c["ref"].startswith("J"):
            w = 20.32
        name = "%s_%s" % (c["value"].replace(" ", "_").replace("/", "_"), len(layout)) if len(layout) > 2 else c["value"].replace(" ", "_").replace("/", "_") + "_2"
        name = name.replace('"', '')
        key = (name, tuple(layout))
        if name not in sym_defs:
            sym_defs[name] = sym_def(name, layout, w)
        d, pins, h = sym_defs[name]
        if y + h + 8 > SHEET_H - 20:
            y = y0; x += colw
        cx, cy = x + colw / 2, y + h / 2 + 4
        instances.append((c, name, pins, cx, cy, layout))
        y += h + 10
    return x + colw

def snap(v):
    return round(v / 1.27) * 1.27

X = 20.0
X = place_group(groups["elem"], X, 25, 0, 48)
X = place_group(groups["buf"], X + 4, 25, 0, 50)
X = place_group(groups["fpga"], X + 4, 25, 0, 52)
X = place_group(groups["audio"], X + 4, 25, 0, 48)
X = place_group(groups["power"], X + 4, 25, 0, 48)
X = place_group(groups["eth"], X + 4, 25, 0, 52)

# ---------------------------------------------------------------- вывод файла
out = ['(kicad_sch (version 20250114) (generator "dpaa_gen") (generator_version "10.0") (uuid "%s") (paper "A1")' % U(),
       '(title_block (title "DPAA — распределительная плата (A3)") (date "2026-10-21") (rev "1") (company "DPAA"))',
       '(lib_symbols']
for name, (d, pins, h) in sym_defs.items():
    out.append(d)
out.append(')')
for (c, name, pins, cx, cy, layout) in instances:
    cx, cy = snap(cx), snap(cy)
    sid = U()
    out.append('(symbol (lib_id "dpaa:%s") (at %.2f %.2f 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "%s")' % (name, cx, cy, sid))
    d, pins2, h = sym_defs[name]
    out.append('(property "Reference" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27))))' % (c["ref"], cx, cy - h / 2 - 1.5))
    out.append('(property "Value" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27))))' % (c["value"], cx, cy + h / 2 + 1.5))
    out.append('(property "Footprint" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) hide))' % (c["fp"], cx, cy))
    out.append('(property "Datasheet" "~" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) hide))' % (cx, cy))
    out.append('(property "Description" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) hide))' % (c["desc"].replace('"', ''), cx, cy))
    for num, nn in c["pads"]:
        out.append('(pin "%s" (uuid "%s"))' % (num, U()))
    out.append('(instances (project "dpaa_dist" (path "/" (reference "%s") (unit 1))))' % c["ref"])
    out.append(')')
    netmap = dict(c["pads"])
    for num, nm, side in layout:
        px, py = pins[num]
        # вывод символа: в схеме y вниз, в символе y вверх -> инвертировать
        x, y = cx + px, cy - py
        netname = netmap.get(num, "")
        if not netname:
            nocon.append((x, y))
        else:
            rot = 180 if side == "L" else 0
            labels.append((x, y, rot, netname))
for (x, y, rot, netname) in labels:
    out.append('(global_label "%s" (shape passive) (at %.2f %.2f %d) (fields_autoplaced yes) (effects (font (size 1.0 1.0)) (justify %s)) (uuid "%s")'
               '(property "Intersheetrefs" "${INTERSHEET_REFS}" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) hide)))'
               % (netname, x, y, rot, "right" if rot == 180 else "left", U(), x, y))
for (x, y) in nocon:
    out.append('(no_connect (at %.2f %.2f) (uuid "%s"))' % (x, y, U()))
out.append('(text "Цепи соединены глобальными метками. Элементы J1–J16: нечётный ряд — усилитель MAX98357A, чётный — микрофон ICS-43434.\\nJ20 = гребёнка P2, J21 = P3 платы расширения Colorlight i9 (шлейфы IDC 2x15, контакт в контакт)." (at 20 585 0) (effects (font (size 2.5 2.5)) (justify left bottom)) (uuid "%s"))' % U())
out.append('(sheet_instances (path "/" (page "1")))')
out.append(')')
txt = "\n".join(out)
# путь корневого листа = uuid схемы
root = txt.split('(uuid "')[1].split('"')[0]
txt = txt.replace('(path "/" (reference', '(path "/%s" (reference' % root)
open(OUT, "w", encoding="utf-8").write(txt)
print("saved", OUT, "symbols", len(sym_defs), "instances", len(instances), "labels", len(labels), "nc", len(nocon))
