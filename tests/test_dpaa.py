import numpy as np
import pytest

from dpaa import C_SOUND, direction, steering_delays, ula
from dpaa.beamforming import delay_and_sum, spatial_spectrum, stft_beamform
from dpaa.patterns import array_factor, db, grating_lobe_free_freq, hpbw_deg, wideband_pattern
from dpaa.propagation import radiate, simulate_free_field
from dpaa.signals import (band_power_db, bandpass_noise, fractional_delay,
                          fractional_delay_fir, phase_shift, time_varying_delay)
from dpaa.transmit import tx_signals

FS = 48_000
POS = ula(8, 0.04)
ANG = np.linspace(-90, 90, 3601)


@pytest.mark.parametrize("steer", [-45, 0, 20, 60])
def test_beam_points_where_steered(steer):
    af = np.abs(array_factor(POS, 3000, ANG, steer_az=steer))
    assert ANG[np.argmax(af)] == pytest.approx(steer, abs=0.1)
    assert af.max() == pytest.approx(1.0)


def test_beamwidth_matches_theory():
    f = 4000
    bw = hpbw_deg(ANG, array_factor(POS, f, ANG))
    theory = np.rad2deg(0.886 * (C_SOUND / f) / (8 * 0.04))
    assert bw == pytest.approx(theory, rel=0.05)


def test_grating_lobe_appears_above_limit():
    f_lim = grating_lobe_free_freq(0.04, 30)
    below = db(array_factor(POS, 0.75 * f_lim, ANG, steer_az=30))
    above = db(array_factor(POS, 1.3 * f_lim, ANG, steer_az=30))
    far = np.abs(ANG - 30) > 40
    assert below[far].max() < -6
    assert above[far].max() > -1  # второй полноценный луч


def test_phase_steering_squints_but_ttd_does_not():
    freqs = np.array([2000.0, 4000.0])
    ttd = wideband_pattern(POS, freqs, ANG, 30, mode="ttd")
    ph = wideband_pattern(POS, freqs, ANG, 30, mode="phase", f0=2000)
    assert ANG[np.argmax(ttd[1])] == pytest.approx(30, abs=0.2)
    assert ANG[np.argmax(ph[0])] == pytest.approx(30, abs=0.2)
    expected = np.rad2deg(np.arcsin(0.5 * 2000 / 4000))  # sinθ(f) = f0/f · sinθ0
    assert ANG[np.argmax(ph[1])] == pytest.approx(expected, abs=0.3)


def test_fractional_delay_is_exact_for_bandlimited_signal():
    x = bandpass_noise(0.2, FS, 500, 8000, rng=0)
    d = 7.3 / FS
    y = fractional_delay(x, d, FS)
    t = np.arange(x.size) / FS
    ref = fractional_delay(x, 0.0, FS)
    # сравнение с аналитически сдвинутой синусоидой
    s = np.sin(2 * np.pi * 1000 * t)
    s_d = fractional_delay(s, d, FS)
    mid = slice(2000, 8000)
    assert np.allclose(s_d[mid], np.sin(2 * np.pi * 1000 * (t[mid] - d)), atol=1e-3)
    assert np.allclose(ref, x, atol=1e-9)
    assert y.shape == x.shape


def test_fir_fractional_delay():
    taps, k = fractional_delay_fir(3.25, ntaps=33)
    assert k == 3
    t = np.arange(4000)
    s = np.sin(2 * np.pi * 0.05 * t)
    y = np.convolve(s, taps)[: t.size]
    total = 16 + 0.25
    mid = slice(200, 3800)
    assert np.allclose(y[mid], np.sin(2 * np.pi * 0.05 * (t[mid] - total)), atol=1e-3)


def test_phase_shift_equals_delay_at_design_frequency():
    t = np.arange(4800) / FS
    f0 = 1000
    s = np.sin(2 * np.pi * f0 * t)
    y = phase_shift(s, np.pi / 2)
    assert np.allclose(y, np.sin(2 * np.pi * f0 * t - np.pi / 2), atol=1e-6)


def test_time_varying_delay_constant_matches_fractional():
    x = bandpass_noise(0.1, FS, 300, 6000, rng=1)
    tau = np.full((2, x.size), 5.5 / FS)
    y = time_varying_delay(x, tau, FS)
    ref = fractional_delay(x, 5.5 / FS, FS)
    mid = slice(200, x.size - 200)
    err = np.sqrt(np.mean((y[0, mid] - ref[mid]) ** 2))
    assert err < 0.02


def test_steering_delays_nonnegative_and_reciprocal():
    tau = steering_delays(POS, 40)
    assert tau.min() == 0
    # для луча вправо (+x) дальний правый элемент излучает последним
    assert np.argmax(tau) == len(POS) - 1


def test_tx_beam_is_louder_in_steered_direction():
    sig = bandpass_noise(0.3, FS, 2000, 4000, rng=2)
    tx = tx_signals(sig, POS, FS, az_deg=30)
    listeners = {a: 10 * np.array([np.sin(np.deg2rad(a)), np.cos(np.deg2rad(a)), 0]) for a in (-30, 0, 30)}
    p = {a: band_power_db(radiate(tx, POS, pos, FS, tx.shape[1] + 2000), FS, 2000, 4000)
         for a, pos in listeners.items()}
    assert p[30] - p[-30] > 10
    assert p[30] - p[0] > 6


def _two_source_scene():
    target = bandpass_noise(1.0, FS, 1500, 4000, rng=3)
    interf = bandpass_noise(1.0, FS, 1500, 4000, rng=4)
    r = 6.0
    pos_t = r * np.array([np.sin(np.deg2rad(-35)), np.cos(np.deg2rad(-35)), 0])
    pos_i = r * np.array([np.sin(np.deg2rad(25)), np.cos(np.deg2rad(25)), 0])
    xt = simulate_free_field([(target, pos_t)], POS, FS)
    xi = simulate_free_field([(interf, pos_i)], POS, FS)
    return xt, xi


def test_das_and_mvdr_improve_sir():
    xt, xi = _two_source_scene()
    band = (1500, 4000)
    sir_in = band_power_db(xt[0], FS, *band) - band_power_db(xi[0], FS, *band)
    das_t = delay_and_sum(xt, POS, FS, -35)
    das_i = delay_and_sum(xi, POS, FS, -35)
    sir_das = band_power_db(das_t, FS, *band) - band_power_db(das_i, FS, *band)
    # MVDR обучается на участке, где звучит только помеха (как «обучающая выборка» в РЛС),
    # затем одни и те же веса применяются к цели и к помехе по отдельности.
    mv_t = stft_beamform(xt, POS, FS, -35, method="mvdr", x_train=xi)
    mv_i = stft_beamform(xi, POS, FS, -35, method="mvdr", x_train=xi)
    sir_mvdr = band_power_db(mv_t, FS, *band) - band_power_db(mv_i, FS, *band)
    assert sir_das - sir_in > 8
    assert sir_mvdr - sir_das > 15


def test_stft_das_matches_time_domain_das():
    xt, _ = _two_source_scene()
    y1 = delay_and_sum(xt, POS, FS, -35)
    # временной DAS даёт выход с задержкой относительно центра решётки — компенсируем
    shift = -np.min(POS @ direction(-35) / C_SOUND)
    y2 = fractional_delay(stft_beamform(xt, POS, FS, -35, method="das"), shift, FS)
    mid = slice(4000, xt.shape[1] - 4000)
    rel = np.sqrt(np.mean((y1[mid] - y2[mid]) ** 2) / np.mean(y1[mid] ** 2))
    assert rel < 0.05


def test_spatial_spectrum_finds_both_sources():
    xt, xi = _two_source_scene()
    grid = np.linspace(-90, 90, 361)
    for method in ("das", "capon"):
        p = spatial_spectrum(xt + xi, POS, FS, grid, 1500, 4000, method=method)
        peaks = [i for i in range(1, len(p) - 1) if p[i] > p[i - 1] and p[i] >= p[i + 1] and p[i] > -6]
        found = sorted(grid[peaks])
        assert len(found) == 2
        assert found[0] == pytest.approx(-35, abs=2)
        assert found[1] == pytest.approx(25, abs=2)
