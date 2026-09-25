#!/bin/sh
# Проверочная разводка (без привязки выводов) для всех поддерживаемых кристаллов:
#   i9    — Colorlight i9, LFE5U-45F (основная плата)
#   i5    — Colorlight i5, LFE5U-25F (дешёвый вариант, тот же верхний уровень)
#   ulx3s — ULX3S, LFE5U-85F
# Печатает занятость ресурсов и максимальную частоту. Битстримы НЕ создаются.
set -e
cd "$(dirname "$0")"
make -s build/i9/dpaa.json BOARD=i9
make -s build/ulx3s/dpaa.json BOARD=ulx3s
mkdir -p build/i5
cp build/i9/dpaa.json build/i5/dpaa.json
run() {  # $1 — каталог, $2 — кристалл
    nextpnr-ecp5 --"$2" --package CABGA381 --json "build/$1/dpaa.json" --lpf-allow-unconstrained \
        --freq 50 --router router2 -l "build/$1/check.log" > /dev/null 2>&1 || true
}
run i9 45k & run i5 25k & run ulx3s 85k & wait
for d in i9 i5 ulx3s; do
    echo "== $d"
    grep -E "TRELLIS_COMB:|TRELLIS_FF:|MULT18X18D:|DP16KD:|Max frequency" "build/$d/check.log" | tail -5 \
        | sed 's/^Info: *//; s/^ERROR: *//'
done
