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
// Таблицы пишутся в теневые регистры и применяются атомарно в начале кадра
// после строба commit — луч переключается без «разрыва».
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

    // ---- таблицы ----
    reg [15:0]        dly_sh [0:NT-1];
    reg [15:0]        dly    [0:NT-1];
    reg signed [17:0] gn_sh  [0:NT-1];
    reg signed [17:0] gn     [0:NT-1];
    reg commit_pending;
    integer t;

    always @(posedge clk)
        if (rst) begin
            for (t = 0; t < NT; t = t + 1) begin
                dly_sh[t] <= DELAY_INIT;
                gn_sh[t]  <= ((t % NI) == 0) ? GAIN_IN0 : GAIN_OTHER;
            end
        end else if (cfg_we) begin
            if (cfg_sel) gn_sh[cfg_idx]  <= cfg_data[17:0];
            else         dly_sh[cfg_idx] <= cfg_data[15:0];
        end

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
    localparam S_IDLE = 2'd0, S_WRITE = 2'd1, S_RUN = 2'd2, S_DRAIN = 2'd3;
    reg [1:0]            st;
    reg [(NI*18)-1:0]    in_lat;
    reg [DEPTH_LOG2-1:0] wptr;
    reg [NI_LOG2:0]      wcnt;
    reg [TL-1:0]         ti;
    reg [2:0]            k;
    reg [3:0]            drain;

    // выдача адресов (стадия A)
    wire [15:0]            d_cur = dly[ti];
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
            r_v <= 1'b0; b_v <= 1'b0; c_v <= 1'b0; d_v <= 1'b0;
            out_data <= 0;
            for (t = 0; t < NT; t = t + 1) begin
                dly[t] <= DELAY_INIT;
                gn[t]  <= ((t % NI) == 0) ? GAIN_IN0 : GAIN_OTHER;
            end
        end else begin
            if (commit) commit_pending <= 1'b1;
            case (st)
                S_IDLE: if (tick) begin
                    in_lat <= in_data;
                    wptr   <= wptr + 1'b1;
                    wcnt   <= 0;
                    st     <= S_WRITE;
                    for (o = 0; o < NO; o = o + 1) oacc[o] <= 0;
                    if (commit_pending || commit) begin
                        commit_pending <= 1'b0;
                        for (t = 0; t < NT; t = t + 1) begin
                            dly[t] <= dly_sh[t];
                            gn[t]  <= gn_sh[t];
                        end
                    end
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
            if (c_v) gprod <= y_sat * gn[c_ti];
            // стадия E: сумма по входам
            if (d_v) oacc[d_o] <= oacc[d_o] + (gprod >>> 16);
        end
    end
endmodule
