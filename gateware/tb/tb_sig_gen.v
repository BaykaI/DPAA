// Тест генератора: записи регистров из файла CFG ({addr[3:0], data[23:0]}), NFR отсчётов -> OUT.
`timescale 1ns/1ps
module tb_sig_gen;
    reg clk = 0;
    always #10 clk = ~clk;
    reg rst = 1, tick = 0, we = 0;
    reg [3:0] addr = 0;
    reg [23:0] data = 0;
    wire signed [17:0] sample;
    wire valid;
    sig_gen dut (.clk(clk), .rst(rst), .tick(tick), .cfg_we(we), .cfg_addr(addr),
                 .cfg_data(data), .sample(sample), .valid(valid));
    reg [27:0] cfg [0:255];
    integer ncfg, nfr, fo, n;
    reg [1023:0] fcfg, fout;
    initial begin
        if (!$value$plusargs("CFG=%s", fcfg)) $fatal(1, "no CFG");
        if (!$value$plusargs("OUT=%s", fout)) $fatal(1, "no OUT");
        if (!$value$plusargs("NCFG=%d", ncfg)) $fatal(1, "no NCFG");
        if (!$value$plusargs("NFR=%d", nfr)) $fatal(1, "no NFR");
        $readmemh(fcfg, cfg);
        fo = $fopen(fout, "w");
        repeat (3) @(posedge clk);
        rst <= 0;
        for (n = 0; n < ncfg; n = n + 1) begin
            we <= 1; addr <= cfg[n][27:24]; data <= cfg[n][23:0];
            @(posedge clk);
        end
        we <= 0;
        for (n = 0; n < nfr; n = n + 1) begin
            tick <= 1; @(posedge clk); tick <= 0;
            @(posedge valid); @(posedge clk);
            $fwrite(fo, "%h\n", sample);
            repeat (4) @(posedge clk);
        end
        $fclose(fo);
        $finish;
    end
endmodule
