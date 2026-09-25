"""Демо на передачу: многоканальные WAV для решётки динамиков + «виртуальные слушатели».

Запуск:  python scripts/make_tx_demo.py

Результат (out/tx/):
  *_8ch.wav        — файлы для воспроизведения на 8 динамиках. Если стоять за решёткой
                     и смотреть туда же, куда она излучает: канал 1 — крайний левый
                     динамик, положительные углы — вправо;
  listen_*.wav     — что услышит человек, стоящий на 4 м под заданным углом
                     (моделирование, можно слушать в обычных наушниках);
  docs/img/07_tx_sweep_listeners.png — уровень звука у слушателей во времени.
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
from dpaa.propagation import radiate  # noqa: E402
from dpaa.signals import bandpass_noise, lfm_chirp, tone_sequence  # noqa: E402
from dpaa.transmit import multi_beam, sweep_signals, tx_signals, write_multichannel_wav  # noqa: E402

FS = 48_000
N, D = 8, 0.04
POS = ula(N, D)
OUT = ROOT / "out" / "tx"
LISTEN_R = 4.0


def listener(az):
    return LISTEN_R * direction(az)


def write_listeners(name, tx, angles):
    """Смоделировать и записать то, что слышат слушатели под углами angles."""
    ys = {a: radiate(tx, POS, listener(a), FS, tx.shape[1] + FS // 20) for a in angles}
    peak = max(np.max(np.abs(y)) for y in ys.values())
    for a, y in ys.items():
        wavfile.write(OUT / f"listen_{name}_{a:+d}deg.wav", FS, (0.9 * y / peak).astype(np.float32))
    return ys


def sweep():
    sig = bandpass_noise(12.0, FS, 1500, 4300, rng=0)
    tx, az = sweep_signals(sig, POS, FS, -60, 60, period=6.0)
    write_multichannel_wav(OUT / "sweep_8ch.wav", tx, FS)
    write_listeners("sweep", tx, [-40, 0, 40])

    # карта «угол слушателя — время»: где сейчас луч
    angles = np.arange(-80, 81, 4)
    hop = FS // 10
    level = []
    for a in angles:
        y = radiate(tx, POS, listener(a), FS)
        frames = y[: y.size // hop * hop].reshape(-1, hop)
        level.append(10 * np.log10(np.mean(frames**2, axis=1) + 1e-20))
    level = np.array(level)
    level -= level.max()
    t = np.arange(level.shape[1]) * hop / FS
    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.pcolormesh(t, angles, level, shading="auto", cmap="magma", vmin=-25, vmax=0)
    ax.plot(np.arange(az.size)[::hop] / FS, az[::hop], "c--", lw=0.8, label="заданное направление")
    ax.set(xlabel="время, с", ylabel="угол слушателя, °",
           title="Сканирование лучом: громкость у слушателей на 4 м (8 динамиков, 1.5–4.3 кГц)")
    ax.legend(loc="upper right")
    fig.colorbar(im, label="дБ")
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "img" / "07_tx_sweep_listeners.png", dpi=120)
    plt.close(fig)


def two_beams():
    """Два независимых луча с разными сигналами — фишка именно цифровой решётки."""
    notes = [2093, 2637, 3136, 2637, 2349, 2794, 3520, 2794] * 2  # C7 E7 G7 ...
    melody = tone_sequence(notes, 0.35, FS)
    pulses = np.concatenate([np.pad(lfm_chirp(0.12, FS, 1800, 4200), (0, int(0.28 * FS)))] * 14)
    n = min(melody.size, pulses.size)
    tx = multi_beam([dict(signal=melody[:n], az_deg=-35), dict(signal=pulses[:n], az_deg=35)], POS, FS)
    write_multichannel_wav(OUT / "two_beams_8ch.wav", tx, FS)
    write_listeners("two_beams", tx, [-35, 0, 35])


def prism():
    """Фазовращатели вместо задержек: луч «разводит» частоты по углам, как призма."""
    sig = bandpass_noise(8.0, FS, 1000, 4300, rng=1)
    for mode in ("phase", "ttd"):
        tx = tx_signals(sig, POS, FS, az_deg=40, mode=mode, f0=2000)
        write_multichannel_wav(OUT / f"prism_{mode}_8ch.wav", tx, FS)
        write_listeners(f"prism_{mode}", tx, [20, 40, 70])


def focus():
    """Фокусировка в точку ближней зоны — «акустический прожектор»."""
    sig = bandpass_noise(6.0, FS, 1500, 4300, rng=2)
    tx = tx_signals(sig, POS, FS, focus=(0.3, 1.0, 0.0))
    write_multichannel_wav(OUT / "focus_8ch.wav", tx, FS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sweep()
    two_beams()
    prism()
    focus()
    print("готово:", *sorted(p.name for p in OUT.iterdir()), sep="\n  ")
