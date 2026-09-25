// Разбор команд управления из UART.
// Кадр: A5 A1 A0 D2 D1 D0 CHK, CHK = A1^A0^D2^D1^D0^5A.
// Старший бит A1 = 1 — запрос чтения регистра, иначе запись.
module uart_cmd #(
    parameter TIMEOUT = 5000        // сброс разбора при паузе внутри кадра (такты)
) (
    input  wire        clk,
    input  wire        rst,
    input  wire [7:0]  rx_data,
    input  wire        rx_valid,
    output reg         wr,
    output reg         rd,
    output reg  [14:0] addr,
    output reg  [23:0] data
);
    reg [2:0]  idx;
    reg [7:0]  b1, b2, b3, b4, b5;
    reg [15:0] tmo;
    wire [7:0] chk = b1 ^ b2 ^ b3 ^ b4 ^ b5 ^ 8'h5A;
    always @(posedge clk) begin
        wr <= 1'b0;
        rd <= 1'b0;
        if (rst) begin
            idx <= 0;
            tmo <= 0;
        end else if (rx_valid) begin
            tmo <= 0;
            case (idx)
                0: if (rx_data == 8'hA5) idx <= 1;
                1: begin b1 <= rx_data; idx <= 2; end
                2: begin b2 <= rx_data; idx <= 3; end
                3: begin b3 <= rx_data; idx <= 4; end
                4: begin b4 <= rx_data; idx <= 5; end
                5: begin b5 <= rx_data; idx <= 6; end
                default: begin
                    idx <= 0;
                    if (rx_data == chk) begin
                        addr <= {b1[6:0], b2};
                        data <= {b3, b4, b5};
                        wr   <= ~b1[7];
                        rd   <=  b1[7];
                    end
                end
            endcase
        end else if (idx != 0) begin
            tmo <= tmo + 1'b1;
            if (tmo == TIMEOUT) idx <= 0;
        end
    end
endmodule
