// Сквозной тест ядра dpaa_core:
//   * команды по UART (файл CMD) настраивают генераторы и лучи;
//   * модели 17 I2S-микрофонов выдают отсчёты из файла MIC (17 значений на кадр);
//   * линии усилителей и ЦАП наушников декодируются и пишутся в TXO/MONO;
//   * ответы UART пишутся в RSPO.
`timescale 1ns/1ps
module tb_core;
    localparam UDIV = 4;
    reg clk = 0;
    always #10 clk = ~clk;
    reg rst = 1;
    reg urx = 1;
    wire utx, bclk, lrclk, mon_sd;
    wire [15:0] txd;
    reg  [16:0] rxd = 0;
    wire [7:0] led;

    dpaa_core #(.UART_DIV(UDIV), .UART_TIMEOUT(2000)) dut (
        .clk(clk), .rst(rst), .uart_rx_a(urx), .uart_rx_b(1'b1), .uart_tx(utx),
        .btn_test(1'b0), .bclk(bclk), .lrclk(lrclk), .txd(txd), .rxd(rxd),
        .mon_sd(mon_sd), .led(led));

    reg [7:0]  cmd_mem [0:65535];
    reg [23:0] mic_mem [0:2097151];
    integer ncmd, nfr, ftx, fmon, frsp, c, b, line;
    reg [1023:0] fcmd, fmic, ftxo, fmono, frspo;

    // ---- отправка команд ----
    task send_byte(input [7:0] v);
        integer j;
        begin
            urx <= 0; repeat (UDIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin
                urx <= v[j]; repeat (UDIV) @(posedge clk);
            end
            urx <= 1; repeat (UDIV * 2) @(posedge clk);
        end
    endtask

    // ---- модели микрофонов (L/R = GND -> левый слот) ----
    // Как настоящий MEMS-микрофон: WS защёлкивается по фронту SCK,
    // данные выдаются по спаду SCK, старший бит — через такт после смены WS.
    integer mic_frame = 0, mpos = 0;
    reg ws_prev = 1;
    reg [23:0] mic_cur [0:16];
    always @(posedge bclk) begin
        if (lrclk != ws_prev) begin
            mpos = 0;
            if (!lrclk) begin
                for (line = 0; line < 17; line = line + 1)
                    mic_cur[line] = mic_mem[mic_frame*17 + line];
                mic_frame = mic_frame + 1;
            end
        end else
            mpos = mpos + 1;
        ws_prev = lrclk;
    end
    always @(negedge bclk)
        for (line = 0; line < 17; line = line + 1)
            rxd[line] <= #30 (!ws_prev && mpos + 1 >= 1 && mpos + 1 <= 24) ? mic_cur[line][23 - mpos] : 1'b0;

    // ---- декодирование линий I2S ----
    integer dbit = 0, n;
    reg lr_prev_p = 1;
    reg [23:0] tl [0:15];
    reg [23:0] tr [0:15];
    reg [23:0] ml, mr;
    always @(posedge bclk) begin
        if (lrclk != lr_prev_p) begin
            if (!lrclk) begin   // начался новый кадр — записываем предыдущий
                for (n = 0; n < 16; n = n + 1) $fwrite(ftx, "%h ", tl[n]);
                $fwrite(ftx, "\n");
                for (n = 0; n < 16; n = n + 1) if (tl[n] !== tr[n]) $fwrite(ftx, "# L!=R line %0d\n", n);
                $fwrite(fmon, "%h %h\n", ml, mr);
            end
            dbit = 0;
        end else
            dbit = dbit + 1;
        lr_prev_p = lrclk;
        if (dbit >= 1 && dbit <= 24) begin
            for (n = 0; n < 16; n = n + 1)
                if (!lrclk) tl[n] = {tl[n][22:0], txd[n]};
                else        tr[n] = {tr[n][22:0], txd[n]};
            if (!lrclk) ml = {ml[22:0], mon_sd};
            else        mr = {mr[22:0], mon_sd};
        end
    end

    // ---- приём ответов UART ----
    reg [7:0] rb;
    integer k;
    always begin
        @(negedge utx);
        repeat (UDIV / 2) @(posedge clk);
        for (k = 0; k < 8; k = k + 1) begin
            repeat (UDIV) @(posedge clk);
            rb[k] = utx;
        end
        repeat (UDIV) @(posedge clk);
        $fwrite(frsp, "%h\n", rb);
    end

    initial begin
        if (!$value$plusargs("CMD=%s", fcmd)) $fatal(1, "no CMD");
        if (!$value$plusargs("MIC=%s", fmic)) $fatal(1, "no MIC");
        if (!$value$plusargs("TXO=%s", ftxo)) $fatal(1, "no TXO");
        if (!$value$plusargs("MONO=%s", fmono)) $fatal(1, "no MONO");
        if (!$value$plusargs("RSPO=%s", frspo)) $fatal(1, "no RSPO");
        if (!$value$plusargs("NCMD=%d", ncmd)) $fatal(1, "no NCMD");
        if (!$value$plusargs("NFR=%d", nfr)) $fatal(1, "no NFR");
        $readmemh(fcmd, cmd_mem);
        $readmemh(fmic, mic_mem);
        ftx = $fopen(ftxo, "w");
        fmon = $fopen(fmono, "w");
        frsp = $fopen(frspo, "w");
        repeat (10) @(posedge clk);
        rst <= 0;
        repeat (10) @(posedge clk);
        for (c = 0; c < ncmd; c = c + 1) send_byte(cmd_mem[c]);
        $fwrite(ftx, "# commands done\n");
        $fwrite(fmon, "# commands done\n");
        repeat (nfr * 1024) @(posedge clk);
        $fclose(ftx); $fclose(fmon); $fclose(frsp);
        $finish;
    end
endmodule
