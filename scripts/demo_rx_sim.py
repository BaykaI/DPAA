"""Демо на приём: 8 микрофонов, два источника звука, цифровое формирование лучей.

Запуск:  python scripts/demo_rx_sim.py

Сцена: «полезный» источник (мелодия) на −35°, «помеха» (шумовые слоги) на +25°,
оба на расстоянии 5 м. Полезный источник включается через 1.5 с — первые 1.5 с
служат обучающей выборкой для адаптивного луча (MVDR), как в РЛС.

Результат (out/rx/): mic1.wav (один микрофон), das_target.wav, das_interf.wav,
mvdr_target.wav; docs/img/08_acoustic_camera.png — пространственный спектр.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.io import wavfile  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dpaa import direction, ula  # noqa: E402
from dpaa.beamforming import delay_and_sum, spatial_spectrum, stft_beamform  # noqa: E402
from dpaa.propagation import simulate_free_field  # noqa: E402
from dpaa.signals import band_power_db, bandpass_noise, tone_sequence  # noqa: E402

FS = 48_000
N, D = 8, 0.04
POS = ula(N, D)
OUT = ROOT / "out" / "rx"
AZ_T, AZ_I, R = -35, 25, 5.0
BAND = (1000, 4300)
T_START = 1.5


def scene():
    notes = [1047, 1319, 1568, 2093, 1568, 1319] * 3
    mel = tone_sequence(notes, 0.3, FS)
    mel = mel + 0.5 * tone_sequence([2 * f for f in notes], 0.3, FS)  # 2-я гармоника
    target = np.concatenate([np.zeros(int(T_START * FS)), mel])
    syll = bandpass_noise(target.size / FS, FS, 1000, 4000, rng=5)
    t = np.arange(syll.size) / FS
    interf = syll * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t)) * 0.3  # «слоги» 4 Гц
    target = target / np.std(mel) * 0.3
    xt = simulate_free_field([(target, R * direction(AZ_T))], POS, FS)
    xi = simulate_free_field([(interf, R * direction(AZ_I))], POS, FS)
    noise = 1e-4 * np.random.default_rng(6).standard_normal(xt.shape)
    return xt, xi + noise


def sir(t, i):
    """Отношение сигнал/помеха на участке, где звучит цель."""
    s = slice(int(T_START * FS), None)
    return band_power_db(t[..., s], FS, *BAND) - band_power_db(i[..., s], FS, *BAND)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    xt, xi = scene()
    mix = xt + xi
    train = mix[:, : int(T_START * FS)]

    outs = {
        "mic1": (xt[0], xi[0]),
        "das_target": (delay_and_sum(xt, POS, FS, AZ_T), delay_and_sum(xi, POS, FS, AZ_T)),
        "das_interf": (delay_and_sum(xt, POS, FS, AZ_I), delay_and_sum(xi, POS, FS, AZ_I)),
        "mvdr_target": (stft_beamform(xt, POS, FS, AZ_T, method="mvdr", x_train=train),
                        stft_beamform(xi, POS, FS, AZ_T, method="mvdr", x_train=train)),
    }
    print("| выход | цель/помеха (SIR), дБ |")
    print("|---|---|")
    peak = max(np.max(np.abs(a + b)) for a, b in outs.values())
    for name, (a, b) in outs.items():
        print(f"| {name} | {sir(a, b):+.1f} |")
        wavfile.write(OUT / f"{name}.wav", FS, (0.9 * (a + b) / peak).astype(np.float32))

    grid = np.linspace(-90, 90, 721)
    fig, ax = plt.subplots(figsize=(8, 4))
    for method, label in (("das", "обычный луч (задержка-сумма)"), ("capon", "адаптивный (Кейпон)")):
        ax.plot(grid, spatial_spectrum(mix, POS, FS, grid, *BAND, method=method), label=label)
    for a in (AZ_T, AZ_I):
        ax.axvline(a, color="gray", ls="--", lw=0.8)
    ax.set(xlabel="направление, °", ylabel="мощность, дБ", ylim=(-30, 1),
           title="«Акустическая камера»: 8 микрофонов, два источника на −35° и +25°")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "img" / "08_acoustic_camera.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
