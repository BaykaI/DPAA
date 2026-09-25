# Прошивка ПЛИС (ULX3S / Lattice ECP5)

| Файл | Назначение |
|---|---|
| `rtl/top_ulx3s.v` | верхний уровень платы: PLL, назначение выводов, ESP32 |
| `rtl/dpaa_core.v` | ядро: регистры, генераторы, ДОС передачи и приёма, I2S, измерители |
| `rtl/delay_sum_engine.v` | цифровое диаграммообразование: дробная задержка + вес + сумма |
| `rtl/sig_gen.v` | генератор: синус (DDS), шум, ЛЧМ, пачки, биквад, огибающая |
| `rtl/i2s_clkgen.v`, `i2s_tx.v`, `i2s_rx.v` | общий такт и многоканальный I2S |
| `rtl/uart_rx.v`, `uart_tx.v`, `uart_cmd.v` | команды управления |
| `rtl/*.hex` | таблицы (генерируются `gen_mem.py` из `dpaa/hw.py`) |
| `tb/` | тестбенчи Icarus Verilog; запускаются из `tests/test_gateware.py` |

```bash
sudo apt install yosys nextpnr-ecp5 fpga-trellis iverilog openfpgaloader
make sim      # RTL-тесты: ядро сверяется с Python-моделью бит в бит
make check    # синтез + разводка без привязки выводов: ресурсы и Fmax
make          # битстрим (нужен официальный ulx3s_v20.lpf, см. docs/hardware/pinout.md)
make prog     # загрузка в ULX3S
```

Проверено: `make check` для LFE5U-85F — 17 % LUT, 9 % FF, 16 умножителей, 9 блоков
памяти, Fmax ≈ 60 МГц при рабочих 50 МГц.
