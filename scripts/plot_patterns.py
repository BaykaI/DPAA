"""Графики, иллюстрирующие принципы ЦАФАР на акустической решётке.

Запуск:  python scripts/plot_patterns.py        (картинки в docs/img/)
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dpaa import C_SOUND, ula  # noqa: E402
from dpaa.patterns import array_factor, db, taper, wideband_pattern  # noqa: E402

OUT = ROOT / "docs" / "img"
ANG = np.linspace(-90, 90, 1801)
N, D = 8, 0.04
POS = ula(N, D)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=120)
    plt.close(fig)
    print("saved", OUT / name)


def steering():
    fig, ax = plt.subplots(figsize=(8, 4))
    for s in (0, 30, 60):
        ax.plot(ANG, db(array_factor(POS, 3000, ANG, steer_az=s)), label=f"луч на {s}°")
    ax.set(xlabel="угол, °", ylabel="уровень, дБ", ylim=(-40, 1),
           title=f"Электронное сканирование: {N} динамиков, шаг {D * 100:.0f} см, 3 кГц")
    ax.grid(alpha=0.3)
    ax.legend()
    save(fig, "01_steering.png")


def grating():
    fig, ax = plt.subplots(figsize=(8, 4))
    f = 3000
    lam = C_SOUND / f
    for k in (0.5, 1.0, 1.5):
        pos = ula(N, k * lam)
        ax.plot(ANG, db(array_factor(pos, f, ANG, steer_az=20)), label=f"d = {k:g}λ ({k * lam * 100:.1f} см)")
    ax.set(xlabel="угол, °", ylabel="уровень, дБ", ylim=(-40, 1),
           title="Дифракционные лепестки: при d > λ/2 появляются «лишние» лучи (луч на 20°)")
    ax.grid(alpha=0.3)
    ax.legend()
    save(fig, "02_grating_lobes.png")


def tapering():
    fig, ax = plt.subplots(figsize=(8, 4))
    pos = ula(16, D)
    for kind in ("uniform", "taylor", "chebyshev"):
        w = taper(16, kind, sidelobe_db=35)
        ax.plot(ANG, db(array_factor(pos, 3500, ANG, weights=w)), label=kind)
    ax.set(xlabel="угол, °", ylabel="уровень, дБ", ylim=(-60, 1),
           title="Амплитудное распределение: боковые лепестки vs ширина луча (16 эл., 3.5 кГц)")
    ax.grid(alpha=0.3)
    ax.legend()
    save(fig, "03_tapering.png")


def squint():
    freqs = np.linspace(500, 4300, 300)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, mode, title in ((axs[0], "phase", "Фазовращатели (настроены на 2 кГц)"),
                            (axs[1], "ttd", "Истинная задержка (цифровая ЦАФАР)")):
        p = wideband_pattern(POS, freqs, ANG, 40, mode=mode, f0=2000)
        im = ax.pcolormesh(ANG, freqs / 1000, db(p, -30), shading="auto", cmap="magma", vmin=-30, vmax=0)
        ax.axvline(40, color="c", lw=0.8, ls="--")
        ax.set(title=title, xlabel="угол, °")
    axs[0].set_ylabel("частота, кГц")
    fig.colorbar(im, ax=axs, label="дБ")
    fig.suptitle("Широкополосный сигнал, луч на 40°: «косоглазие» луча (beam squint)")
    fig.savefig(OUT / "04_squint.png", dpi=120)
    plt.close(fig)
    print("saved", OUT / "04_squint.png")


def quantization():
    freqs = np.array([3500.0])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(ANG, db(wideband_pattern(POS, freqs, ANG, 23, mode="ttd")[0]), label="дробная задержка (точно)")
    for fs in (48_000, 16_000):
        p = wideband_pattern(POS, freqs, ANG, 23, mode="ttd", fs=fs)[0]
        ax.plot(ANG, db(p), label=f"задержка кратна отсчёту, fs = {fs // 1000} кГц")
    ax.set(xlabel="угол, °", ylabel="уровень, дБ", ylim=(-40, 1),
           title="Квантование задержек (аналог дискретного фазовращателя), луч на 23°, 3.5 кГц")
    ax.grid(alpha=0.3)
    ax.legend()
    save(fig, "05_quantization.png")


def beamwidth_vs_freq():
    freqs = np.linspace(300, 6000, 300)
    fig, ax = plt.subplots(figsize=(8, 4))
    p = wideband_pattern(POS, freqs, ANG, 0, mode="ttd")
    ax.pcolormesh(ANG, freqs / 1000, db(p, -30), shading="auto", cmap="magma", vmin=-30, vmax=0)
    ax.axhline(C_SOUND / (2 * D) / 1000, color="c", ls="--", lw=0.8)
    ax.text(-88, C_SOUND / (2 * D) / 1000 + 0.1, "d = λ/2", color="c")
    ax.set(xlabel="угол, °", ylabel="частота, кГц",
           title="Почему низкие частоты «не рулятся»: ширина луча ~ λ / апертура")
    save(fig, "06_beamwidth_vs_freq.png")


if __name__ == "__main__":
    steering()
    grating()
    tapering()
    squint()
    quantization()
    beamwidth_vs_freq()
