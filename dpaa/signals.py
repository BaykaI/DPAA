"""Цифровые «фазовращатели и линии задержки» и тестовые сигналы."""
import numpy as np
from scipy import signal as sps
from scipy.fft import irfft, next_fast_len, rfft, rfftfreq


def fractional_delay(x, delay_s, fs, length=None):
    """Задержка сигнала(ов) на произвольное (дробное) время через БПФ.

    Это цифровая «истинная временная задержка» (TTD): она одинаково верна
    для всех частот, поэтому луч не «уплывает» при широкополосном сигнале.

    x: (..., T); delay_s: скаляр или массив формы x.shape[:-1], все >= 0.
    length: длина результата (по умолчанию T).
    """
    x = np.asarray(x, dtype=float)
    delay_s = np.asarray(delay_s, dtype=float)
    if np.any(delay_s < 0):
        raise ValueError("delays must be non-negative")
    n = x.shape[-1]
    length = n if length is None else length
    max_shift = int(np.ceil(delay_s.max() * fs)) + 1 if delay_s.size else 1
    nfft = next_fast_len(max(n, length) + max_shift + 64)
    X = rfft(x, nfft)
    f = rfftfreq(nfft, 1 / fs)
    X = X * np.exp(-2j * np.pi * f * delay_s[..., None])
    return irfft(X, nfft)[..., :length]


def integer_delay(x, delay_s, fs, length=None):
    """Задержка, округлённая до целого числа отсчётов (грубая «линия задержки»)."""
    x = np.asarray(x, dtype=float)
    delay_s = np.broadcast_to(np.asarray(delay_s, dtype=float), x.shape[:-1])
    n = x.shape[-1]
    length = n if length is None else length
    out = np.zeros(x.shape[:-1] + (length,))
    for idx in np.ndindex(x.shape[:-1]):
        k = int(round(delay_s[idx] * fs))
        m = max(0, min(n, length - k))
        out[idx + (slice(k, k + m),)] = x[idx + (slice(0, m),)]
    return out


def phase_shift(x, phase_rad):
    """Постоянный по частоте фазовый сдвиг (идеальный узкополосный фазовращатель).

    Для частоты f0 он эквивалентен задержке phase/(2π f0), но для других частот
    нет — отсюда «косоглазие» (beam squint) решётки с фазовращателями.
    """
    x = np.asarray(x, dtype=float)
    phase_rad = np.asarray(phase_rad, dtype=float)
    n = x.shape[-1]
    X = rfft(x) * np.exp(-1j * phase_rad[..., None])
    return irfft(X, n)


def time_varying_delay(x, tau, fs, oversample=8):
    """Задержка, меняющаяся во времени: y_n(t) = x(t - tau_n(t)).

    x: (T,) исходный сигнал; tau: (N, T) задержки в секундах (>= 0).
    Используется для плавного сканирования лучом. Сигнал сначала
    передискретизируется в oversample раз, затем интерполируется линейно.
    """
    x = np.asarray(x, dtype=float)
    up = sps.resample_poly(x, oversample, 1)
    t_up = np.arange(up.size) / (fs * oversample)
    t = np.arange(x.size) / fs
    return np.stack([np.interp(t - tau_n, t_up, up, left=0.0, right=0.0) for tau_n in tau])


def fractional_delay_fir(delay_samples, ntaps=33):
    """КИХ-фильтр дробной задержки (окно Блэкмана + sinc) для работы в реальном времени.

    Полная задержка фильтра = (ntaps - 1)/2 + дробная часть delay_samples.
    Возвращает (taps, integer_part), где integer_part нужно реализовать сдвигом буфера.
    """
    integer_part = int(np.floor(delay_samples))
    frac = delay_samples - integer_part
    k = np.arange(ntaps) - (ntaps - 1) / 2 - frac
    taps = np.sinc(k) * np.blackman(ntaps)
    return taps / taps.sum(), integer_part


def bandpass_noise(duration, fs, f_lo, f_hi, rng=None):
    """Белый шум, ограниченный полосой [f_lo, f_hi], нормированный на RMS = 1."""
    rng = np.random.default_rng(rng)
    n = int(round(duration * fs))
    X = rfft(rng.standard_normal(n))
    f = rfftfreq(n, 1 / fs)
    X[(f < f_lo) | (f > f_hi)] = 0
    x = irfft(X, n)
    return x / np.sqrt(np.mean(x**2))


def tone_sequence(freqs, note_dur, fs, fade=0.01):
    """Последовательность тонов (простая «мелодия») с плавными краями."""
    n = int(round(note_dur * fs))
    t = np.arange(n) / fs
    env = np.ones(n)
    nf = int(fade * fs)
    env[:nf] = np.linspace(0, 1, nf)
    env[-nf:] = np.linspace(1, 0, nf)
    return np.concatenate([np.sin(2 * np.pi * f * t) * env for f in freqs])


def lfm_chirp(duration, fs, f0, f1):
    """ЛЧМ-импульс (как зондирующий сигнал радиолокатора) с окном Тьюки."""
    t = np.arange(int(round(duration * fs))) / fs
    return sps.chirp(t, f0, duration, f1) * sps.windows.tukey(t.size, 0.2)


def band_power_db(x, fs, f_lo, f_hi):
    """Мощность сигнала в полосе, дБ."""
    X = rfft(x)
    f = rfftfreq(x.shape[-1], 1 / fs)
    band = (f >= f_lo) & (f <= f_hi)
    return 10 * np.log10(np.sum(np.abs(X[..., band]) ** 2, axis=-1) + 1e-30)
