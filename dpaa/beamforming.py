"""Цифровое диаграммообразование на приём (ДОС).

* delay_and_sum — классическое фазирование «задержка и сумма» во временной области;
* stft_beamform — формирование луча в частотной области (по поддиапазонам);
* mvdr_weights  — адаптивный фильтр Кейпона (MVDR): луч на цель + нули на помехи;
* spatial_spectrum — «акустическая камера»: мощность по направлениям.
"""
import numpy as np
from scipy.signal import istft, stft

from .geometry import C_SOUND, direction, steering_delays, steering_vector
from .signals import fractional_delay


def delay_and_sum(x, positions, fs, az_deg=0.0, el_deg=0.0, focus=None,
                  weights=None, c=C_SOUND):
    """Луч «задержка-сумма»: выравнивание каналов дробными задержками и сложение.

    x: (N, T) сигналы микрофонов. Возвращает (T,).
    """
    x = np.asarray(x, dtype=float)
    tau = steering_delays(positions, az_deg, el_deg, focus=focus, c=c)
    amp = np.ones(len(x)) if weights is None else np.asarray(weights, dtype=float)
    y = fractional_delay(x, tau, fs)
    return (amp @ y) / amp.sum()


def _stft(x, fs, nperseg):
    return stft(x, fs, nperseg=nperseg, noverlap=nperseg * 3 // 4)


def _istft(Y, fs, nperseg):
    return istft(Y, fs, nperseg=nperseg, noverlap=nperseg * 3 // 4)[1]


def covariance(X):
    """Выборочные ковариационные матрицы по бинам: X (N, F, T) -> R (F, N, N)."""
    return np.einsum("nft,mft->fnm", X, X.conj()) / X.shape[-1]


def mvdr_weights(R, a, loading=1e-2):
    """Веса Кейпона w = R⁻¹a / (aᴴR⁻¹a) с диагональной регуляризацией.

    R: (F, N, N), a: (F, N). Возвращает (F, N).
    loading — доля от среднего собственного значения, добавляемая на диагональ.
    """
    n = R.shape[-1]
    tr = np.real(np.trace(R, axis1=1, axis2=2)) / n
    Rl = R + (loading * tr + 1e-20)[:, None, None] * np.eye(n)[None]
    Ria = np.linalg.solve(Rl, a[..., None])[..., 0]
    denom = np.einsum("fn,fn->f", a.conj(), Ria)
    return Ria / denom[:, None]


def stft_beamform(x, positions, fs, az_deg=0.0, el_deg=0.0, method="das",
                  x_train=None, nperseg=1024, loading=1e-2, c=C_SOUND):
    """Формирование луча в частотной области.

    method: "das" — обычное фазирование, "mvdr" — адаптивное (Кейпон).
    x_train — обучающая выборка для оценки ковариации (например, участок,
    где звучит только помеха); по умолчанию используется сам x.
    """
    f, _, X = _stft(np.asarray(x, dtype=float), fs, nperseg)
    proj = np.asarray(positions, dtype=float) @ direction(az_deg, el_deg) / c
    a = np.exp(2j * np.pi * np.outer(f, proj))  # (F, N)
    if method == "das":
        w = a / len(positions)
    elif method == "mvdr":
        Xt = X if x_train is None else _stft(np.asarray(x_train, dtype=float), fs, nperseg)[2]
        w = mvdr_weights(covariance(Xt), a, loading)
    else:
        raise ValueError(f"unknown method {method!r}")
    Y = np.einsum("fn,nft->ft", w.conj(), X)
    return _istft(Y, fs, nperseg)[: x.shape[-1]]


def spatial_spectrum(x, positions, fs, az_grid, f_lo, f_hi, method="das",
                     nperseg=1024, loading=1e-3, c=C_SOUND):
    """Пространственный спектр (мощность по направлениям), дБ — «акустическая камера».

    method: "das" — P(θ) = aᴴRa (обычный луч), "capon" — P(θ) = 1/(aᴴR⁻¹a).
    """
    f, _, X = _stft(np.asarray(x, dtype=float), fs, nperseg)
    band = (f >= f_lo) & (f <= f_hi)
    R = covariance(X[:, band, :])
    n = len(positions)
    dirs = direction(az_grid)
    P = np.zeros(len(az_grid))
    for fi, Rf in zip(f[band], R):
        A = steering_vector(positions, fi, dirs, c)  # (N, M)
        if method == "das":
            P += np.real(np.einsum("nm,nk,km->m", A.conj(), Rf, A)) / n**2
        elif method == "capon":
            tr = np.real(np.trace(Rf)) / n
            Ri = np.linalg.inv(Rf + loading * tr * np.eye(n))
            P += 1 / np.real(np.einsum("nm,nk,km->m", A.conj(), Ri, A))
        else:
            raise ValueError(f"unknown method {method!r}")
    return 10 * np.log10(P / P.max())
