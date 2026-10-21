#!/bin/bash
# Производственный пакет: Gerber + сверловка (JLCPCB/PCBWay), файл координат, BOM, PDF, рендеры, STEP
cd "$(dirname "$0")/.."
KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"; KP="/c/Program Files/KiCad/10.0/bin/python.exe"
rm -rf fab && mkdir -p fab/gerber
"$KC" pcb export gerbers --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" --no-protel-ext --subtract-soldermask -o fab/gerber/ dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" pcb export drill --format excellon --excellon-units mm --excellon-zeros-format decimal --generate-map --map-format pdf -o fab/gerber/ dpaa_dist.kicad_pcb >/dev/null 2>&1
(cd fab/gerber && python -I -c "import zipfile,os; z=zipfile.ZipFile('../dpaa_dist_gerber.zip','w',zipfile.ZIP_DEFLATED); [z.write(f) for f in sorted(os.listdir('.')) if f.endswith(('.gbr','.drl','.gbrjob'))]; z.close()")
"$KC" pcb export pos --format csv --units mm --side both --use-drill-file-origin -o fab/dpaa_dist_pos_raw.csv dpaa_dist.kicad_pcb >/dev/null 2>&1
PYTHONIOENCODING=utf-8 "$KP" -I gen/make_bom.py
rm -f fab/dpaa_dist_pos_raw.csv
"$KC" pcb export pdf --layers "F.Cu,F.SilkS,Edge.Cuts" -o fab/dpaa_dist_top.pdf dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" pcb export pdf --layers "B.Cu,Edge.Cuts" --mirror -o fab/dpaa_dist_bottom.pdf dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" pcb export pdf --layers "F.SilkS,F.Fab,Edge.Cuts" -o fab/dpaa_dist_assembly.pdf dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" sch export pdf -o fab/dpaa_dist_schematic.pdf dpaa_dist.kicad_sch >/dev/null 2>&1
"$KC" pcb render --side top --background opaque --quality basic -w 1800 -h 2600 -o fab/render_top.png dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" pcb render --side bottom --background opaque --quality basic -w 1800 -h 2600 -o fab/render_bottom.png dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" pcb render --perspective --rotate "-30,0,20" --zoom 0.9 --background opaque --quality basic -w 2000 -h 1600 -o fab/render_3d.png dpaa_dist.kicad_pcb >/dev/null 2>&1
"$KC" pcb export step --subst-models -o fab/dpaa_dist.step dpaa_dist.kicad_pcb >/dev/null 2>&1
ls fab fab/gerber | head -40
