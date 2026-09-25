// Передатчик UART 8N1.
module uart_tx #(
    parameter CLKS_PER_BIT = 50
) (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] data,
    input  wire       start,
    output reg        tx,
    output wire       busy
);
    reg [15:0] cnt;
    reg [3:0] bitn;
    reg [9:0] sh;
    reg run;
    assign busy = run;
    always @(posedge clk)
        if (rst) begin
            run <= 1'b0;
            tx  <= 1'b1;
        end else if (!run) begin
            tx <= 1'b1;
            if (start) begin
                sh   <= {1'b1, data, 1'b0};
                run  <= 1'b1;
                cnt  <= 0;
                bitn <= 0;
            end
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end else begin
            cnt <= CLKS_PER_BIT - 1;
            if (bitn == 10) begin
                run <= 1'b0;
            end else begin
                tx   <= sh[0];
                sh   <= {1'b1, sh[9:1]};
                bitn <= bitn + 1'b1;
            end
        end
endmodule
