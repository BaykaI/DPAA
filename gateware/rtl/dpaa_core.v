// Ядро акустической ЦАФАР (независимо от платы).
//
//   генераторы (2 луча) -> ДОС передачи (2 x 16) -> I2S -> 16 усилителей MAX98357A
//   16 MEMS-микрофонов -> I2S -> ДОС приёма (16 x 2) -> I2S -> ЦАП наушников
//   + калибровочный микрофон (17-я линия), измерители уровня, UART-управление.
//
// Все каналы тактируются общими BCLK/LRCLK — это и есть «когерентность»
// решётки: задержки между каналами задаются только цифровой обработкой.
module dpaa_core #(
    parameter UART_DIV     = 50,     // 1 Мбод при 50 МГц
    parameter UART_TIMEOUT = 5000,
    parameter BCLK_DIV_LOG2 = 4
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        uart_rx_a,    // от ноутбука (FTDI)
    input  wire        uart_rx_b,    // от ESP32
    output wire        uart_tx,      // ответы (в обе стороны)
    input  wire        btn_test,     // удержание — принудительное излучение (проверка)
    output wire        bclk,
    output wire        lrclk,
    output wire [15:0] txd,          // данные усилителей
    input  wire [16:0] rxd,          // данные микрофонов (16 + калибровочный)
    output wire        mon_sd,       // ЦАП наушников (левое/правое ухо = лучи приёма 0/1)
    output wire [7:0]  led
);
    // ---------------- тактирование I2S ----------------
    wire frame_start, bit_start, bit_sample;
    wire [5:0] bit_idx;
    i2s_clkgen #(.DIV_LOG2(BCLK_DIV_LOG2), .SAMPLE_PHASE((1 << BCLK_DIV_LOG2) - 2)) u_clk (
        .clk(clk), .rst(rst), .bclk(bclk), .lrclk(lrclk),
        .frame_start(frame_start), .bit_start(bit_start),
        .bit_sample(bit_sample), .bit_idx(bit_idx));

    // ---------------- UART и шина регистров ----------------
    wire [7:0] ra_d, rb_d;
    wire ra_v, rb_v;
    uart_rx #(.CLKS_PER_BIT(UART_DIV)) u_rxa (.clk(clk), .rst(rst), .rx(uart_rx_a), .data(ra_d), .valid(ra_v));
    uart_rx #(.CLKS_PER_BIT(UART_DIV)) u_rxb (.clk(clk), .rst(rst), .rx(uart_rx_b), .data(rb_d), .valid(rb_v));
    wire wa, rda, wb, rdb;
    wire [14:0] aa, ab;
    wire [23:0] da, db;
    uart_cmd #(.TIMEOUT(UART_TIMEOUT)) u_cmda (.clk(clk), .rst(rst), .rx_data(ra_d), .rx_valid(ra_v),
        .wr(wa), .rd(rda), .addr(aa), .data(da));
    uart_cmd #(.TIMEOUT(UART_TIMEOUT)) u_cmdb (.clk(clk), .rst(rst), .rx_data(rb_d), .rx_valid(rb_v),
        .wr(wb), .rd(rdb), .addr(ab), .data(db));

    // приоритет у ноутбука; одновременное завершение двух кадров почти невозможно
    wire        bus_wr   = wa | wb;
    wire        bus_rd   = rda | rdb;
    wire [14:0] bus_addr = (wa | rda) ? aa : ab;
    wire [23:0] bus_data = wa ? da : db;

    // ---------------- регистры управления ----------------
    reg [1:0] ctrl;             // bit0 — передача, bit1 — приём
    reg commit_tx, commit_rx;
    always @(posedge clk) begin
        commit_tx <= 1'b0;
        commit_rx <= 1'b0;
        if (rst) ctrl <= 2'b10;  // после включения динамики молчат
        else if (bus_wr && bus_addr == 15'h0002) ctrl <= bus_data[1:0];
        else if (bus_wr && bus_addr == 15'h0003) begin
            commit_tx <= bus_data[0];
            commit_rx <= bus_data[1];
        end
    end
    wire tx_en = ctrl[0] | btn_test;
    wire rx_en = ctrl[1];

    // ---------------- генераторы ----------------
    wire signed [17:0] g0, g1;
    wire gv0, gv1;
    sig_gen u_gen0 (.clk(clk), .rst(rst), .tick(frame_start),
        .cfg_we(bus_wr && bus_addr[14:4] == 11'h001), .cfg_addr(bus_addr[3:0]), .cfg_data(bus_data),
        .sample(g0), .valid(gv0));
    sig_gen u_gen1 (.clk(clk), .rst(rst), .tick(frame_start),
        .cfg_we(bus_wr && bus_addr[14:4] == 11'h002), .cfg_addr(bus_addr[3:0]), .cfg_data(bus_data),
        .sample(g1), .valid(gv1));

    // ---------------- ДОС передачи: 2 луча -> 16 излучателей ----------------
    wire [16*24-1:0] tx_out;
    wire tx_done;
    delay_sum_engine #(.NI_LOG2(1), .NO_LOG2(4), .OUT_SHL(6),
                       .GAIN_IN0(18'd32768), .GAIN_OTHER(18'd0)) u_tx (
        .clk(clk), .rst(rst), .tick(frame_start), .in_data({g1, g0}),
        .cfg_we(bus_wr && bus_addr[14:8] == 7'h10), .cfg_sel(bus_addr[7]),
        .cfg_idx(bus_addr[4:0]), .cfg_data(bus_data), .commit(commit_tx),
        .out_data(tx_out), .done(tx_done));

    wire [16*24-1:0] tx_gated = tx_en ? tx_out : {16*24{1'b0}};
    i2s_tx #(.NLINES(16)) u_i2s_tx (.clk(clk), .bit_start(bit_start), .bit_idx(bit_idx),
        .left(tx_gated), .right(tx_gated), .sd(txd));

    // ---------------- приём: 16 микрофонов + калибровочный ----------------
    wire [17*24-1:0] mic;
    wire mic_v;
    i2s_rx #(.NLINES(17)) u_i2s_rx (.clk(clk), .bit_sample(bit_sample), .bit_idx(bit_idx),
        .sd_in(rxd), .data(mic), .valid(mic_v));

    // старшие 18 бит 24-битного отсчёта
    wire [16*18-1:0] mic18;
    genvar gi;
    generate
        for (gi = 0; gi < 16; gi = gi + 1) begin : g_mic
            assign mic18[gi*18 +: 18] = mic[gi*24 + 6 +: 18];
        end
    endgenerate

    wire [2*24-1:0] rx_out;
    wire rx_done;
    delay_sum_engine #(.NI_LOG2(4), .NO_LOG2(1), .OUT_SHL(6),
                       .GAIN_IN0(18'd4096), .GAIN_OTHER(18'd4096)) u_rx (
        .clk(clk), .rst(rst), .tick(frame_start), .in_data(mic18),
        .cfg_we(bus_wr && bus_addr[14:8] == 7'h20), .cfg_sel(bus_addr[7]),
        .cfg_idx(bus_addr[4:0]), .cfg_data(bus_data), .commit(commit_rx),
        .out_data(rx_out), .done(rx_done));

    wire [2*24-1:0] rx_gated = rx_en ? rx_out : {2*24{1'b0}};
    i2s_tx #(.NLINES(1)) u_i2s_mon (.clk(clk), .bit_start(bit_start), .bit_idx(bit_idx),
        .left(rx_gated[23:0]), .right(rx_gated[47:24]), .sd(mon_sd));

    // ---------------- измерители уровня и счётчик кадров ----------------
    reg [23:0] frames;
    reg [23:0] peak [0:16];
    integer pi;
    always @(posedge clk)
        if (rst) begin
            frames <= 0;
            for (pi = 0; pi < 17; pi = pi + 1) peak[pi] <= 0;
        end else begin
            if (frame_start) frames <= frames + 1'b1;
            for (pi = 0; pi < 17; pi = pi + 1)
                if (bus_rd && bus_addr == 15'h0100 + pi)
                    peak[pi] <= 0;
                else if (mic_v) begin
                    if (mic[pi*24+23] ? (-mic[pi*24 +: 24]) > peak[pi] : mic[pi*24 +: 24] > peak[pi])
                        peak[pi] <= mic[pi*24+23] ? -mic[pi*24 +: 24] : mic[pi*24 +: 24];
                end
        end

    // ---------------- ответы на чтение ----------------
    reg [23:0] rd_val;
    always @(*) begin
        rd_val = 24'h0;
        if (bus_addr == 15'h0000) rd_val = 24'hDAA001;
        else if (bus_addr == 15'h0001) rd_val = frames;
        else if (bus_addr == 15'h0002) rd_val = {22'd0, ctrl};
        else if (bus_addr[14:5] == 10'h008 && bus_addr[4:0] < 17) rd_val = peak[bus_addr[4:0]];
    end

    reg [55:0] rsp;
    reg [2:0]  rsp_n;
    reg        tx_start;
    reg [7:0]  tx_byte;
    wire       tx_busy;
    always @(posedge clk) begin
        tx_start <= 1'b0;
        if (rst) rsp_n <= 0;
        else if (bus_rd && rsp_n == 0) begin
            rsp   <= {8'h5A, 1'b1, bus_addr, rd_val,
                      (8'h5A ^ {1'b1, bus_addr[14:8]} ^ bus_addr[7:0] ^ rd_val[23:16] ^ rd_val[15:8] ^ rd_val[7:0])};
            rsp_n <= 7;
        end else if (rsp_n != 0 && !tx_busy && !tx_start) begin
            tx_start <= 1'b1;
            tx_byte  <= rsp[55:48];
            rsp      <= {rsp[47:0], 8'h00};
            rsp_n    <= rsp_n - 1'b1;
        end
    end
    uart_tx #(.CLKS_PER_BIT(UART_DIV)) u_utx (.clk(clk), .rst(rst), .data(tx_byte),
        .start(tx_start), .tx(uart_tx), .busy(tx_busy));

    // ---------------- светодиоды ----------------
    reg [19:0] act;
    always @(posedge clk)
        if (rst) act <= 0;
        else if (ra_v | rb_v) act <= 20'hFFFFF;
        else if (act != 0) act <= act - 1'b1;
    assign led = {peak[0][22:19], act != 0, rx_en, tx_en, frames[14]};
endmodule
