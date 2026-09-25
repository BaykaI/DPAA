"""Аппаратная модель акустической ЦАФАР на ПЛИС (ULX3S / ECP5).

Здесь собрано всё, что должно совпадать «бит в бит» между Python и RTL:
  * тактирование и частота дискретизации;
  * коэффициенты фильтра дробной задержки и таблица синуса (hex-файлы для ПЛИС);
  * форматы регистров (задержка, усиление, частота генератора) и карта адресов;
  * протокол команд по UART;
  * эталонная целочисленная модель ядра диаграммообразования (delay_sum_engine.v).
"""
from pathlib import Path

import numpy as np
from scipy import signal as sps

from .geometry import C_SOUND, direction, near_field_vector, ula  # noqa: F401

# --- Тактирование -----------------------------------------------------------
F_CLK = 50_000_000            # системная частота ПЛИС (PLL 25 -> 50 МГц)
BCLK_DIV_LOG2 = 4             # BCLK = F_CLK / 16 = 3.125 МГц
FRAME_CLKS = 1024             # 64 такта BCLK на кадр I2S
FS = F_CLK / FRAME_CLKS       # 48828.125 Гц

# --- Решётка ------------------------------------------------------------------
N_ELEM = 16
PITCH = 0.04
# микрофон стоит в углу плитки держателя: +14.8 мм вправо и +14.8 мм вверх от центра
# динамика (hardware/mech/dpaa_element.scad); вверх = ось z модели решётки
MIC_OFFSET = np.array([0.0148, 0.0, 0.0148])

# --- Ядро дробной задержки ----------------------------------------------------
W = 18                        # разрядность отсчётов и коэффициентов (умножитель 18x18)
TAPS = 8
TAP_CENTER = 3                # минимальная допустимая целая задержка
PHASE_BITS = 5                # 32 фазы -> шаг 1/32 отсчёта (0.64 мкс, 0.2 мм пути звука)
PHASES = 1 << PHASE_BITS
COEF_FRAC = 16                # коэффициенты и усиления в формате Q2.16
DEPTH = 256                   # глубина кольцевого буфера на вход
MAX_DELAY = DEPTH - TAPS      # максимальная целая часть задержки
UNITY = 1 << COEF_FRAC        # усиление 1.0

# --- Карта регистров (адрес 16 бит, данные 24 бита) ----------------------------
REG_ID = 0x0000               # R: идентификатор/версия
REG_FRAMES = 0x0001           # R: счётчик кадров
REG_CTRL = 0x0002             # W: bit0 — передача разрешена, bit1 — приём разрешён
REG_COMMIT = 0x0003           # W: bit0 — применить таблицы TX, bit1 — таблицы RX
GEN_BASE = (0x0010, 0x0020)   # W: генераторы сигналов для луча 0 и 1
REG_PEAK = 0x0100             # R: пиковый уровень микрофона i (0x0100 + i), сброс при чтении
TX_DELAY, TX_GAIN = 0x1000, 0x1080
RX_DELAY, RX_GAIN = 0x2000, 0x2080
ID_VALUE = 0xDAA001

# смещения регистров генератора
GEN_MODE, GEN_INC_LO, GEN_INC_HI, GEN_AMP = 0, 1, 2, 3
GEN_RATE_LO, GEN_RATE_HI, GEN_CHIRP_LEN, GEN_PERIOD = 4, 5, 6, 7
GEN_ON_LEN, GEN_ENV_STEP, GEN_B0, GEN_B1, GEN_B2, GEN_A1, GEN_A2, GEN_FILT = range(8, 16)
MODE_OFF, MODE_SINE, MODE_NOISE, MODE_CHIRP = 0, 1, 2, 3

TX_BEAMS = 2                  # независимых лучей на передачу
RX_BEAMS = 2                  # лучей на приём (левое и правое ухо наушников)
N_MICS = 16

SYNC_CMD, SYNC_RSP = 0xA5, 0x5A


# --- Коэффициенты -------------------------------------------------------------
def fd_coefficients(phases=PHASES, taps=TAPS, center=TAP_CENTER, band=0.2, lam=1e-4):
    """Фильтры дробной задержки (float), форма (phases, taps).

    Для фазы p фильтр приближает задержку (center + p/phases) отсчёта методом
    наименьших квадратов в полосе [0, band·fs] с небольшой регуляризацией
    (чтобы не усиливать сигнал вне полосы). Ошибка ≈ −78 дБ до 0.12·fs.
    """
    ff = np.linspace(0, band, 400)
    k = np.arange(taps)
    A = np.exp(-2j * np.pi * np.outer(ff, k))
    Ar = np.vstack([A.real, A.imag, np.sqrt(lam) * np.eye(taps)])
    h = np.zeros((phases, taps))
    for p in range(phases):
        d = np.exp(-2j * np.pi * ff * (center + p / phases))
        dr = np.concatenate([d.real, d.imag, np.zeros(taps)])
        h[p] = np.linalg.lstsq(Ar, dr, rcond=None)[0]
    return h


def quantize(x, frac=COEF_FRAC, bits=W):
    q = np.round(np.asarray(x) * (1 << frac)).astype(np.int64)
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return np.clip(q, lo, hi)


def fd_coefficients_int():
    return quantize(fd_coefficients())


def sine_table(n=1024, bits=W):
    amp = (1 << (bits - 1)) - 1
    return np.round(amp * np.sin(2 * np.pi * np.arange(n) / n)).astype(np.int64)


def write_hex(path, values, bits=W):
    mask = (1 << bits) - 1
    digits = (bits + 3) // 4
    Path(path).write_text("".join(f"{int(v) & mask:0{digits}x}\n" for v in values))


# --- Форматы регистров ----------------------------------------------------------
def delay_reg(delay_samples):
    """Задержка в отсчётах -> регистр (целая часть << 5 | фаза), с округлением до 1/32."""
    q = np.round(np.asarray(delay_samples, dtype=float) * PHASES).astype(np.int64)
    if np.any(q < TAP_CENTER * PHASES) or np.any(q >= MAX_DELAY * PHASES):
        raise ValueError(f"delay out of range [{TAP_CENTER}, {MAX_DELAY}) samples")
    return q


def gain_reg(gain):
    return quantize(gain)


def phase_inc(freq_hz, fs=FS):
    return int(round(freq_hz / fs * 2**32)) & 0xFFFFFFFF


def biquad_bandpass(f_lo, f_hi, fs=FS):
    """Коэффициенты полосового биквада (Q2.16) для генератора шума: b0 b1 b2 a1 a2."""
    b, a = sps.butter(1, [f_lo, f_hi], btype="bandpass", fs=fs)
    return [int(v) for v in quantize([b[0], b[1], b[2], a[1], a[2]])]


# --- Расчёт таблиц для ЦАФАР -----------------------------------------------------
def element_positions(n=N_ELEM, pitch=PITCH):
    """Центры динамиков."""
    return ula(n, pitch)


def mic_positions(n=N_MICS, pitch=PITCH):
    """Акустические отверстия микрофонов (сдвинуты от центров динамиков на MIC_OFFSET)."""
    return ula(n, pitch) + MIC_OFFSET


def beam_delays(az_deg=0.0, focus=None, positions=None, c=C_SOUND, fs=FS, margin=TAP_CENTER + 1):
    """Задержки (в отсчётах) для луча на передачу/приём, минимальная = margin."""
    from .geometry import steering_delays

    p = element_positions() if positions is None else positions
    return steering_delays(p, az_deg, focus=focus, c=c) * fs + margin


# --- Протокол UART ------------------------------------------------------------------
def encode_write(addr, data):
    """Кадр записи: A5 A1 A0 D2 D1 D0 CHK, CHK = A1^A0^D2^D1^D0^0x5A."""
    addr &= 0x7FFF
    data = int(data) & 0xFFFFFF
    body = [addr >> 8, addr & 0xFF, data >> 16, (data >> 8) & 0xFF, data & 0xFF]
    chk = 0x5A
    for b in body:
        chk ^= b
    return bytes([SYNC_CMD, *body, chk])


def encode_read(addr):
    frame = bytearray(encode_write(addr, 0))
    frame[1] |= 0x80
    frame[6] ^= 0x80
    return bytes(frame)


def decode_response(frame):
    if len(frame) != 7 or frame[0] != SYNC_RSP:
        raise ValueError("bad response frame")
    chk = 0x5A
    for b in frame[1:6]:
        chk ^= b
    if chk != frame[6]:
        raise ValueError("bad checksum")
    return ((frame[1] & 0x7F) << 8) | frame[2], (frame[3] << 16) | (frame[4] << 8) | frame[5]


def element_weights(n, taper="uniform", sll_db=30.0, weights=None, off=()):
    """Амплитудное распределение по элементам (max = 1).

    taper:   "uniform", "taylor", "chebyshev", "hann" — окно с уровнем боковых sll_db;
    weights: произвольные веса (перекрывают taper), могут быть отрицательными;
    off:     номера элементов (с 0), которые выключаются — «отказ» или прореживание.
    """
    from .patterns import taper as window

    w = np.asarray(weights, dtype=float) if weights is not None else window(n, taper, sll_db)
    if w.shape != (n,):
        raise ValueError(f"need {n} weights, got {w.shape}")
    w = w.copy()
    w[list(off)] = 0.0
    if not np.any(w):
        raise ValueError("all elements are off")
    return w / np.max(np.abs(w))


def tx_beam_commands(beam, az_deg=None, focus=None, gains=None, n_out=N_ELEM,
                     taper="uniform", sll_db=30.0, off=(), level=0.5):
    """Команды: задержки и веса луча beam на передачу (без commit).

    Веса = level · распределение (максимум level); gains — готовые веса (перекрывают всё).
    """
    d = delay_reg(beam_delays(az_deg or 0.0, focus=focus))
    if gains is None:
        gains = level * element_weights(n_out, taper, sll_db, off=off)
    g = gain_reg(gains)
    cmds = []
    for o in range(n_out):
        idx = o * TX_BEAMS + beam
        cmds.append(encode_write(TX_DELAY + idx, d[o]))
        cmds.append(encode_write(TX_GAIN + idx, g[o]))
    return cmds


def rx_beam_commands(out, az_deg=None, focus=None, gains=None, n_in=N_MICS,
                     taper="uniform", sll_db=30.0, off=()):
    """Команды луча приёма out. Веса нормируются к единичному усилению в направлении луча."""
    d = delay_reg(beam_delays(az_deg or 0.0, focus=focus, positions=mic_positions(n_in)))
    if gains is None:
        w = element_weights(n_in, taper, sll_db, off=off)
        gains = w / np.sum(w)
    g = gain_reg(gains)
    cmds = []
    for i in range(n_in):
        idx = out * n_in + i
        cmds.append(encode_write(RX_DELAY + idx, d[i]))
        cmds.append(encode_write(RX_GAIN + idx, g[i]))
    return cmds


def gen_commands(beam, mode, freq=None, amp=0.5, chirp=None, burst=None, band=None, env_ms=5.0):
    """Команды настройки генератора луча beam.

    chirp=(f0, f1, dur_s); burst=(on_s, period_s); band=(f_lo, f_hi) — фильтр шума.
    """
    base = GEN_BASE[beam]
    w = lambda off, val: encode_write(base + off, val)  # noqa: E731
    cmds = []
    if mode == MODE_CHIRP:
        f0, f1, dur = chirp
        n = int(round(dur * FS))
        inc0 = phase_inc(f0)
        rate = int(round((phase_inc(f1) - inc0) / n))
        cmds += [w(GEN_INC_LO, inc0 & 0xFFFF), w(GEN_INC_HI, inc0 >> 16),
                 w(GEN_RATE_LO, rate & 0xFFFF), w(GEN_RATE_HI, (rate >> 16) & 0xFFFF),
                 w(GEN_CHIRP_LEN, n)]
    elif freq is not None:
        inc = phase_inc(freq)
        cmds += [w(GEN_INC_LO, inc & 0xFFFF), w(GEN_INC_HI, inc >> 16)]
    if band is not None:
        for off, v in zip((GEN_B0, GEN_B1, GEN_B2, GEN_A1, GEN_A2), biquad_bandpass(*band)):
            cmds.append(w(off, v))
        cmds.append(w(GEN_FILT, 1))
    else:
        cmds.append(w(GEN_FILT, 0))
    on, per = burst if burst is not None else (0, 0)
    cmds += [w(GEN_PERIOD, int(round(per * FS))), w(GEN_ON_LEN, int(round(on * FS)))]
    step = max(1, int((1 << 17) / max(1.0, env_ms * 1e-3 * FS)))
    cmds += [w(GEN_ENV_STEP, step), w(GEN_AMP, int(amp * ((1 << 17) - 1))), w(GEN_MODE, mode)]
    return cmds


# --- Эталонная модель ядра ----------------------------------------------------------
def _sat(x, bits):
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return np.clip(x, lo, hi)


def engine_model(x, delays, gains, out_shl, coef=None):
    """Целочисленная модель delay_sum_engine.v.

    x:      (NI, T) входные отсчёты (int, 18 бит);
    delays: (NO, NI) регистры задержки; gains: (NO, NI) регистры усиления.
    Возвращает (NO, T) выходы (24 бит), y[:, n] вычислен в кадре n.
    """
    coef = fd_coefficients_int() if coef is None else coef
    x = np.asarray(x, dtype=np.int64)
    ni, t = x.shape
    no = delays.shape[0]
    xp = np.concatenate([np.zeros((ni, DEPTH), dtype=np.int64), x], axis=1)
    out = np.zeros((no, t), dtype=np.int64)
    n = np.arange(t) + DEPTH
    for o in range(no):
        acc_o = np.zeros(t, dtype=np.int64)
        for i in range(ni):
            d_int, ph = int(delays[o, i]) >> PHASE_BITS, int(delays[o, i]) & (PHASES - 1)
            acc = np.zeros(t, dtype=np.int64)
            for k in range(TAPS):
                acc += xp[i, n - d_int + TAP_CENTER - k] * coef[ph, k]
            y = _sat(acc >> COEF_FRAC, W)
            acc_o += (y * int(gains[o, i])) >> COEF_FRAC
        out[o] = _sat(acc_o << out_shl, 24)
    return out
