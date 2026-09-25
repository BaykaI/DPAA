"""Расчёт базовых параметров акустической ЦАФАР (таблицы для docs/concept.md).

Запуск:  python scripts/design_calc.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dpaa import C_SOUND, ula  # noqa: E402
from dpaa.geometry import fraunhofer_distance  # noqa: E402
from dpaa.patterns import array_factor, grating_lobe_free_freq, hpbw_deg  # noqa: E402

FS = 48_000
ANG = np.linspace(-90, 90, 7201)


def table(n, d):
    pos = ula(n, d)
    aperture = n * d
    print(f"\n### N = {n}, d = {d * 100:.1f} см, апертура {aperture * 100:.0f} см")
    print(f"f без дифракц. лепестков: {grating_lobe_free_freq(d):.0f} Гц (нормаль), "
          f"{grating_lobe_free_freq(d, 30):.0f} Гц (±30°), {grating_lobe_free_freq(d, 60):.0f} Гц (±60°)")
    print("| f, Гц | λ, см | ширина луча −3 дБ (нормаль) | при 30° | дальняя зона 2D²/λ, м |")
    print("|---|---|---|---|---|")
    for f in (500, 1000, 2000, 3000, 4000):
        bw0 = hpbw_deg(ANG, array_factor(pos, f, ANG, 0))
        bw30 = hpbw_deg(ANG, array_factor(pos, f, ANG, 30))
        print(f"| {f} | {C_SOUND / f * 100:.1f} | {bw0:.1f}° | {bw30:.1f}° | "
              f"{fraunhofer_distance(aperture, f):.2f} |")


def quantization():
    print("\n### Квантование задержки при целом числе отсчётов")
    print("| fs, кГц | шаг задержки, мкс | путь звука за шаг, мм | фазовая ошибка max при 4 кГц | эквивалент фазовращателя |")
    print("|---|---|---|---|---|")
    for fs in (16_000, 48_000, 96_000, 192_000):
        dt = 1 / fs
        step_deg = 360 * 4000 * dt
        bits = np.log2(360 / step_deg)
        print(f"| {fs / 1000:g} | {dt * 1e6:.1f} | {C_SOUND * dt * 1e3:.1f} | ±{step_deg / 2:.0f}° | ≈{bits:.1f} бит |")


def scale():
    print("\n### Масштаб «радио ↔ звук» (одинаковая длина волны)")
    print("| Диапазон РЛС | f радио | λ | f звука с той же λ |")
    print("|---|---|---|---|")
    for name, f in (("L", 1.3e9), ("S", 3e9), ("C", 5.5e9), ("X", 10e9), ("Ku", 15e9)):
        lam = 3e8 / f
        print(f"| {name} | {f / 1e9:g} ГГц | {lam * 100:.1f} см | {C_SOUND / lam:.0f} Гц |")
    print(f"\nКоэффициент масштаба времени: c_света / c_звука ≈ {3e8 / C_SOUND:.2e}")


if __name__ == "__main__":
    scale()
    table(8, 0.04)
    table(16, 0.04)
    quantization()
