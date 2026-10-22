# -*- coding: utf-8 -*-
"""После заливки зон: куски земли на верхнем слое без переходного/выводной площадки — сшить переходным
с нижним слоем в свободном месте внутри куска. Запуск: python KiCad -I stitch_fix.py (плата с залитыми зонами)."""
import os, math
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "..", "dpaa_dist.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
G = 0.635
VIA_D, VIA_DRL = 0.6, 0.3

def segdist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

tracks = []
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        tracks.append((t.GetStart().x / 1e6, t.GetStart().y / 1e6, t.GetEnd().x / 1e6, t.GetEnd().y / 1e6, t.GetWidth() / 1e6, t.GetNetname(), t.GetLayer()))
    else:
        p = t.GetPosition(); tracks.append((p.x / 1e6, p.y / 1e6, p.x / 1e6, p.y / 1e6, t.GetWidth(pcbnew.F_Cu) / 1e6, t.GetNetname(), -1))
pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        m_ = 0.7 if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else 0.0        # NPTH: отверстие-отверстие >= 0,5
        pads.append((bb.GetLeft() / 1e6 - m_, bb.GetTop() / 1e6 - m_, bb.GetRight() / 1e6 + m_, bb.GetBottom() / 1e6 + m_, p.GetNetname()))

# растр занятости: ячейки сетки 0,635 вблизи дорожек/площадок (запас 0,55 от оси дорожки + полуширина)
blocked = set()
def mark(x, y, r):
    for ix in range(int((x - r) / G), int((x + r) / G) + 2):
        for iy in range(int((y - r) / G), int((y + r) / G) + 2):
            if math.hypot(ix * G - x, iy * G - y) <= r:
                blocked.add((ix, iy))
for (x1, y1, x2, y2, w, nm, L) in tracks:
    if nm == "GND" and L != -1:
        continue                                   # своя земля зазора не требует
    r = 0.55 + w / 2
    n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 0.3))
    for k in range(n + 1):
        mark(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n, r)
for (l, t, rr, bt, nm) in pads:
    if nm == "GND" and (rr - l) < 3.0:
        continue                                   # своя SMD-площадка земли — можно рядом
    for ix in range(int((l - 0.7) / G), int((rr + 0.7) / G) + 2):
        for iy in range(int((t - 0.7) / G), int((bt + 0.7) / G) + 2):
            x, y = ix * G, iy * G
            if max(l - x, 0, x - rr) ** 2 + max(t - y, 0, y - bt) ** 2 <= 0.65 ** 2:
                blocked.add((ix, iy))
def free(x, y, r=0.55):
    return (int(round(x / G)), int(round(y / G))) not in blocked

zf = zb = None
for z in b.Zones():
    if z.GetNetname() == "GND" and z.GetLayer() == F and z.GetAssignedPriority() == 0:
        zf = z
    if z.GetNetname() == "GND" and z.GetLayer() == B and z.GetAssignedPriority() == 0:
        zb = z
vias = [t.GetPosition() for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
tht = [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
pb = zb.GetFilledPolysList(B)
n_add = 0
for L, z in ((F, zf),):
    ps = z.GetFilledPolysList(L)
    other = zb.GetFilledPolysList(B) if L == F else zf.GetFilledPolysList(F)
    others = []
    for j in range(other.OutlineCount()):
        oo = other.Outline(j); ob = oo.BBox()
        others.append((ob.GetLeft(), ob.GetTop(), ob.GetRight(), ob.GetBottom(), oo))
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        if any(o.PointInside(v) for v in vias) or any(o.PointInside(v) for v in tht) or any(o.PointInside(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1))) for (x1, y1, x2, y2, w, nm, L) in tracks if nm == 'GND' and L == F):
            continue
        bb = o.BBox()
        placed = False
        for iy in range(int(bb.GetTop() / 1e6 / G), int(bb.GetBottom() / 1e6 / G) + 1):
            for ix in range(int(bb.GetLeft() / 1e6 / G), int(bb.GetRight() / 1e6 / G) + 1):
                x, y = ix * G, iy * G
                pt = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
                if not o.PointInside(pt):
                    continue
                # с другой стороны тоже должна быть земля
                ok_other = any(l <= pt.x <= r_ and t <= pt.y <= bt and oo.PointInside(pt) for (l, t, r_, bt, oo) in others)
                if free(x, y):
                    mark(x, y, 0.9)
                    v = pcbnew.PCB_VIA(b); v.SetPosition(pt); v.SetWidth(pcbnew.FromMM(VIA_D)); v.SetDrill(pcbnew.FromMM(VIA_DRL))
                    v.SetLayerPair(F, B); v.SetNet(b.FindNet("GND")); b.Add(v); n_add += 1; placed = True
                    tracks.append((x, y, x, y, VIA_D, "GND", -1))
                    break
            if placed:
                break
        if not placed:
            print("не нашёл места для переходного в куске", "F" if L == F else "B", round(bb.GetLeft() / 1e6, 1), round(bb.GetTop() / 1e6, 1))
pcbnew.SaveBoard(PCB, b)
print("добавлено сшивающих переходных", n_add)
