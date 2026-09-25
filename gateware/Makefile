# Сборка прошивки ПЛИС для ULX3S (ECP5) открытыми инструментами:
#   yosys + nextpnr-ecp5 + ecppack; загрузка — openFPGALoader или fujprog.
#
#   make check      — синтез и разводка без привязки выводов: ресурсы и частота
#   make            — битстрим build/dpaa.bit (нужен официальный LPF платы, см. ниже)
#   make prog       — загрузить в ПЛИС (SRAM)
#   make flash      — записать во флеш (сохраняется после выключения)
#   make sim        — RTL-тесты (pytest)
#
# DEVICE: 85k (LFE5U-85F), 45k, 25k, 12k — по варианту платы ULX3S.
# BOARD_LPF: официальный файл ограничений ULX3S (ulx3s_v20.lpf из документации
# платы) — положить в gateware/. К нему добавляются настройки буферов ulx3s_dpaa_io.lpf.
DEVICE    ?= 85k
PACKAGE   ?= CABGA381
BOARD_LPF ?= ulx3s_v20.lpf
BUILD     := build
RTL     := rtl
SOURCES := $(addprefix $(RTL)/, pll_25_50.v i2s_clkgen.v i2s_tx.v i2s_rx.v uart_rx.v uart_tx.v \
           uart_cmd.v sig_gen.v delay_sum_engine.v dpaa_core.v top_ulx3s.v)
HEX     := $(RTL)/fd_coeffs.hex $(RTL)/sine_1024.hex
all: $(BUILD)/dpaa.bit

$(HEX): gen_mem.py ../dpaa/hw.py
	python3 gen_mem.py

$(BUILD)/dpaa.json: $(SOURCES) $(HEX)
	mkdir -p $(BUILD)
	cd $(RTL) && yosys -q -l ../$(BUILD)/yosys.log -p "synth_ecp5 -top top_ulx3s -json ../$@" $(notdir $(SOURCES))

$(BUILD)/dpaa.lpf: ulx3s_dpaa_io.lpf
	@test -f $(BOARD_LPF) || { echo "Нет $(BOARD_LPF): скачайте официальный LPF ULX3S (см. docs/hardware/pinout.md)"; exit 1; }
	cat $(BOARD_LPF) ulx3s_dpaa_io.lpf > $@

$(BUILD)/dpaa.config: $(BUILD)/dpaa.json $(BUILD)/dpaa.lpf
	nextpnr-ecp5 --$(DEVICE) --package $(PACKAGE) --json $< --lpf $(BUILD)/dpaa.lpf \
	  --freq 50 --textcfg $@ --report $(BUILD)/report.json -l $(BUILD)/nextpnr.log

# Проверка без привязки выводов (битстрим НЕ для загрузки в плату!)
check: $(BUILD)/dpaa.json
	nextpnr-ecp5 --$(DEVICE) --package $(PACKAGE) --json $< --lpf-allow-unconstrained \
	  --freq 50 --report $(BUILD)/check_report.json -l $(BUILD)/check.log
	@grep -E "TRELLIS_COMB|TRELLIS_FF|MULT18X18D|DP16KD|Max frequency" $(BUILD)/check.log | tail -6

$(BUILD)/dpaa.bit: $(BUILD)/dpaa.config
	ecppack --compress $< $@

prog: $(BUILD)/dpaa.bit
	openFPGALoader --board ulx3s $<

flash: $(BUILD)/dpaa.bit
	openFPGALoader --board ulx3s -f $<

sim:
	cd .. && python3 -m pytest -q tests/test_gateware.py

clean:
	rm -rf $(BUILD)

.PHONY: all check prog flash sim clean
