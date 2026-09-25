# Сборка прошивки ПЛИС (Lattice ECP5) открытыми инструментами:
#   yosys + nextpnr-ecp5 + ecppack; загрузка — openFPGALoader.
#
#   make check          — синтез и разводка без привязки выводов: ресурсы и частота
#   make                — битстрим build/<плата>/dpaa.bit (нужен заполненный LPF, см. ниже)
#   make prog           — загрузить в ПЛИС (SRAM)
#   make flash          — записать во флеш (сохраняется после выключения)
#   make sim            — RTL-тесты (pytest)
#
# BOARD=i9     — Colorlight i9 v7.2 (LFE5U-45F) + плата расширения (основной вариант)
#                ограничения: colorlight_i9_dpaa.lpf (заменить все SITE "???")
# BOARD=i5     — Colorlight i5 (LFE5U-25F), та же плата расширения; colorlight_i5_dpaa.lpf
#                (разводка модулей i5 и i9 может отличаться — выводы заполнять по своей ревизии)
# BOARD=ulx3s  — ULX3S (LFE5U-85F); ограничения: официальный ulx3s_v20.lpf платы
#                + настройки буферов ulx3s_dpaa_io.lpf
BOARD ?= i9

ifeq ($(BOARD),ulx3s)
  DEVICE  ?= 85k
  TOP     := top_ulx3s
  LPF_SRC := ulx3s_v20.lpf ulx3s_dpaa_io.lpf
  PROG    := openFPGALoader --board ulx3s
else ifeq ($(BOARD),i9)
  DEVICE  ?= 45k
  TOP     := top_colorlight_i9
  LPF_SRC := colorlight_i9_dpaa.lpf
  PROG    := openFPGALoader -c cmsisdap
else ifeq ($(BOARD),i5)
  DEVICE  ?= 25k
  TOP     := top_colorlight_i9
  LPF_SRC := colorlight_i5_dpaa.lpf
  PROG    := openFPGALoader -c cmsisdap
else
  $(error BOARD must be i9, i5 or ulx3s)
endif

PACKAGE ?= CABGA381
BUILD   := build/$(BOARD)
RTL     := rtl
CORE    := pll_25_50.v i2s_clkgen.v i2s_tx.v i2s_rx.v uart_rx.v uart_tx.v \
           uart_cmd.v sig_gen.v delay_sum_engine.v dpaa_core.v
SOURCES := $(addprefix $(RTL)/, $(CORE) $(TOP).v)
HEX     := $(RTL)/fd_coeffs.hex $(RTL)/sine_1024.hex

all: $(BUILD)/dpaa.bit

$(HEX): gen_mem.py ../dpaa/hw.py
	python3 gen_mem.py

$(BUILD)/dpaa.json: $(SOURCES) $(HEX)
	mkdir -p $(BUILD)
	cd $(RTL) && yosys -q -l ../$(BUILD)/yosys.log -p "synth_ecp5 -top $(TOP) -json ../$@" $(notdir $(SOURCES))

# Файл ограничений: все исходные файлы должны существовать, заглушек "???" быть не должно
$(BUILD)/dpaa.lpf: $(wildcard $(LPF_SRC))
	@for f in $(LPF_SRC); do test -f $$f || { echo "Нет $$f (см. docs/hardware/pinout.md)"; exit 1; }; done
	@if grep -q '???' $(LPF_SRC); then echo "В $(LPF_SRC) остались SITE \"???\": заполните выводы по распиновке платы"; exit 1; fi
	mkdir -p $(BUILD)
	cat $(LPF_SRC) > $@

$(BUILD)/dpaa.config: $(BUILD)/dpaa.json $(BUILD)/dpaa.lpf
	nextpnr-ecp5 --$(DEVICE) --package $(PACKAGE) --json $< --lpf $(BUILD)/dpaa.lpf \
	  --freq 50 --router router2 --textcfg $@ --report $(BUILD)/report.json -l $(BUILD)/nextpnr.log

# Проверка без привязки выводов (битстрим НЕ для загрузки в плату!)
check: $(BUILD)/dpaa.json
	nextpnr-ecp5 --$(DEVICE) --package $(PACKAGE) --json $< --lpf-allow-unconstrained \
	  --freq 50 --router router2 --report $(BUILD)/check_report.json -l $(BUILD)/check.log
	@grep -E "TRELLIS_COMB|TRELLIS_FF|MULT18X18D|DP16KD|Max frequency" $(BUILD)/check.log | tail -6

$(BUILD)/dpaa.bit: $(BUILD)/dpaa.config
	ecppack --compress $< $@

prog: $(BUILD)/dpaa.bit
	$(PROG) $<

flash: $(BUILD)/dpaa.bit
	$(PROG) -f $<

sim:
	cd .. && python3 -m pytest -q tests/test_gateware.py

clean:
	rm -rf build

.PHONY: all check prog flash sim clean
