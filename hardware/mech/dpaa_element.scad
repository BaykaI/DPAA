// Держатель элемента акустической ЦАФАР под ГОТОВЫЕ модули (минимум своего монтажа).
//
// «Плитка» 39.6 x 59.6 мм (шаг решётки 40 мм по горизонтали, 60 мм по вертикали):
//   внизу  — динамик (круглый 28…36 мм или овальный 15 x 24 мм) в закрытом объёме;
//   вверху — круглое гнездо под готовый модуль микрофона ICS-43434 (Ø ≈ 14 мм,
//            проверить штангенциркулем и поправить mic_d): модуль вставляется сзади
//            до упорного бортика, выводы смотрят назад, к проводам.
// Модуль усилителя MAX98357A крепится стяжкой к задней панели за динамиком.
//
// Система координат: x — вправо, y — вверх, z — от лицевой плоскости назад.
// Печать: держатель — лицом вниз на стол; крышка — наружной стороной вниз.
// PLA/PETG, сопло 0.4, слой 0.2, 3–4 периметра, заполнение 30 %, без поддержек.
//
// Использование:
//   openscad -D 'part="holder"' -D 'speaker="rd28"' -o holder.stl dpaa_element.scad
//   part: holder | back | assembly | exploded | array_line | array_planar
//         | panel_line | panel_planar (2D, для лазерной резки: экспорт в SVG/DXF)

part    = "exploded";
// Динамик (размеры в таблице ниже — типовые, ИЗМЕРИТЬ свою партию и поправить):
//   "rd28" — круглый 28 мм, 8 Ом 2 Вт, внутренний магнит (основной, ≈ 0.5–1 $);
//   "rd36" — круглый 36 мм майларовый, 8 Ом 1 Вт (самый дешёвый, 1 Вт — см. mechanics.md);
//   "rd32" — круглый 32 мм (Dayton Audio CE32A-8 и аналоги);
//   "sq32" — квадратный 32 мм (Visaton BF 32 S);
//   "ov1524" — овальный 15 x 24 x 3.5 мм, 8 Ом 0.8 Вт (длинной стороной вертикально).
speaker = "rd28";

$fn = 72;

// ---------- решётка ----------
pitch_x = 40;
pitch_y = 60;
gap     = 0.4;
W       = pitch_x - gap;      // ширина плитки
Ht      = pitch_y - gap;      // высота плитки
sp_y    = -Ht/2 + W/2;        // центр динамика (-10)
mic_y   =  Ht/2 - (Ht - W)/2; // центр микрофона (+19.8)

// ---------- динамик ----------
//   [ширина (Ø), высота (= ширине у круглых), монтажная глубина, толщина обода,
//    Ø магнита, глубина объёма за динамиком L_cav]
spk_table = [["rd28",   [28.0, 28.0,  6.0, 1.5, 16, 16]],
             ["rd36",   [36.0, 36.0,  5.0, 1.5, 16, 16]],
             ["rd32",   [32.0, 32.0, 14.5, 1.2, 22, 16]],
             ["sq32",   [32.0, 32.0, 11.0, 1.2, 22, 16]],
             ["ov1524", [15.0, 24.0,  3.5, 2.5, 10, 10]]];  // выводы 50 мм — объём мельче
spk      = spk_table[search([speaker], spk_table)[0]][1];
shape    = speaker[0] == "s" ? "square" : speaker[0] == "o" ? "oval" : "round";
spk_w    = spk[0];
spk_h    = spk[1];
spk_depth= spk[2];            // от лицевой плоскости рамы до торца магнита
flange_t = spk[3];            // толщина обода, на который давят упоры крышки
magnet_d = spk[4];
L_cav    = spk[5];
spk_clr  = 0.4;               // зазор гнезда под раму

// ---------- лицевая часть ----------
lip        = 1.5;             // толщина перед рамой динамика
flange_pkt = 1.8;             // гнездо под раму динамика
t_front    = lip + flange_pkt;
horn_in    = shape == "oval" ? 3.0 : 4.5;   // раскрыв меньше рамы: рама лежит на бортике
chamfer    = 1.0;

// ---------- объём за динамиком ----------
cav    = max(32.8, max(spk_w, spk_h) + 2*spk_clr + 0.4);  // для 36 мм стенки ≈ 1.4 мм
depth  = t_front + L_cav;

// ---------- модуль микрофона ----------
mic_d     = 14.2;             // диаметр гнезда = диаметр модуля + 0.2 (ИЗМЕРИТЬ модуль!)
mic_lip_w = 0.9;              // ширина упорного бортика спереди
mic_lip_t = 0.8;              // толщина бортика
wall      = 3;                // боковые стенки верхней части

// ---------- крышка ----------
back_t  = 3;
plug_h  = 2;
clr     = 0.25;
post    = 2.4;
// упоры давят на обод рамы: у квадратной — в углы, у круглой — по диагоналям на радиусе
// spk_w/2 - 1.3, у овальной — ближе к концам (в середине магнит, внизу провода)
pr      = (spk_w/2 - 1.3) / sqrt(2);
oy      = spk_h/2 - 2.5;
ox      = sqrt(pow(spk_w/2, 2) - pow(oy - (spk_h - spk_w)/2, 2)) - 1.0;
pxy     = shape == "square" ? [14.6, 14.6] : shape == "oval" ? [ox, oy] : [pr, pr];
posts   = [for (sx = [-1, 1], sy = [-1, 1]) [sx*pxy[0], sy*pxy[1]]];
m3_xy   = 12;
m3_d    = 4.2;
cable_d = 5;
cable_y = -10;                // относительно центра динамика

// =====================================================================
// контур рамы динамика (2D), увеличенный на grow с каждой стороны
module spk_outline(grow = 0) {
    w = spk_w + 2*grow;
    h = spk_h + 2*grow;
    if (shape == "square") square([w, h], center = true);
    else hull() for (sy = [-1, 1]) translate([0, sy*(h - w)/2]) circle(d = w);
}

// раскрыв: у квадратной рамы — круглый (диффузор круглый)
module horn_outline(grow = 0) {
    if (shape == "square") circle(d = spk_w + 2*grow);
    else spk_outline(grow);
}

module holder() {
    difference() {
        union() {
            translate([-W/2, -Ht/2, 0]) cube([W, Ht, t_front]);                        // лицевая пластина
            translate([-W/2, sp_y - W/2, 0]) cube([W, W, depth]);                       // корпус динамика
            for (sx = [-1, 1])                                                          // стенки верхней части
                translate([sx > 0 ? W/2 - wall : -W/2, sp_y + W/2 - 1, 0]) cube([wall, Ht - W + 1, depth]);
            translate([-W/2, Ht/2 - 2, 0]) cube([W, 2, depth]);                         // верхняя кромка
        }
        // объём за динамиком
        translate([-cav/2, sp_y - cav/2, t_front]) cube([cav, cav, L_cav + 1]);
        // гнездо под раму динамика
        translate([0, sp_y, lip]) linear_extrude(flange_pkt + 0.01) spk_outline(spk_clr/2);
        // раскрыв с фаской
        translate([0, sp_y, -1]) linear_extrude(t_front + 2) horn_outline(-horn_in/2);
        translate([0, sp_y, -0.01]) hull() {
            linear_extrude(0.01) horn_outline(-horn_in/2 + chamfer);
            translate([0, 0, chamfer]) linear_extrude(0.01) horn_outline(-horn_in/2);
        }
        // гнездо микрофона: сквозное отверстие с упорным бортиком спереди
        translate([0, mic_y, mic_lip_t]) cylinder(d = mic_d, h = depth);
        translate([0, mic_y, -1]) cylinder(d = mic_d - 2*mic_lip_w, h = mic_lip_t + 2);
    }
}

module back() {
    difference() {
        union() {
            translate([-W/2, -W/2, 0]) cube([W, W, back_t]);
            translate([-(cav - 2*clr)/2, -(cav - 2*clr)/2, -plug_h]) cube([cav - 2*clr, cav - 2*clr, plug_h]);
            post_len = depth - plug_h - (lip + flange_t);
            for (q = posts)
                translate([q[0] - post/2, q[1] - post/2, -plug_h - post_len])
                    cube([post, post, post_len]);
        }
        // глухие закладные M3 — объём остаётся герметичным
        for (sx = [-1, 1]) translate([sx*m3_xy, 0, -plug_h + 0.8]) cylinder(d = m3_d, h = back_t + plug_h);
        // провода динамика (после монтажа залить термоклеем)
        translate([0, cable_y, -plug_h - 1]) cylinder(d = cable_d, h = back_t + plug_h + 2);
    }
}

// условные модели готовых модулей и динамика для сборочных видов
module speaker_dummy() {
    basket = max(0, min(3, spk_depth - flange_t - 1));
    color(shape == "oval" ? "white" : "dimgray") {
        linear_extrude(flange_t) spk_outline();
        if (basket > 0)
            translate([0, 0, flange_t]) cylinder(d1 = min(spk_w, spk_h) - 4, d2 = magnet_d, h = basket);
        translate([0, 0, flange_t + basket]) cylinder(d = magnet_d, h = spk_depth - flange_t - basket);
    }
    color("black") translate([0, 0, -0.01]) linear_extrude(0.2) spk_outline(-2);
}

module mic_module_dummy() {       // круглая плата Ø14 с двумя рядами по 3 штыря
    color("black") cylinder(d = mic_d - 0.2, h = 1.6);
    color("silver") translate([-1.75, -1.3, 1.6]) cube([3.5, 2.6, 1]);
    for (sx = [-1, 1], i = [-1:1])
        color("gold") translate([sx*4.5, i*2.54, 1.6]) cylinder(d = 0.64, h = 8, $fn = 8);
}

module amp_module_dummy() {       // модуль MAX98357A ~18 x 19 мм
    color("royalblue") translate([-9, -9.5, 0]) cube([18, 19, 1.6]);
    color("black") translate([-1.5, -1.5, 1.6]) cube([3, 3, 0.8]);
}

module element(explode = 0) {
    color("lightsteelblue") holder();
    translate([0, sp_y, lip + explode*1.6]) speaker_dummy();
    translate([0, mic_y, mic_lip_t + explode*1.0]) mic_module_dummy();
    color("slategray") translate([0, sp_y, depth + explode*2.2]) back();
    translate([0, sp_y + 2, depth + back_t + 4 + explode*3.2]) amp_module_dummy();   // на задней панели
}

// 2D: задняя панель (лазерная резка) для nx x ny элементов
module panel(nx, ny, margin = 20, pt = 4) {
    difference() {
        square([nx*pitch_x + 2*margin, ny*pitch_y + 2*margin]);
        for (i = [0:nx-1], j = [0:ny-1])
            translate([margin + pitch_x/2 + i*pitch_x, margin + pitch_y/2 + j*pitch_y]) {
                for (sx = [-1, 1]) translate([sx*m3_xy, sp_y]) circle(d = 3.4);               // крепление крышки
                translate([0, sp_y + cable_y]) circle(d = 8);                                // провода динамика
                translate([-(W/2 - wall - 1), sp_y + W/2]) square([W - 2*wall - 2, Ht - W - 3]);  // окно к выводам микрофона
                for (sx = [-1, 1]) translate([sx*11 - 0.8, sp_y + 7]) square([1.6, 4.5]);    // прорези под стяжку усилителя
            }
        for (x = [8, nx*pitch_x + 2*margin - 8], y = [8, ny*pitch_y + 2*margin - 8])
            translate([x, y]) circle(d = 5.5);
    }
}

module array(nx, ny) {
    for (i = [0:nx-1], j = [0:ny-1])
        translate([(i - (nx-1)/2)*pitch_x, (j - (ny-1)/2)*pitch_y, 0]) element();
}

if (part == "holder")        holder();
else if (part == "back")     rotate([180, 0, 0]) back();
else if (part == "assembly") element(0);
else if (part == "exploded") element(12);
else if (part == "array_line")   array(16, 1);
else if (part == "array_planar") array(8, 4);
else if (part == "panel_line")   panel(16, 1);
else if (part == "panel_planar") panel(8, 4);
