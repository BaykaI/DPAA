// Тест ядра delay_sum_engine: сравнение с эталонной моделью dpaa.hw.engine_model.
// Файлы (пути задаются plusargs): CFG — записи {sel, idx[6:0], data[23:0]},
// IN — T*NI отсчётов по 18 бит, OUT — результат (NO значений в строке).
`timescale 1ns/1ps
module tb_engine;
    parameter NI_LOG2 = 1;
    parameter NO_LOG2 = 4;
    parameter OUT_SHL = 6;
    localparam NI = 1 << NI_LOG2;
    localparam NO = 1 << NO_LOG2;
    localparam TL = NI_LOG2 + NO_LOG2;

    reg clk = 0;
    always #10 clk = ~clk;
    reg rst = 1, tick = 0, cfg_we = 0, cfg_sel = 0, commit = 0;
    reg [TL-1:0] cfg_idx = 0;
    reg [23:0] cfg_data = 0;
    reg [NI*18-1:0] in_data = 0;
    wire [NO*24-1:0] out_data;
    wire done;

    delay_sum_engine #(.NI_LOG2(NI_LOG2), .NO_LOG2(NO_LOG2), .OUT_SHL(OUT_SHL)) dut (
        .clk(clk), .rst(rst), .tick(tick), .in_data(in_data),
        .cfg_we(cfg_we), .cfg_sel(cfg_sel), .cfg_idx(cfg_idx), .cfg_data(cfg_data),
        .commit(commit), .out_data(out_data), .done(done));

    reg [31:0] cfg_mem [0:4095];
    reg [17:0] in_mem  [0:1048575];
    integer ncfg, nfr, fo, n, i, o;
    reg [1023:0] fcfg, fin, fout;

    initial begin
        if (!$value$plusargs("CFG=%s", fcfg)) $fatal(1, "no CFG");
        if (!$value$plusargs("IN=%s", fin)) $fatal(1, "no IN");
        if (!$value$plusargs("OUT=%s", fout)) $fatal(1, "no OUT");
        if (!$value$plusargs("NCFG=%d", ncfg)) $fatal(1, "no NCFG");
        if (!$value$plusargs("NFR=%d", nfr)) $fatal(1, "no NFR");
        $readmemh(fcfg, cfg_mem);
        $readmemh(fin, in_mem);
        fo = $fopen(fout, "w");
        repeat (5) @(posedge clk);
        rst <= 0;
        @(posedge clk);
        for (n = 0; n < ncfg; n = n + 1) begin
            cfg_we   <= 1;
            cfg_sel  <= cfg_mem[n][31];
            cfg_idx  <= cfg_mem[n][30:24];
            cfg_data <= cfg_mem[n][23:0];
            @(posedge clk);
        end
        cfg_we <= 0;
        commit <= 1;
        @(posedge clk);
        commit <= 0;
        for (n = 0; n < nfr; n = n + 1) begin
            for (i = 0; i < NI; i = i + 1)
                in_data[i*18 +: 18] <= in_mem[n*NI + i];
            tick <= 1;
            @(posedge clk);
            tick <= 0;
            @(posedge done);
            @(posedge clk);
            for (o = 0; o < NO; o = o + 1)
                $fwrite(fo, "%h ", out_data[o*24 +: 24]);
            $fwrite(fo, "\n");
        end
        $fclose(fo);
        $finish;
    end
endmodule
