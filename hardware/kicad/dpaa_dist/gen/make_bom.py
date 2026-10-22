# -*- coding: utf-8 -*-
"""BOM и файл координат в формате JLCPCB (и общий CSV) из платы."""
import os, csv, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
import pcbnew
board = pcbnew.LoadBoard(os.path.join(ROOT, "dpaa_dist.kicad_pcb"))
# подбор покупных наименований (LCSC — ориентир, проверить при заказе)
PARTNO = {
 ("74LVC244A", "SOIC-20W"): ("SN74LVC244ADWR (TI) / 74LVC244AD (Nexperia)", "C7936"),
 ("PCM5102A", "TSSOP-20"): ("PCM5102APWR (TI)", "C107668"),
 ("TDA1308", "SOIC-8"): ("TDA1308T/N2 (NXP)", "C77218"),
 ("AO4407A", "SOIC-8"): ("AO4407A (Alpha & Omega)", "C77770"),
 ("AP2112K-3.3", "SOT-23-5"): ("AP2112K-3.3TRG1 (Diodes)", "C51118"),
 ("SMBJ5.0A", "D_SMB"): ("SMBJ5.0A (Littelfuse/любой)", "C113978"),
 ("PTC 1.5A", "Fuse_1812"): ("PTC 1812 1,5 A 6 В (MF-MSMF150 или аналог)", "C70069"),
 ("1000u", "CP_Radial_D10"): ("1000 мкФ 10 В, Ø10 мм, шаг 5 мм", "C3326"),
 ("220u", "CP_Radial_D6.3"): ("220 мкФ 6,3 В (10 В), Ø6,3 мм, шаг 2,5 мм", "C2838"),
 ("600R", "L_0805"): ("феррит 0805 600 Ом/100 МГц, 2 А", "C1017"),
 ("LED", "LED_0603"): ("светодиод 0603 зелёный", "C72043"),
 ("кнопка", "SW_Push"): ("кнопка тактовая 6x6x5 SMD", "C318884"),
 ("2x6", "PinHeader_2x06"): ("штыревая гребёнка 2x6, 2,54 мм, прямая", "C2337"),
 ("IDC 2x15", "IDC-Header_2x15"): ("вилка IDC 2x15 (BH-30) с ключом, 2,54 мм", "C2337"),
 ("ESP32", "PinHeader_1x03"): ("штыревая гребёнка 1x3, 2,54 мм", "C2337"),
 ("RJ45", "RJ45"): ("гнездо RJ45 8P8C без магнетиков (Amphenol 54602-908 или аналог)", "C86580"),
 ("5.5/2.1", "BarrelJack"): ("гнездо DC 5,5/2,1 мм (DC-005)", "C16214"),
 ("3.5mm", "Jack_3.5mm"): ("гнездо 3,5 мм стерео, угловое (SJ1-3523N / PJ-320)", "C145816"),
 ("RB1-125B8G1A", "RJ45_UDE"): ("RJ45 MagJack 1000BASE-T UDE RB1-125B8G1A", "C363353"),
 ("1n 2kV", "C_1812"): ("конденсатор 1812 1 нФ 2 кВ X7R", "C135917"),
 ("1M", "R_0603"): ("резистор 0603 1 МОм 1%", ""),
 ("0R DNP", "R_0603"): ("резистор 0603 0 Ом — НЕ УСТАНАВЛИВАТЬ (DNP)", ""),
}
def partno(value, fpname):
    for (v, f), (name, lcsc) in PARTNO.items():
        if value == v and f in fpname:
            return name, lcsc
    if fpname.startswith("R_0603"):
        return ("резистор 0603 %s 1%%" % value, "")
    if fpname.startswith("C_0603"):
        return ("конденсатор 0603 %s X7R 25 В" % value, "")
    if fpname.startswith("C_0805"):
        return ("конденсатор 0805 %s X7R/X5R 16 В" % value, "")
    return (value, "")

rows = []
grp = collections.OrderedDict()
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref.startswith("H") or fp.IsDNP():
        continue
    fpname = fp.GetFPID().GetLibItemName().wx_str() if hasattr(fp.GetFPID().GetLibItemName(), "wx_str") else str(fp.GetFPID().GetLibItemName())
    val = fp.GetValue()
    key = (val, fpname)
    grp.setdefault(key, []).append(ref)
    pos = fp.GetPosition()
    rows.append((ref, val, fpname, pos.x / 1e6, -pos.y / 1e6, fp.GetOrientationDegrees(), "top" if fp.GetLayer() == pcbnew.F_Cu else "bottom", fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE))

def refsort(r):
    import re
    m = re.match(r"([A-Z]+)(\d+)", r); return (m.group(1), int(m.group(2))) if m else (r, 0)
with open(os.path.join(ROOT, "fab", "dpaa_dist_bom_jlcpcb.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fpname), refs in grp.items():
        name, lcsc = partno(val, fpname)
        w.writerow([val, ",".join(sorted(refs, key=refsort)), fpname, lcsc])
with open(os.path.join(ROOT, "fab", "dpaa_dist_bom.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["Поз.", "Кол-во", "Значение", "Корпус (KiCad)", "Наименование для заказа", "LCSC (ориентир)"])
    for (val, fpname), refs in grp.items():
        name, lcsc = partno(val, fpname)
        w.writerow([",".join(sorted(refs, key=refsort)), len(refs), val, fpname, name, lcsc])
# координаты: JLCPCB (Designator, Mid X, Mid Y, Layer, Rotation) — только SMD
with open(os.path.join(ROOT, "fab", "dpaa_dist_cpl_jlcpcb.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for (ref, val, fpname, x, y, rot, side, tht) in sorted(rows, key=lambda r: refsort(r[0])):
        if tht:
            continue
        w.writerow([ref, "%.3fmm" % x, "%.3fmm" % y, side, "%.1f" % rot])
with open(os.path.join(ROOT, "fab", "dpaa_dist_pos.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["Ref", "Val", "Package", "PosX_mm", "PosY_mm", "Rot", "Side", "THT"])
    for r in sorted(rows, key=lambda r: refsort(r[0])):
        w.writerow([r[0], r[1], r[2], "%.3f" % r[3], "%.3f" % r[4], "%.1f" % r[5], r[6], "да" if r[7] else ""])
print("BOM: позиций", len(grp), "компонентов", len(rows), "SMD", sum(1 for r in rows if not r[7]))
