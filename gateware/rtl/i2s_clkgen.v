// Тактирование I2S для всех каналов решётки (общий BCLK/LRCLK = когерентность).
// BCLK = clk / 2^DIV_LOG2, кадр = 64 такта BCLK (два слота по 32 бита).
// LRCLK = 0 — левый слот, 1 — правый (стандарт Philips I2S).
module i2s_clkgen #(
    parameter DIV_LOG2 = 4,
    parameter SAMPLE_PHASE = 14     // такт внутри периода BCLK, когда защёлкиваются входы
) (
    input  wire       clk,
    input  wire       rst,
    output wire       bclk,
    output wire       lrclk,
    output wire       frame_start,  // строб: начало кадра
    output wire       bit_start,    // строб: спад BCLK (смена данных на выходах)
    output wire       bit_sample,   // строб: момент выборки входных данных
    output wire [5:0] bit_idx       // номер такта BCLK в кадре
);
    reg [DIV_LOG2+5:0] cnt;
    always @(posedge clk)
        if (rst) cnt <= 0;
        else     cnt <= cnt + 1'b1;

    wire [DIV_LOG2-1:0] sub = cnt[DIV_LOG2-1:0];
    assign bit_idx     = cnt[DIV_LOG2+5:DIV_LOG2];
    assign bclk        = cnt[DIV_LOG2-1];
    assign lrclk       = bit_idx[5];
    assign bit_start   = (sub == 0);
    assign frame_start = (cnt == 0);
    assign bit_sample  = (sub == SAMPLE_PHASE);
endmodule
