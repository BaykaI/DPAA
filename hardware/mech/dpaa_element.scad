// Держатель элемента акустической ЦАФАР: динамик + микрофон в одном корпусе.
//
// «Плитка» 39.6 x 39.6 мм = шаг решётки 40 мм — из одинаковых плиток собирается
// и линейная решётка 16x1, и плоская 8x4 / 8x8 (сканирование в двух плоскостях).
//
//   спереди:  раскрыв динамика с фаской + углубление под микроплату микрофона
//             (ICS-43434, 8x8 мм) в правом верхнем углу;
//   внутри:   закрытый объём за динамиком (нет излучения назад, микрофон
//             акустически отделён от тыла динамика);
//   сзади:    крышка с упорами, прижимающими раму динамика, 2 закладные гайки M3
//             для крепления к задней панели и паз для платы усилителя.
//
// Система координат: x — вправо, y — вверх, z — от лицевой плоскости назад.
// Печать: держатель — лицом вниз на стол; крышка — наружной стороной вниз.
// PLA/PETG, сопло 0.4, слой 0.2, заполнение 30 %, без поддержек.
//
// Использование:
//   openscad -D 'part="holder"' -D 'speaker="square32"' -o holder.stl dpaa_element.scad
//   part: holder | back | micboard | assembly | exploded | array_line | array_planar
//         | panel_line | panel_planar (2D, для лазерной резки: экспорт в SVG/DXF)

part    = "exploded";
speaker = "round32";    // "round32" — Dayton Audio CE32A-8 (основной); "square32" — Visaton BF 32 S

$fn = 72;

// ---------- решётка ----------
pitch = 40;
gap   = 0.4;
W     = pitch - gap;          // размер плитки

// ---------- лицевая часть ----------
lip        = 3.2;             // толщина перед рамой динамика (глубина под микроплату + 0.8)
flange_pkt = 1.8;             // глубина гнезда под раму динамика
t_front    = lip + flange_pkt;
cone_d     = 27.5;            // раскрыв перед диффузором
chamfer    = 0.8;             // фаска раскрыва на лицевой стороне

// ---------- динамик ----------
spk_sq     = 32.4;            // гнездо под квадратную раму 32 x 32 (+0.4 зазор)
spk_rd     = 32.4;            // гнездо под круглую раму Ø32
spk_depth  = speaker == "square32" ? 11.0 : 14.5;   // монтажная глубина по данным производителей
flange_t   = 1.2;             // толщина рамы (уточнить по образцу; компенсируется прокладкой)

// ---------- объём за динамиком ----------
cav    = 32.8;                // внутренний размер корпуса
L_cav  = 16;                  // длина объёма
depth  = t_front + L_cav;     // полная глубина держателя

// ---------- микрофон ----------
mic_xy     = [14.8, 14.8];        // центр микроплаты (и акустического отверстия)
mic_board  = 8.2;             // гнездо под плату 8.0 x 8.0
mic_recess = 2.4;             // плата 0.8 + микрофон 1.0 + зазор
wire_xy    = [17.8, 17.8];    // канал проводов микрофона
wire_d     = 2.0;

// ---------- крышка ----------
back_t  = 3;
plug_h  = 2;
clr     = 0.25;
post    = 2.4;
post_xy = speaker == "square32" ? 14.6 : 10.7;   // упоры в углы рамы / в кольцо рамы
m3_xy   = 12;                 // закладные M3 в (±12, 0)
m3_d    = 4.2;                // под латунную закладную M3 x 4.5
cable_d = 5;
cable_y = -10;
slot_w  = 1.7;                // паз под плату усилителя 1.6 мм
rib_t   = 1.2;
rib_h   = 6;
rib_y   = [-2, 16];

// =====================================================================
module holder() {
    difference() {
        translate([-W/2, -W/2, 0]) cube([W, W, depth]);
        // объём за динамиком
        translate([-cav/2, -cav/2, t_front]) cube([cav, cav, L_cav + 1]);
        // гнездо под раму динамика
        if (speaker == "square32")
            translate([-spk_sq/2, -spk_sq/2, lip]) cube([spk_sq, spk_sq, flange_pkt + 0.01]);
        else
            translate([0, 0, lip]) cylinder(d = spk_rd, h = flange_pkt + 0.01);
        // раскрыв с фаской
        translate([0, 0, -1]) cylinder(d = cone_d, h = t_front + 2);
        translate([0, 0, -0.01]) cylinder(d1 = cone_d + 2*chamfer, d2 = cone_d, h = chamfer);
        // гнездо микроплаты (открыто вперёд)
        translate([mic_xy[0] - mic_board/2, mic_xy[1] - mic_board/2, -0.01])
            cube([mic_board, mic_board, mic_recess]);
        // канал проводов: сквозь лицевую часть, затем в объём за динамиком
        translate([wire_xy[0], wire_xy[1], -1]) cylinder(d = wire_d, h = t_front + 3);
        hull() {
            translate([wire_xy[0], wire_xy[1], t_front + 0.5]) cylinder(d = wire_d, h = 1.5);
            translate([cav/2 - 2, cav/2 - 2, t_front + 0.5]) cylinder(d = wire_d, h = 1.5);
        }
    }
}

module back() {
    difference() {
        union() {
            // пластина крышки (z отсчитывается от задней грани держателя)
            translate([-W/2, -W/2, 0]) cube([W, W, back_t]);
            // пробка, входящая в объём
            translate([-(cav - 2*clr)/2, -(cav - 2*clr)/2, -plug_h]) cube([cav - 2*clr, cav - 2*clr, plug_h]);
            // упоры, прижимающие раму динамика
            post_len = depth - plug_h - (lip + flange_t);
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx*post_xy - post/2, sy*post_xy - post/2, -plug_h - post_len])
                    cube([post, post, post_len]);
            // рёбра паза под плату усилителя (плата 1.6 мм, ширина 32 мм)
            for (sx = [-1, 1])
                translate([sx > 0 ? slot_w/2 : -slot_w/2 - rib_t, rib_y[0], back_t])
                    cube([rib_t, rib_y[1] - rib_y[0], rib_h]);
        }
        // закладные M3 со стороны задней панели — глухие, объём остаётся герметичным
        for (sx = [-1, 1]) translate([sx*m3_xy, 0, -plug_h + 0.8]) cylinder(d = m3_d, h = back_t + plug_h);
        // кабель динамика и микрофона
        translate([0, cable_y, -plug_h - 1]) cylinder(d = cable_d, h = back_t + plug_h + 2);
    }
}

// микроплата микрофона 8 x 8 x 0.8 мм, ICS-43434 на тыльной стороне,
// звуковое отверстие Ø0.8 мм через плату по центру микрофона
module micboard() {
    difference() {
        color("darkgreen") translate([-4, -4, 0]) cube([8, 8, 0.8]);
        translate([0, 0, -1]) cylinder(d = 0.8, h = 3, $fn = 16);
    }
    color("silver") translate([-1.75, -1.325, 0.8]) cube([3.5, 2.65, 0.98]);
    // контактные площадки проводов: VDD, GND, SCK, WS, SD
    for (i = [0:4]) color("gold") translate([2.3, -3.2 + i*1.4, 0.8]) cube([1.2, 0.8, 0.05]);
}

// условная модель динамика для сборочных видов
module speaker_dummy() {
    color("dimgray") {
        if (speaker == "square32") translate([-16, -16, 0]) cube([32, 32, flange_t]);
        else cylinder(d = 32, h = flange_t);
        translate([0, 0, flange_t]) cylinder(d1 = 28, d2 = 18, h = 4);
        translate([0, 0, flange_t + 4]) cylinder(d = 18, h = spk_depth - flange_t - 4);
    }
    color("black") translate([0, 0, 0.2]) cylinder(d1 = 26, d2 = 12, h = 3);
}

module element(explode = 0) {
    color("lightsteelblue") holder();
    translate([0, 0, lip + explode*1.6]) speaker_dummy();          // вставляется сзади
    // лицевая сторона платы утоплена на 0.6 мм, микрофон — на тыльной стороне платы
    translate([mic_xy[0], mic_xy[1], mic_recess - 0.8 - 0.98 - explode*1.2]) micboard();
    color("slategray") translate([0, 0, depth + explode*2.2]) back();
}

// 2D: задняя панель (лазерная резка) для nx x ny элементов
module panel(nx, ny, margin = 20) {
    difference() {
        square([nx*pitch + 2*margin, ny*pitch + 2*margin]);
        for (i = [0:nx-1], j = [0:ny-1])
            translate([margin + pitch/2 + i*pitch, margin + pitch/2 + j*pitch]) {
                // окно под рёбра, плату усилителя и кабель
                translate([-7, -18]) square([14, 36]);
                for (sx = [-1, 1]) translate([sx*m3_xy, 0]) circle(d = 3.4);
            }
        // крепёжные отверстия панели к стойке
        for (x = [8, nx*pitch + 2*margin - 8], y = [8, ny*pitch + 2*margin - 8])
            translate([x, y]) circle(d = 5.5);
    }
}

module array(nx, ny) {
    for (i = [0:nx-1], j = [0:ny-1])
        translate([(i - (nx-1)/2)*pitch, (j - (ny-1)/2)*pitch, 0]) element();
}

if (part == "holder")        holder();
else if (part == "back")     rotate([180, 0, 0]) back();   // наружной стороной на стол
else if (part == "micboard") micboard();
else if (part == "assembly") element(0);
else if (part == "exploded") element(14);
else if (part == "array_line")   array(16, 1);
else if (part == "array_planar") array(8, 4);
else if (part == "panel_line")   panel(16, 1);
else if (part == "panel_planar") panel(8, 4);
