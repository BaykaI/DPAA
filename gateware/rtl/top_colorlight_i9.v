// Верхний уровень для Colorlight i9 (Lattice ECP5 LFE5U-45F) + плата расширения
// с DAPLink (JTAG + USB-UART) и 6 сдвоенными PMOD.
// Выводы — gateware/colorlight_i9_dpaa.lpf (заполнить по распиновке платы расширения).
//
// Wi‑Fi-пульт: отдельная плата ESP32-S3 DevKit, соединённая с ПЛИС по UART (esp_rx/esp_tx).
// Ноутбук: USB-UART отладчика DAPLink или любой адаптер CP2102/CH340 (usb_rx/usb_tx).
module top_colorlight_i9 (
    input  wire        clk25,       // генератор 25 МГц модуля i9
    output wire        led,         // светодиод модуля — «сердцебиение»
    input  wire        btn_test,    // кнопка на PMOD (необязательно): тестовый тон
    input  wire        usb_rx,      // от ноутбука к ПЛИС
    output wire        usb_tx,      // от ПЛИС к ноутбуку
    input  wire        esp_rx,      // от ESP32-S3 к ПЛИС
    output wire        esp_tx,      // от ПЛИС к ESP32-S3
    output wire        bclk,
    output wire        lrclk,
    output wire [15:0] txd,
    input  wire [16:0] rxd,
    output wire        mon_sd
);
    wire clk, locked;
    pll_25_50 u_pll (.clkin(clk25), .clkout0(clk), .locked(locked));

    reg [15:0] por = 0;
    always @(posedge clk)
        if (!locked) por <= 0;
        else if (!por[15]) por <= por + 1'b1;
    wire rst = !por[15];

    wire uart_tx;
    assign usb_tx = uart_tx;
    assign esp_tx = uart_tx;

    wire [7:0] leds;
    dpaa_core u_core (
        .clk(clk), .rst(rst),
        .uart_rx_a(usb_rx), .uart_rx_b(esp_rx), .uart_tx(uart_tx),
        .btn_test(btn_test),
        .bclk(bclk), .lrclk(lrclk), .txd(txd), .rxd(rxd), .mon_sd(mon_sd),
        .led(leds));
    assign led = leds[0];
endmodule
