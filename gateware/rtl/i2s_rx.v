// Многоканальный приёмник I2S (цифровые MEMS-микрофоны, вывод L/R = GND ->
// левый слот). Каждая линия — свой микрофон; 24 бита, старший бит первым.
module i2s_rx #(
    parameter NLINES = 17
) (
    input  wire                  clk,
    input  wire                  bit_sample,
    input  wire [5:0]            bit_idx,
    input  wire [NLINES-1:0]     sd_in,
    output reg  [NLINES*24-1:0]  data,
    output reg                   valid
);
    reg [NLINES-1:0] sd_q;
    reg [23:0] sh [0:NLINES-1];
    integer n;
    always @(posedge clk) begin
        sd_q  <= sd_in;
        valid <= 1'b0;
        if (bit_sample) begin
            if (!bit_idx[5] && bit_idx[4:0] >= 1 && bit_idx[4:0] <= 24)
                for (n = 0; n < NLINES; n = n + 1)
                    sh[n] <= {sh[n][22:0], sd_q[n]};
            if (bit_idx == 25) begin
                for (n = 0; n < NLINES; n = n + 1)
                    data[n*24 +: 24] <= sh[n];
                valid <= 1'b1;
            end
        end
    end
endmodule
