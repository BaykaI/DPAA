// Ядро цифрового диаграммообразования: «дробная задержка + вес + сумма».
//
//   out[o] = SUM_i  g[o][i] * x_i(t - d[o][i])
//
// Одно и то же ядро работает:
//   * на передачу:  NI = число лучей (источников), NO = число излучателей;
//   * на приём:     NI = число микрофонов,         NO = число лучей.
//
// Задержка d — 16 бит: [15:5] целая часть в отсчётах (>= 3), [4:0] — фаза 1/32.
// Дробная часть реализуется 8-отводным КИХ-фильтром (32 набора коэффициентов,
// Q2.16, рассчитаны методом наименьших квадратов — см. dpaa/hw.py).
// Вес g — 18 бит со знаком, Q2.16 (65536 = 1.0).
// Таблицы хранятся в блочной памяти в двух банках: запись идёт в неактивный банк,
// по стробу commit банки меняются местами в начале кадра (луч переключается без
// «разрыва»), затем новый активный банк копируется в неактивный (NT тактов), чтобы
// последующие частичные изменения опирались на актуальную таблицу.
//
// Вычисление: конвейер на одном умножителе для отводов и одном для весов,
// NO*NI*8 + ~10 тактов на кадр (TX: 264, RX: 264 из 1024 доступных).
module delay_sum_engine #(
    parameter NI_LOG2    = 1,
    parameter NO_LOG2    = 4,
    parameter DEPTH_LOG2 = 8,
    parameter OUT_SHL    = 6,
    parameter [17:0] GAIN_IN0   = 18'd32768,  // вес входа 0 после сброса
    parameter [17:0] GAIN_OTHER = 18'd0       // вес остальных входов после сброса
) (
    input  wire                          clk,
    input  wire                          rst,
    input  wire                          tick,
    input  wire [(1<<NI_LOG2)*18-1:0]    in_data,
    input  wire                          cfg_we,
    input  wire                          cfg_sel,   // 0 — задержка, 1 — вес
    input  wire [NI_LOG2+NO_LOG2-1:0]    cfg_idx,   // o*NI + i
    input  wire [23:0]                   cfg_data,
    input  wire                          commit,
    output reg  [(1<<NO_LOG2)*24-1:0]    out_data,
    output reg                           done
);
    localparam NI = 1 << NI_LOG2;
    localparam NO = 1 << NO_LOG2;
    localparam TL = NI_LOG2 + NO_LOG2;
    localparam NT = 1 << TL;
    localparam [15:0] DELAY_INIT = 16'd256;  // 8.0 отсчёта — луч по нормали

    // ---- таблицы: 2 банка в памяти ----
    reg [15:0]        tdly [0:2*NT-1];
    reg signed [17:0] tgn  [0:2*NT-1];
    integer t;
    initial for (t = 0; t < 2*NT; t = t + 1) begin
        tdly[t] = DELAY_INIT;
        tgn[t]  = ((t % NI) == 0) ? GAIN_IN0 : GAIN_OTHER;
    end
    reg commit_pending;
    reg act;                                  // активный банк

    // порты памяти таблиц (по одному порту записи и чтения на таблицу)
    reg          td_we, tg_we;
    reg [TL:0]   td_wa, tg_wa, td_ra, tg_ra;
    reg [15:0]   td_wd;
    reg signed [17:0] tg_wd;
    reg [15:0]   td_q;
    reg signed [17:0] tg_q;
    always @(posedge clk) begin
        if (td_we) tdly[td_wa] <= td_wd;
        if (tg_we) tgn[tg_wa]  <= tg_wd;
        td_q <= tdly[td_ra];
        tg_q <= tgn[tg_ra];
    end

    // очередь записей настройки (запись откладывается, пока идёт копирование банков)
    reg [TL+24:0] q_mem [0:3];                // {sel, idx, data}
    reg [1:0]     q_wp, q_rp;
    reg [2:0]     q_n;

    // ---- буфер отсчётов и ПЗУ коэффициентов ----
    reg signed [17:0] mem  [0:NI*(1<<DEPTH_LOG2)-1];
    reg signed [17:0] coef [0:255];
    initial $readmemh("fd_coeffs.hex", coef);
    integer m;
    initial for (m = 0; m < NI*(1<<DEPTH_LOG2); m = m + 1) mem[m] = 0;

    reg                          we;
    reg [NI_LOG2+DEPTH_LOG2-1:0] waddr, raddr;
    reg signed [17:0]            wdata, x_rd, h_rd;
    reg [7:0]                    caddr;
    always @(posedge clk) begin
        if (we) mem[waddr] <= wdata;
        x_rd <= mem[raddr];
        h_rd <= coef[caddr];
    end

    // ---- управление ----
    localparam S_IDLE = 3'd0, S_WRITE = 3'd1, S_RUN = 3'd2, S_DRAIN = 3'd3, S_COPY = 3'd4;
    reg [2:0]            st;
    reg [TL:0]           ccnt;
    reg [(NI*18)-1:0]    in_lat;
    reg [DEPTH_LOG2-1:0] wptr;
    reg [NI_LOG2:0]      wcnt;
    reg [TL-1:0]         ti;
    reg [2:0]            k;
    reg [3:0]            drain;

    // выдача адресов (стадия A)
    wire [15:0]            d_cur = td_q;      // задержка текущего члена (читается заранее)
    wire [DEPTH_LOG2-1:0]  rptr  = wptr - d_cur[DEPTH_LOG2+4:5] + 3 - k;

    // конвейер
    reg              a_v, a_k0, a_k7;  reg [TL-1:0] a_ti;   // адрес выставлен
    reg              r_v, r_k0, r_k7;  reg [TL-1:0] r_ti;   // данные памяти готовы
    reg              b_v, b_k0, b_k7;  reg [TL-1:0] b_ti;
    reg              c_v;              reg [TL-1:0] c_ti;
    reg              d_v;              reg [NO_LOG2-1:0] d_o;
    reg signed [35:0] prod;
    reg signed [38:0] acc;
    reg signed [35:0] gprod;
    reg signed [27:0] oacc [0:NO-1];

    wire signed [22:0] y_sh  = acc >>> 16;
    wire signed [17:0] y_sat = (y_sh > 23'sd131071)  ?  18'sd131071 :
                               (y_sh < -23'sd131072) ? -18'sd131072 : y_sh[17:0];

    // адреса чтения таблиц
    wire [TL-1:0] ti_next = (st == S_RUN) ? ((k == 7) ? ti + 1'b1 : ti) : {TL{1'b0}};
    always @(*) begin
        td_ra = (st == S_COPY) ? {act, ccnt[TL-1:0]} : {act, ti_next};
        tg_ra = (st == S_COPY) ? {act, ccnt[TL-1:0]} : {act, b_ti};
    end

    // порт записи: копирование банков важнее, иначе — запись из очереди
    wire          copy_wr = (st == S_COPY) && (ccnt != 0);
    wire [TL+24:0] q_head = q_mem[q_rp];
    wire          q_pop   = !copy_wr && (q_n != 0);
    always @(*) begin
        td_we = 1'b0; tg_we = 1'b0;
        td_wa = {~act, ccnt[TL-1:0] - 1'b1};
        tg_wa = {~act, ccnt[TL-1:0] - 1'b1};
        td_wd = td_q; tg_wd = tg_q;
        if (copy_wr) begin
            td_we = 1'b1; tg_we = 1'b1;
        end else if (q_pop) begin
            td_wa = {~act, q_head[TL+23:24]};
            tg_wa = {~act, q_head[TL+23:24]};
            td_wd = q_head[15:0];
            tg_wd = q_head[17:0];
            if (q_head[TL+24]) tg_we = 1'b1;
            else               td_we = 1'b1;
        end
    end

    always @(posedge clk)
        if (rst) begin
            q_wp <= 0; q_rp <= 0; q_n <= 0;
        end else begin
            if (cfg_we) begin
                q_mem[q_wp] <= {cfg_sel, cfg_idx, cfg_data};
                q_wp <= q_wp + 1'b1;
            end
            if (q_pop) q_rp <= q_rp + 1'b1;
            q_n <= q_n + (cfg_we ? 3'd1 : 3'd0) - (q_pop ? 3'd1 : 3'd0);
        end

    integer o;
    reg signed [35:0] osh;
    always @(posedge clk) begin
        we   <= 1'b0;
        done <= 1'b0;
        a_v  <= 1'b0;
        if (rst) begin
            st <= S_IDLE;
            wptr <= 0;
            commit_pending <= 1'b0;
            act <= 1'b0;
            r_v <= 1'b0; b_v <= 1'b0; c_v <= 1'b0; d_v <= 1'b0;
            b_ti <= 0;
            out_data <= 0;
        end else begin
            if (commit) commit_pending <= 1'b1;
            case (st)
                S_IDLE: if (tick) begin
                    in_lat <= in_data;
                    wptr   <= wptr + 1'b1;
                    wcnt   <= 0;
                    st     <= S_WRITE;
                    for (o = 0; o < NO; o = o + 1) oacc[o] <= 0;
                    // смена банков только когда очередь записей пуста
                    if ((commit_pending || commit) && q_n == 0 && !cfg_we) begin
                        commit_pending <= 1'b0;
                        act  <= ~act;
                        ccnt <= 0;
                        st   <= S_COPY;
                    end
                end
                S_COPY: begin
                    ccnt <= ccnt + 1'b1;
                    if (ccnt == NT) st <= S_WRITE;
                end
                S_WRITE: begin
                    we    <= 1'b1;
                    waddr <= {wcnt[NI_LOG2-1:0], wptr};
                    wdata <= in_lat[wcnt[NI_LOG2-1:0]*18 +: 18];
                    wcnt  <= wcnt + 1'b1;
                    if (wcnt == NI - 1) begin
                        st <= S_RUN;
                        ti <= 0;
                        k  <= 0;
                    end
                end
                S_RUN: begin
                    raddr <= {ti[NI_LOG2-1:0], rptr};
                    caddr <= {d_cur[4:0], k};
                    a_v   <= 1'b1;
                    a_k0  <= (k == 0);
                    a_k7  <= (k == 7);
                    a_ti  <= ti;
                    k     <= k + 1'b1;
                    if (k == 7) begin
                        ti <= ti + 1'b1;
                        if (ti == NT - 1) begin
                            st    <= S_DRAIN;
                            drain <= 0;
                        end
                    end
                end
                S_DRAIN: begin
                    drain <= drain + 1'b1;
                    if (drain == 9) begin
                        for (o = 0; o < NO; o = o + 1) begin
                            osh = oacc[o] <<< OUT_SHL;
                            out_data[o*24 +: 24] <= (osh > 36'sd8388607)  ? 24'h7FFFFF :
                                                    (osh < -36'sd8388608) ? 24'h800000 : osh[23:0];
                        end
                        done <= 1'b1;
                        st   <= S_IDLE;
                    end
                end
            endcase

            // стадия R: чтение буфера и ПЗУ коэффициентов
            r_v  <= a_v; r_k0 <= a_k0; r_k7 <= a_k7; r_ti <= a_ti;
            // стадия B: произведение отсчёта на коэффициент
            b_v  <= r_v; b_k0 <= r_k0; b_k7 <= r_k7; b_ti <= r_ti;
            if (r_v) prod <= x_rd * h_rd;
            // стадия C: накопление по отводам
            c_v  <= b_v & b_k7;
            c_ti <= b_ti;
            // (без конкатенаций: {..} в тернарном операторе делает выражение беззнаковым)
            if (b_v) begin
                if (b_k0) acc <= prod;
                else      acc <= acc + prod;
            end
            // стадия D: вес
            d_v <= c_v;
            d_o <= c_ti[TL-1:NI_LOG2];
            if (c_v) gprod <= y_sat * tg_q;
            // стадия E: сумма по входам
            if (d_v) oacc[d_o] <= oacc[d_o] + (gprod >>> 16);
        end
    end
endmodule
