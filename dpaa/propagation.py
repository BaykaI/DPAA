"""Простейшая модель распространения звука в свободном поле (без отражений)."""
import numpy as np

from .geometry import C_SOUND
from .signals import fractional_delay


def simulate_free_field(sources, receivers, fs, length=None, c=C_SOUND,
                        noise_std=0.0, rng=None):
    """Сигналы на приёмниках от набора точечных источников.

    sources:   список пар (signal (T,), position (3,));
    receivers: координаты приёмников (M, 3).
    Учитываются задержка распространения r/c и затухание 1/r (нормировано к 1 м).
    Возвращает массив (M, length).
    """
    receivers = np.asarray(receivers, dtype=float)
    if length is None:
        length = max(len(s) for s, _ in sources)
    out = np.zeros((len(receivers), length))
    for sig, pos in sources:
        r = np.linalg.norm(receivers - np.asarray(pos, dtype=float), axis=1)
        sig = np.broadcast_to(np.asarray(sig, dtype=float), (len(receivers), len(sig)))
        out += fractional_delay(sig, r / c, fs, length) / r[:, None]
    if noise_std > 0:
        out += noise_std * np.random.default_rng(rng).standard_normal(out.shape)
    return out


def radiate(element_signals, element_positions, listener, fs, length=None, c=C_SOUND):
    """Что услышит слушатель в точке listener от решётки излучателей.

    element_signals: (N, T) сигналы, поданные на излучатели (ненаправленные).
    Возвращает (T',) — сумму вкладов всех излучателей.
    """
    element_positions = np.asarray(element_positions, dtype=float)
    r = np.linalg.norm(element_positions - np.asarray(listener, dtype=float), axis=1)
    if length is None:
        length = element_signals.shape[-1]
    y = fractional_delay(element_signals, r / c, fs, length) / r[:, None]
    return y.sum(axis=0)
