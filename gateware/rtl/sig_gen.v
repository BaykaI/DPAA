// Генератор зондирующих/демонстрационных сигналов для одного луча.
//   режим 0 — тишина, 1 — синус (DDS), 2 — шум (xorshift32), 3 — ЛЧМ (чирп);
//   необязательный полосовой биквад (для шума), пачки (period/on_len)
//   и плавная огибающая, чтобы не было щелчков.
// Один отсчёт на строб tick (частота дискретизации кадра I2S).
module sig_gen (
    input  wire               clk,
    input  wire               rst,
    input  wire               tick,
    input  wire               cfg_we,
    input  wire [3:0]         cfg_addr,
    input  wire [23:0]        cfg_data,
    output reg  signed [17:0] sample,
    output reg                valid
);
    // ---- регистры настройки ----
    reg [1:0]  mode;
    reg [31:0] inc0, rate;
    reg [17:0] amp, env_step;
    reg [15:0] chirp_len, period, on_len;
    reg signed [17:0] b0, b1, b2, a1, a2;
    reg filt_en;

    always @(posedge clk)
        if (rst) begin
            mode <= 2'd1;                    // по умолчанию: синус 3 кГц, 1/8 шкалы
            inc0 <= 32'd263882791;           // 3000 Гц при fs = 48828.125 Гц
            amp  <= 18'd16384;
            rate <= 0; chirp_len <= 0; period <= 0; on_len <= 0;
            env_step <= 18'd128;
            // полоса 1.5–4.3 кГц (Баттерворт, 2-й порядок), Q2.16; включается регистром 0xF
            b0 <= 18'sd10097; b1 <= 18'sd0; b2 <= -18'sd10097;
            a1 <= -18'sd104945; a2 <= 18'sd45342;
            filt_en <= 1'b0;
        end else if (cfg_we)
            case (cfg_addr)
                4'h0: mode          <= cfg_data[1:0];
                4'h1: inc0[15:0]    <= cfg_data[15:0];
                4'h2: inc0[31:16]   <= cfg_data[15:0];
                4'h3: amp           <= cfg_data[17:0];
                4'h4: rate[15:0]    <= cfg_data[15:0];
                4'h5: rate[31:16]   <= cfg_data[15:0];
                4'h6: chirp_len     <= cfg_data[15:0];
                4'h7: period        <= cfg_data[15:0];
                4'h8: on_len        <= cfg_data[15:0];
                4'h9: env_step      <= cfg_data[17:0];
                4'hA: b0            <= cfg_data[17:0];
                4'hB: b1            <= cfg_data[17:0];
                4'hC: b2            <= cfg_data[17:0];
                4'hD: a1            <= cfg_data[17:0];
                4'hE: a2            <= cfg_data[17:0];
                4'hF: filt_en       <= cfg_data[0];
            endcase

    // ---- таблица синуса ----
    reg signed [17:0] sine_rom [0:1023];
    initial $readmemh("sine_1024.hex", sine_rom);

    // ---- состояние ----
    reg [31:0] phase, inc, rng;
    reg [15:0] chirp_cnt, per_cnt;
    reg [17:0] env;
    reg gate;
    reg [2:0] st;
    reg signed [17:0] rom_q, raw, x1, x2, y1, y2, filt;
    reg signed [35:0] p0, p1, p2, p3, p4;
    reg signed [36:0] prod;

    wire [31:0] r1 = rng ^ (rng << 13);
    wire [31:0] r2 = r1 ^ (r1 >> 17);
    wire [31:0] r3 = r2 ^ (r2 << 5);

    wire signed [37:0] fsum = p0 + p1 + p2 - p3 - p4;
    wire signed [21:0] fsh  = fsum >>> 16;
    wire signed [17:0] fsat = (fsh > 22'sd131071)  ?  18'sd131071 :
                              (fsh < -22'sd131072) ? -18'sd131072 : fsh[17:0];
    wire [17:0] target = (gate && mode != 2'd0) ? amp : 18'd0;

    always @(posedge clk) rom_q <= sine_rom[phase[31:22]];

    always @(posedge clk)
        if (rst) begin
            st <= 0; valid <= 1'b0; sample <= 0;
            phase <= 0; inc <= 32'd263882791; rng <= 32'h2545F491;
            chirp_cnt <= 0; per_cnt <= 0; env <= 0; gate <= 1'b1;
            x1 <= 0; x2 <= 0; y1 <= 0; y2 <= 0;
        end else begin
            valid <= 1'b0;
            case (st)
                0: if (tick) begin
                    // шаг DDS / ЛЧМ / шума; адрес таблицы синуса = старая фаза
                    phase <= phase + inc;
                    if (mode == 2'd3) begin
                        if (chirp_cnt + 1'b1 >= chirp_len) begin
                            chirp_cnt <= 0;
                            inc <= inc0;
                        end else begin
                            chirp_cnt <= chirp_cnt + 1'b1;
                            inc <= inc + rate;
                        end
                    end else begin
                        inc <= inc0;
                        chirp_cnt <= 0;
                    end
                    rng <= r3;
                    if (period == 0) begin
                        gate <= 1'b1;
                        per_cnt <= 0;
                    end else begin
                        gate <= (per_cnt < on_len);
                        per_cnt <= (per_cnt + 1'b1 >= period) ? 16'd0 : per_cnt + 1'b1;
                    end
                    st <= 1;
                end
                1: st <= 2;   // ожидание чтения таблицы
                2: begin
                    raw <= (mode == 2'd2) ? $signed(rng[17:0]) :
                           (mode == 2'd0) ? 18'sd0 : rom_q;
                    st <= 3;
                end
                3: begin
                    p0 <= b0 * raw; p1 <= b1 * x1; p2 <= b2 * x2;
                    p3 <= a1 * y1;  p4 <= a2 * y2;
                    st <= 4;
                end
                4: begin
                    x2 <= x1; x1 <= raw;
                    y2 <= y1; y1 <= fsat;
                    filt <= filt_en ? fsat : raw;
                    if (env < target)
                        env <= (target - env > env_step) ? env + env_step : target;
                    else if (env > target)
                        env <= (env - target > env_step) ? env - env_step : target;
                    st <= 5;
                end
                5: begin
                    prod <= filt * $signed({1'b0, env});
                    st <= 6;
                end
                default: begin
                    sample <= prod >>> 17;
                    valid <= 1'b1;
                    st <= 0;
                end
            endcase
        end
endmodule
