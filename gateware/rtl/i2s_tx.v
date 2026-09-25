// Многоканальный передатчик I2S: NLINES линий данных с общими BCLK/LRCLK.
// 24-битные отсчёты, выровненные по старшему биту 32-битного слота.
// Отсчёты защёлкиваются в начале кадра.
// MONO = 1: в правый слот идёт тот же отсчёт, что в левый (вход right не используется,
// экономится половина регистров) — так питаются усилители решётки.
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
    reg [NLINES*24-1:0] l_q, r_q;
    wire [4:0] q = bit_idx[4:0];
    integer n;
    always @(posedge clk)
        if (bit_start) begin
            if (bit_idx == 0) begin
                l_q <= left;
                if (!MONO) r_q <= right;
            end
            for (n = 0; n < NLINES; n = n + 1)
                if (q == 0 || q > 24)
                    sd[n] <= 1'b0;
                else if (bit_idx[5])
                    sd[n] <= MONO ? l_q[n*24 + 24 - q] : r_q[n*24 + 24 - q];
                else
                    sd[n] <= (bit_idx == 0) ? 1'b0 : l_q[n*24 + 24 - q];
        end
endmodule
