// Верхний уровень для платы ULX3S (Lattice ECP5).
// Назначение выводов — docs/hardware/pinout.md; ограничения — ulx3s_dpaa.lpf.
//
//   gp[0]  BCLK        gp[1]  LRCLK       gp[2..17] TXD0..TXD15 (усилители)
//   gp[18] MON_SD      gn[0..15] MIC0..MIC15  gn[16] CAL_MIC
//
// ESP32 на плате: wifi_en = 1 (включён), wifi_gpio0 = 1 (обычная загрузка).
// Команды управления принимаются и от ноутбука (USB-UART FTDI), и от ESP32.
module top_ulx3s (
    input  wire        clk_25mhz,
    input  wire [6:0]  btn,
    output wire [7:0]  led,
    input  wire        ftdi_txd,     // от ноутбука к ПЛИС
    output wire        ftdi_rxd,     // от ПЛИС к ноутбуку
    input  wire        wifi_txd,     // от ESP32 к ПЛИС
    output wire        wifi_rxd,     // от ПЛИС к ESP32
    output wire        wifi_en,
    output wire        wifi_gpio0,
    inout  wire [27:0] gp,
    inout  wire [27:0] gn
);
    wire clk, locked;
    pll_25_50 u_pll (.clkin(clk_25mhz), .clkout0(clk), .locked(locked));

    // сброс: ждём захвата PLL + ~1 мс; btn[0] (PWR) не используется
    reg [15:0] por = 0;
    always @(posedge clk)
        if (!locked) por <= 0;
        else if (!por[15]) por <= por + 1'b1;
    wire rst = !por[15];

    wire uart_tx;
    assign ftdi_rxd   = uart_tx;
    assign wifi_rxd   = uart_tx;
    assign wifi_en    = 1'b1;
    assign wifi_gpio0 = 1'b1;

    wire bclk, lrclk, mon_sd;
    wire [15:0] txd;
    dpaa_core u_core (
        .clk(clk), .rst(rst),
        .uart_rx_a(ftdi_txd), .uart_rx_b(wifi_txd), .uart_tx(uart_tx),
        .btn_test(btn[1]),   // FIRE1: проверочный тон 3 кГц по нормали, пока нажата
        .bclk(bclk), .lrclk(lrclk), .txd(txd), .rxd(gn[16:0]), .mon_sd(mon_sd),
        .led(led));

    assign gp[0]     = bclk;
    assign gp[1]     = lrclk;
    assign gp[17:2]  = txd;
    assign gp[18]    = mon_sd;
    assign gp[27:19] = 9'bz;
    assign gn        = 28'bz;
endmodule
