// Приёмник UART 8N1.
module uart_rx #(
    parameter CLKS_PER_BIT = 50
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output reg  [7:0] data,
    output reg        valid
);
    reg [2:0] sync = 3'b111;
    reg [15:0] cnt;
    reg [3:0] bitn;
    reg busy;
    reg [7:0] sh;
    always @(posedge clk) begin
        sync  <= {sync[1:0], rx};
        valid <= 1'b0;
        if (rst) begin
            busy <= 1'b0;
        end else if (!busy) begin
            if (!sync[2]) begin            // старт-бит
                busy <= 1'b1;
                cnt  <= CLKS_PER_BIT / 2;
                bitn <= 0;
            end
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end else begin
            cnt <= CLKS_PER_BIT - 1;
            if (bitn == 0) begin
                if (sync[2]) busy <= 1'b0;  // ложный старт
            end else if (bitn <= 8) begin
                sh <= {sync[2], sh[7:1]};
            end else begin
                busy <= 1'b0;
                if (sync[2]) begin          // стоп-бит корректен
                    data  <= sh;
                    valid <= 1'b1;
                end
            end
            bitn <= bitn + 1'b1;
        end
    end
endmodule
