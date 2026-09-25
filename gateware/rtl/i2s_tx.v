// Многоканальный передатчик I2S: NLINES линий данных с общими BCLK/LRCLK.
// 24-битные отсчёты, выровненные по старшему биту 32-битного слота.
// Отсчёты защёлкиваются в начале кадра.
// MONO = 1: в правый слот идёт тот же отсчёт, что в левый (вход right не используется,
// экономится половина регистров) — так питаются усилители решётки.
//
// Каждая линия — кольцевой сдвиговый регистр: на каждом из 24 бит слота выдаётся
// старший бит и слово поворачивается на 1; через 24 такта оно возвращается на место,
// поэтому в режиме MONO тот же регистр без перезагрузки обслуживает и правый слот.
module i2s_tx #(
    parameter NLINES = 16,
    parameter MONO   = 0
) (
    input  wire                  clk,
    input  wire                  bit_start,
    input  wire [5:0]            bit_idx,
    input  wire [NLINES*24-1:0]  left,
    input  wire [NLINES*24-1:0]  right,
    output reg  [NLINES-1:0]     sd
);
    reg [23:0] l_sh [0:NLINES-1];
    reg [23:0] r_sh [0:NLINES-1];
    wire [4:0] q = bit_idx[4:0];
    wire       data_bit = (q != 0) && (q <= 24);
    integer n;
    always @(posedge clk)
        if (bit_start) begin
            for (n = 0; n < NLINES; n = n + 1) begin
                if (bit_idx == 0) begin
                    l_sh[n] <= left[n*24 +: 24];
                    if (!MONO) r_sh[n] <= right[n*24 +: 24];
                    sd[n] <= 1'b0;
                end else if (!data_bit) begin
                    sd[n] <= 1'b0;
                end else if (bit_idx[5] && !MONO) begin
                    sd[n]   <= r_sh[n][23];
                    r_sh[n] <= {r_sh[n][22:0], r_sh[n][23]};
                end else begin
                    sd[n]   <= l_sh[n][23];
                    l_sh[n] <= {l_sh[n][22:0], l_sh[n][23]};
                end
            end
        end
endmodule
