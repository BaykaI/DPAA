#!/bin/bash
# Сборка платы: генератор (компоновка + трассировка) -> нормы -> DRC -> схема -> ERC -> картинки
cd "$(dirname "$0")"
KP="/c/Program Files/KiCad/10.0/bin/python.exe"; KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
PYTHONIOENCODING=utf-8 "$KP" -I make_board.py 2>&1 | grep -v "^$" | grep "^цепей\|^трасс\|^FAIL\|^скош\|^сшив\|^финал\|^земля\|^убрано\|^переходных\|Traceback\|Error" 
python -I fix_pro.py ../dpaa_dist.kicad_pro >/dev/null
cd ..
"$KC" pcb drc --refill-zones --save-board --format json -o drc.json dpaa_dist.kicad_pcb >/dev/null 2>&1
PYTHONIOENCODING=utf-8 "$KP" -I gen/stitch_fix.py 2>&1 | tail -1
"$KC" pcb drc --refill-zones --save-board --format json -o drc.json dpaa_dist.kicad_pcb >/dev/null 2>&1
PYTHONIOENCODING=utf-8 "$KP" -I gen/make_sch.py 2>&1 | tail -1
"$KC" sch erc --format json -o erc.json dpaa_dist.kicad_sch >/dev/null 2>&1
PYTHONIOENCODING=utf-8 python -I gen/drc_report.py
