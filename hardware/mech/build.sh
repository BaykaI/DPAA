#!/bin/sh
# Пересборка STL, контуров панели и рендеров из dpaa_element.scad.
# Нужны: openscad (и xvfb-run для рендеров без экрана).
set -e
cd "$(dirname "$0")"
mkdir -p stl render
for sp in rd28 rd36 rd32 sq32; do
  for pt in holder back; do
    openscad -q -D "part=\"$pt\"" -D "speaker=\"$sp\"" -o "stl/${pt}_${sp}.stl" dpaa_element.scad
  done
done

for pl in panel_line panel_planar; do
  openscad -q -D "part=\"$pl\"" -o "stl/$pl.svg" dpaa_element.scad
  openscad -q -D "part=\"$pl\"" -o "stl/$pl.dxf" dpaa_element.scad
done
R() { xvfb-run -a openscad -q -D "part=\"$1\"" -D "speaker=\"$2\"" --camera="$3" $6 \
        --imgsize="$4" --colorscheme=Tomorrow -o "render/$5.png" dpaa_element.scad; }
R exploded rd28 110,80,-150,0,0,26 1200,1000 exploded ""
R exploded rd28 -110,80,120,0,0,26 1200,1000 back ""
R assembly rd36 60,45,-110,0,0,8 1000,900 assembly_rd36 ""
R assembly rd28 60,45,-110,0,0,8 1000,900 assembly ""
R array_line rd28 150,160,-650,0,0,10 1600,700 array_line "--viewall --autocenter"
R array_planar rd28 120,160,-520,0,0,10 1400,1000 array_planar "--viewall --autocenter"
echo "готово: stl/, render/"
