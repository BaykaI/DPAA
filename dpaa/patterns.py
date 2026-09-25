"""Диаграммы направленности (ДН) решётки: узкополосные и широкополосные."""
import warnings

import numpy as np
from scipy.signal import windows

from .geometry import C_SOUND, direction, steering_vector


def taper(n, kind="uniform", sidelobe_db=30):
    """Амплитудное распределение (весовое окно) по элементам, max = 1."""
    if kind == "uniform":
        w = np.ones(n)
    elif kind == "taylor":
        w = windows.taylor(n, nbar=4, sll=sidelobe_db, norm=False)
    elif kind == "chebyshev":
        with warnings.catch_warnings():  # предупреждение касается спектрального анализа, не решёток
            warnings.simplefilter("ignore", UserWarning)
            w = windows.chebwin(n, at=sidelobe_db)
    elif kind == "hann":
        w = windows.hann(n + 2)[1:-1]
    else:
        raise ValueError(f"unknown taper {kind!r}")
    return w / w.max()


def array_factor(positions, freq, scan_az, steer_az=0.0, weights=None,
                 scan_el=0.0, steer_el=0.0, c=C_SOUND):
    """Узкополосная ДН (комплексная), нормированная к 1 в максимуме при фазировании.

    weights — амплитудное распределение (по умолчанию равномерное).
    """
    n = len(positions)
    amp = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    w = amp * steering_vector(positions, freq, direction(steer_az, steer_el), c)
    a = steering_vector(positions, freq, direction(scan_az, scan_el), c)
    return (w.conj() @ a) / amp.sum()


def wideband_pattern(positions, freqs, scan_az, steer_az, mode="ttd", f0=None,
                     weights=None, fs=None, phase_bits=None, c=C_SOUND):
    """ДН как функция частоты и угла: |AF(f, θ)|, форма (F, M).

    mode:
      * "ttd"   — истинные временные задержки (цифровая дробная задержка);
      * "phase" — фазовращатели, настроенные на частоту f0 (луч «косит» с частотой).
    fs:         если задано — задержки округляются до целых отсчётов (квантование);
    phase_bits: если задано (режим "phase") — фаза квантуется на 2**bits уровней.
    """
    positions = np.asarray(positions, dtype=float)
    n = len(positions)
    amp = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    tau = positions @ direction(steer_az) / c
    tau = tau - tau.min()
    if fs is not None:
        tau = np.round(tau * fs) / fs
    a = np.stack([steering_vector(positions, f, direction(scan_az), c) for f in freqs])
    ref = positions @ direction(steer_az) / c
    ref = ref - ref.min()  # общий сдвиг не влияет на модуль ДН
    if mode == "ttd":
        w = amp[None, :] * np.exp(2j * np.pi * np.outer(freqs, tau))
    elif mode == "phase":
        if f0 is None:
            raise ValueError("mode='phase' requires f0")
        phi = 2 * np.pi * f0 * ref
        if phase_bits is not None:
            step = 2 * np.pi / 2**phase_bits
            phi = np.round(phi / step) * step
        w = np.broadcast_to(amp * np.exp(1j * phi), (len(freqs), n))
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return np.abs(np.einsum("fn,fnm->fm", w.conj(), a)) / amp.sum()


def db(x, floor=-60.0):
    """Модуль в дБ с ограничением снизу."""
    return np.maximum(20 * np.log10(np.abs(x) + 1e-12), floor)


def hpbw_deg(angles_deg, pattern):
    """Ширина луча по уровню -3 дБ (град), по главному максимуму."""
    p = np.abs(pattern) / np.abs(pattern).max()
    i0 = int(np.argmax(p))
    thr = 1 / np.sqrt(2)
    lo = i0
    while lo > 0 and p[lo] >= thr:
        lo -= 1
    hi = i0
    while hi < len(p) - 1 and p[hi] >= thr:
        hi += 1
    # линейная интерполяция краёв
    left = np.interp(thr, [p[lo], p[lo + 1]], [angles_deg[lo], angles_deg[lo + 1]])
    right = np.interp(thr, [p[hi], p[hi - 1]], [angles_deg[hi], angles_deg[hi - 1]])
    return right - left


def grating_lobe_free_freq(spacing, max_steer_deg=0.0, c=C_SOUND):
    """Максимальная частота без дифракционных лепестков: f < c / (d (1 + |sin θ|))."""
    return c / (spacing * (1 + abs(np.sin(np.deg2rad(max_steer_deg)))))
