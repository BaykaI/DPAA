"""Цифровое диаграммообразование на передачу: сигналы для каждого излучателя."""
import numpy as np
from scipy.io import wavfile

from .geometry import C_SOUND, direction, steering_delays
from .signals import fractional_delay, integer_delay, phase_shift, time_varying_delay


def tx_signals(signal, positions, fs, az_deg=0.0, el_deg=0.0, focus=None,
               weights=None, mode="ttd", f0=None, c=C_SOUND):
    """Сигналы для N излучателей, формирующих луч в заданном направлении/точке.

    mode:
      * "ttd"       — точные дробные задержки (правильная широкополосная ЦАФАР);
      * "integer"   — задержки, округлённые до целых отсчётов (квантование);
      * "phase"     — постоянный фазовый сдвиг, рассчитанный на частоту f0
                      (имитация фазовращателей — луч «косит» по частоте).
    Возвращает (N, T + max_delay).
    """
    signal = np.asarray(signal, dtype=float)
    n = len(positions)
    tau = steering_delays(positions, az_deg, el_deg, focus=focus, c=c)
    amp = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    length = signal.size + int(np.ceil(tau.max() * fs)) + 1
    tiled = np.broadcast_to(signal, (n, signal.size))
    if mode == "ttd":
        out = fractional_delay(tiled, tau, fs, length)
    elif mode == "integer":
        out = integer_delay(tiled, tau, fs, length)
    elif mode == "phase":
        if f0 is None:
            raise ValueError("mode='phase' requires f0")
        padded = np.pad(tiled, ((0, 0), (0, length - signal.size)))
        out = phase_shift(padded, 2 * np.pi * f0 * tau)
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return out * amp[:, None]


def multi_beam(beams, positions, fs, c=C_SOUND):
    """Несколько одновременных лучей с разными сигналами (суперпозиция).

    beams: список словарей с ключами signal, az_deg и (опционально) остальными
    аргументами tx_signals. Возвращает сумму (N, T).
    """
    parts = [tx_signals(positions=positions, fs=fs, c=c, **b) for b in beams]
    length = max(p.shape[1] for p in parts)
    out = np.zeros((len(positions), length))
    for p in parts:
        out[:, : p.shape[1]] += p
    return out


def sweep_signals(signal, positions, fs, az_start, az_stop, weights=None,
                  period=None, c=C_SOUND):
    """Плавное сканирование луча от az_start до az_stop (и обратно, если задан period).

    Задержки меняются во времени непрерывно — как при электронном сканировании.
    """
    signal = np.asarray(signal, dtype=float)
    t = np.arange(signal.size) / fs
    if period is None:
        az = az_start + (az_stop - az_start) * t / t[-1]
    else:  # треугольная «пила» туда-обратно
        phase = (t / period) % 1.0
        tri = 1 - np.abs(2 * phase - 1)
        az = az_start + (az_stop - az_start) * tri
    p = np.asarray(positions, dtype=float)
    tau = (p @ direction(az).T) / c  # (N, T)
    max_span = np.max(np.abs(p[:, 0])) * 2 / c
    tau = tau - tau.min(axis=0, keepdims=True)
    tau = tau + (max_span - tau.max(axis=0, keepdims=True)) / 2  # центрируем, >= 0
    amp = np.ones(len(p)) if weights is None else np.asarray(weights, dtype=float)
    return time_varying_delay(signal, tau, fs) * amp[:, None], az


def write_multichannel_wav(path, x, fs, peak=0.9):
    """Записать (N, T) как N-канальный WAV float32 с нормировкой пика."""
    x = np.asarray(x, dtype=float)
    scale = peak / max(np.max(np.abs(x)), 1e-12)
    wavfile.write(path, int(fs), (x.T * scale).astype(np.float32))
