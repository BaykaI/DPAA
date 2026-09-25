"""Генерация таблиц для ПЛИС: коэффициенты дробной задержки и синус.

Запуск:  python gateware/gen_mem.py   (пишет gateware/rtl/*.hex)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from dpaa import hw  # noqa: E402


def main():
    rtl = HERE / "rtl"
    hw.write_hex(rtl / "fd_coeffs.hex", hw.fd_coefficients_int().ravel())
    hw.write_hex(rtl / "sine_1024.hex", hw.sine_table())
    print("written:", rtl / "fd_coeffs.hex", rtl / "sine_1024.hex")


if __name__ == "__main__":
    main()
