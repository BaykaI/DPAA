# -*- coding: utf-8 -*-
"""Простой трассировщик по сетке для двухслойной платы (A*, шаг 0,635 мм).
Слой F — предпочтительно горизонтальные дорожки, слой B — вертикальные.
Цепи трассируются по очереди, каждая — деревом (контакт за контактом к уже проложенной части).
Результат: список отрезков и переходных отверстий в миллиметрах."""
import heapq, math

G = 0.635            # шаг сетки, мм
INF = 10 ** 9

class Grid:
    def __init__(self, w, h, margin=1.5):
        self.w, self.h = w, h
        self.nx = int(w / G) + 1
        self.ny = int(h / G) + 1
        n = self.nx * self.ny
        # владелец ячейки на каждом слое: 0 — свободно, -1 — запрет, иначе id цепи
        self.occ = [[0] * n, [0] * n]
        self.via_ok = [True] * n
        self.fat_ok = [True] * n
        self.fat_owner = [0] * n
        self.cost = [0] * n
        self.vcost = [[0] * n, [0] * n]
        self.margin = margin
        for ix in range(self.nx):
            for iy in range(self.ny):
                x, y = ix * G, iy * G
                if x < margin or y < margin or x > w - margin or y > h - margin:
                    i = iy * self.nx + ix
                    self.occ[0][i] = self.occ[1][i] = -1
                    self.via_ok[i] = False
                if x < margin + 0.6 or y < margin + 0.6 or x > w - margin - 0.6 or y > h - margin - 0.6:
                    self.fat_ok[self.idx(ix, iy)] = False

    def idx(self, ix, iy):
        return iy * self.nx + ix

    def cell(self, x, y):
        return int(round(x / G)), int(round(y / G))

    def block_rect(self, x1, y1, x2, y2, layers, netid, clr=0.33, via_clr=0.5, fat_clr=0.75):
        """Занять ячейки, центры которых лежат ближе clr к прямоугольнику площадки."""
        m = max(clr, via_clr, fat_clr)
        ix1 = max(0, int((x1 - m) / G)); ix2 = min(self.nx - 1, int((x2 + m) / G) + 1)
        iy1 = max(0, int((y1 - m) / G)); iy2 = min(self.ny - 1, int((y2 + m) / G) + 1)
        for ix in range(ix1, ix2 + 1):
            cx = ix * G
            dx = max(x1 - cx, 0, cx - x2)
            for iy in range(iy1, iy2 + 1):
                cy = iy * G
                dy = max(y1 - cy, 0, cy - y2)
                d = math.hypot(dx, dy)
                i = self.idx(ix, iy)
                if d <= via_clr:
                    self.via_ok[i] = False
                if d <= clr + 0.35 and self.cost[i] < 3:
                    self.cost[i] += 1
                if d <= fat_clr:
                    if netid < 0:
                        self.fat_owner[i] = -1
                    elif self.fat_owner[i] == 0:
                        self.fat_owner[i] = netid
                    elif self.fat_owner[i] != netid:
                        self.fat_owner[i] = -1
                if d <= clr:
                    for L in layers:
                        if self.occ[L][i] != netid:
                            self.occ[L][i] = netid if self.occ[L][i] == 0 else -1

    def free_near(self, ix, iy, L, netid, r=2):
        """Ближайшая к (ix,iy) ячейка слоя L, свободная или принадлежащая netid."""
        best = None
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                jx, jy = ix + dx, iy + dy
                if 0 <= jx < self.nx and 0 <= jy < self.ny:
                    o = self.occ[L][self.idx(jx, jy)]
                    if o == 0 or o == netid:
                        d = dx * dx + dy * dy
                        if best is None or d < best[0]:
                            best = (d, jx, jy)
        return None if best is None else (best[1], best[2])


class Router:
    def __init__(self, grid, via_cost=12, bend_cost=3, wrong_dir=2, log=None):
        self.g = grid
        self.via_cost, self.bend_cost, self.wrong_dir = via_cost, bend_cost, wrong_dir
        self.tracks = []     # (x1,y1,x2,y2,layer,netid,width)
        self.vias = []       # (x,y,netid)
        self.log = log
        self.fail = []
        self.net_cells = {}  # netid -> ячейки, занятые дорожками этой цепи (не площадками)
        self.cur = None
        self.base_occ = None
        self.base_via = None
        self.via_cnt = None

    def freeze_base(self):
        """Запомнить занятость после площадок/отводов/шин — для перекладки."""
        self.base_occ = [list(self.g.occ[0]), list(self.g.occ[1])]
        self.base_via = list(self.g.via_ok)
        self.via_cnt = [0] * len(self.base_via)

    def ripup(self, netid):
        g = self.g
        for (ix, iy, L) in self.net_cells.get(netid, ()):
            i = g.idx(ix, iy)
            if g.occ[L][i] == netid:
                g.occ[L][i] = self.base_occ[L][i]
        self.net_cells[netid] = set()
        for (x, y, nd) in self.vias:
            if nd == netid:
                ix, iy = g.cell(x, y)
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    jx, jy = ix + dx, iy + dy
                    if 0 <= jx < g.nx and 0 <= jy < g.ny:
                        j = g.idx(jx, jy)
                        self.via_cnt[j] -= 1
                        g.via_ok[j] = self.base_via[j] and self.via_cnt[j] == 0
        self.vias = [v for v in self.vias if v[2] != netid]
        self.tracks = [t for t in self.tracks if t[5] != netid]
        self.fail = [f for f in self.fail if f[0] != netid]

    def blockers(self, t, r=4):
        """Цепи, занимающие ячейки вокруг терминала t (кроме площадок из base)."""
        g = self.g
        ix0, iy0, _ = t
        out = set()
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                jx, jy = ix0 + dx, iy0 + dy
                if 0 <= jx < g.nx and 0 <= jy < g.ny:
                    j = g.idx(jx, jy)
                    for L in (0, 1):
                        o = g.occ[L][j]
                        if o > 0 and self.base_occ[L][j] != o:
                            out.add(o)
        return out

    def route_net(self, netid, terminals, width=0.25, wide=False, fat=False, maxexp=400000, preset=()):
        """terminals: список (ix, iy, layer или None=любой). Первая точка — корень дерева."""
        g = self.g
        if len(terminals) < 2 and not preset:
            return True
        tree = set()           # (ix, iy, L) ячейки, принадлежащие цепи
        cells = self.net_cells.setdefault(netid, set())
        def claim(ix, iy, L):
            i = g.idx(ix, iy)
            if g.occ[L][i] != netid:
                cells.add((ix, iy, L))
            g.occ[L][i] = netid
            tree.add((ix, iy, L))
            if wide:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    jx, jy = ix + dx, iy + dy
                    if 0 <= jx < g.nx and 0 <= jy < g.ny:
                        j = g.idx(jx, jy)
                        if g.occ[L][j] == 0:
                            g.occ[L][j] = netid
        def add_term(t):
            ix, iy, L = t
            for LL in ((0, 1) if L is None else (L,)):
                claim(ix, iy, LL)
        for c in preset:
            tree.add(c)
        add_term(terminals[0])
        ok = True
        # порядок: ближайший к дереву следующий
        rest = list(terminals[1:] if not preset else terminals)
        while rest:
            # ближайший терминал к дереву
            def dist(t):
                return min(abs(t[0] - a) + abs(t[1] - b) for (a, b, _) in tree)
            rest.sort(key=dist)
            t = rest.pop(0)
            path = self._astar(netid, t, tree, maxexp, fat)
            if path is None:
                ok = False
                self.fail.append((netid, t, self.last_reason))
                add_term(t)
                continue
            self._commit(path, netid, width, claim)
            add_term(t)
        return ok

    def _astar(self, netid, t, tree, maxexp, fat=False):
        g = self.g
        tx, ty, tL = t
        # цели: ячейки дерева. Эвристика — манхэттен до ближайшей (грубо: до корня-ближайшего по сетке)
        goals = tree
        # предварительно: для эвристики возьмём несколько точек
        glist = list(goals)[:64]
        def h(ix, iy):
            return min(abs(ix - a) + abs(iy - b) for (a, b, _) in glist)
        tcells = {(a, b) for (a, b, _) in tree} | {(tx, ty)}
        starts = [(tx, ty, L) for L in ((0, 1) if tL is None else (tL,))]
        openq = []
        best = {}
        for (sx, sy, sL) in starts:
            i = g.idx(sx, sy)
            if g.occ[sL][i] not in (0, netid):
                continue
            key = (sx, sy, sL, 4)     # 4 = без направления
            best[key] = 0
            heapq.heappush(openq, (h(sx, sy), 0, sx, sy, sL, 4, None))
        came = {}
        nexp = 0
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
        while openq:
            f, c, ix, iy, L, d, prev = heapq.heappop(openq)
            key = (ix, iy, L, d)
            if best.get(key, INF) < c:
                continue
            if key in came and came[key] is not None and prev is not None and came[key] != prev:
                pass
            came[key] = prev
            if (ix, iy, L) in goals and not (ix == tx and iy == ty):
                return self._backtrace(came, key)
            nexp += 1
            if nexp > maxexp:
                self.last_reason = 'limit'
                return None
            # шаги по слою
            for nd, (dx, dy) in enumerate(dirs):
                jx, jy = ix + dx, iy + dy
                if not (0 <= jx < g.nx and 0 <= jy < g.ny):
                    continue
                o = g.occ[L][g.idx(jx, jy)]
                if o != 0 and o != netid:
                    continue
                if fat and not self._fat_free(jx, jy, L, netid, (jx, jy) in tcells):
                    continue
                if dy != 0 and g.vcost[L][g.idx(jx, jy)] >= 10 ** 6 and o != netid:
                    continue
                jj = g.idx(jx, jy)
                horizontal = dy == 0
                step = 1 + g.cost[jj] + (0 if horizontal else g.vcost[L][jj])
                if (L == 0) != horizontal:
                    step += self.wrong_dir
                if d != 4 and d != nd:
                    step += self.bend_cost
                nc = c + step
                nk = (jx, jy, L, nd)
                if nc < best.get(nk, INF):
                    best[nk] = nc
                    heapq.heappush(openq, (nc + h(jx, jy), nc, jx, jy, L, nd, key))
            # переход на другой слой
            i = g.idx(ix, iy)
            if g.via_ok[i]:
                L2 = 1 - L
                o = g.occ[L2][i]
                if o == 0 or o == netid:
                    nc = c + self.via_cost
                    nk = (ix, iy, L2, 4)
                    if nc < best.get(nk, INF):
                        best[nk] = nc
                        heapq.heappush(openq, (nc + h(ix, iy), nc, ix, iy, L2, 4, key))
        self.last_reason = 'closed'
        return None

    def _fat_free(self, ix, iy, L, netid, is_term):
        g = self.g
        if is_term:
            return True
        i = g.idx(ix, iy)
        if not g.fat_ok[i] or g.fat_owner[i] not in (0, netid):
            return False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            jx, jy = ix + dx, iy + dy
            if 0 <= jx < g.nx and 0 <= jy < g.ny:
                o = g.occ[L][g.idx(jx, jy)]
                if o != 0 and o != netid:
                    return False
        return True

    def _backtrace(self, came, key):
        path = []
        while key is not None:
            path.append(key)
            key = came[key]
        path.reverse()
        return path

    def _commit(self, path, netid, width, claim):
        g = self.g
        # сжать в отрезки
        pts = [(k[0], k[1], k[2]) for k in path]
        for (ix, iy, L) in pts:
            claim(ix, iy, L)
        i = 0
        while i < len(pts) - 1:
            ax, ay, aL = pts[i]
            bx, by, bL = pts[i + 1]
            if aL != bL:
                self.vias.append((ax * G, ay * G, netid))
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    jx, jy = ax + dx, ay + dy
                    if 0 <= jx < g.nx and 0 <= jy < g.ny:
                        j = g.idx(jx, jy)
                        g.via_ok[j] = False
                        if self.via_cnt is not None:
                            self.via_cnt[j] += 1
                i += 1
                continue
            dx, dy = bx - ax, by - ay
            j = i + 1
            while j + 1 < len(pts) and pts[j + 1][2] == aL and (pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]) == (dx, dy):
                j += 1
            ex, ey, _ = pts[j]
            self.tracks.append((ax * G, ay * G, ex * G, ey * G, aL, netid, width))
            i = j


def column_penalty(grid, x, halfw, layers, pen=20, y1=None, y2=None, xa=None, xb=None):
    """Штраф за вертикальный ход в полосе |x - x0| <= halfw или xa..xb (выходы с площадок колонки должны оставаться свободны)."""
    if xa is None:
        xa, xb = x - halfw, x + halfw
    ix1 = max(0, int(xa / G)); ix2 = min(grid.nx - 1, int(xb / G) + 1)
    for ix in range(ix1, ix2 + 1):
        if xa - 0.01 <= ix * G <= xb + 0.01:
            for iy in range(grid.ny):
                if y1 is not None and not (y1 <= iy * G <= y2):
                    continue
                i = grid.idx(ix, iy)
                for L in layers:
                    grid.vcost[L][i] = max(grid.vcost[L][i], pen)
