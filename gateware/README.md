# Прошивка ПЛИС (Lattice ECP5: Colorlight i9 или ULX3S)

| Файл | Назначение |
|---|---|
| `rtl/top_colorlight_i9.v` | верхний уровень Colorlight i9 (основная плата): PLL, UART к ESP32-S3 и ноутбуку |
| `rtl/top_ulx3s.v` | верхний уровень ULX3S (альтернатива) |
| `colorlight_i9_dpaa.lpf` | ограничения i9 — шаблон, заполнить выводы по распиновке платы расширения |
| `rtl/dpaa_core.v` | ядро: регистры, генераторы, ДОС передачи и приёма, I2S, измерители |
| `rtl/delay_sum_engine.v` | цифровое диаграммообразование: дробная задержка + вес + сумма |
| `rtl/sig_gen.v` | генератор: синус (DDS), шум, ЛЧМ, пачки, биквад, огибающая |
| `rtl/i2s_clkgen.v`, `i2s_tx.v`, `i2s_rx.v` | общий такт и многоканальный I2S |
| `rtl/uart_rx.v`, `uart_tx.v`, `uart_cmd.v` | команды управления |
| `rtl/*.hex` | таблицы (генерируются `gen_mem.py` из `dpaa/hw.py`) |
| `tb/` | тестбенчи Icarus Verilog; запускаются из `tests/test_gateware.py` |

```bash
sudo apt install yosys nextpnr-ecp5 fpga-trellis iverilog openfpgaloader
make sim                 # RTL-тесты: ядро сверяется с Python-моделью бит в бит
make check               # синтез + разводка без привязки выводов (Colorlight i9): ресурсы и Fmax
make                     # битстрим для i9 (нужен заполненный colorlight_i9_dpaa.lpf)
make prog                # загрузка через DAPLink платы расширения
make BOARD=ulx3s ...     # то же для ULX3S (нужен официальный ulx3s_v20.lpf)
```

Проверено: `make check` для LFE5U-85F — 17 % LUT, 9 % FF, 16 умножителей, 9 блоков
памяти, Fmax ≈ 60 МГц при рабочих 50 МГц.
