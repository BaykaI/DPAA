"""RTL-тесты ПЛИС (нужен Icarus Verilog; иначе пропускаются)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gateware"))
import sim  # noqa: E402

from dpaa import hw  # noqa: E402
from dpaa.signals import bandpass_noise, fractional_delay  # noqa: E402

pytestmark = pytest.mark.skipif(not sim.have_iverilog(), reason="iverilog not installed")


@pytest.mark.parametrize("ni_log2,no_log2", [(1, 4), (4, 1)])
def test_engine_bit_exact(tmp_path, ni_log2, no_log2):
    rng = np.random.default_rng(ni_log2)
    ni, no, t = 1 << ni_log2, 1 << no_log2, 320
    x = np.stack([bandpass_noise(t / hw.FS, hw.FS, 300, 9000, rng=rng) for _ in range(ni)])
    x = np.clip(np.round(x / np.abs(x).max() * 0.7 * 2**17), -2**17, 2**17 - 1).astype(np.int64)
    delays = rng.integers(hw.TAP_CENTER * hw.PHASES, 200 * hw.PHASES, size=(no, ni))
    gains = rng.integers(-2**17, 2**17, size=(no, ni)) // (2 if ni > 2 else 1)
    cfg = []
    for o in range(no):
        for i in range(ni):
            idx = o * ni + i
            cfg.append((0 << 31) | (idx << 24) | int(delays[o, i]))
            cfg.append((1 << 31) | (idx << 24) | (int(gains[o, i]) & 0xFFFFFF))
    sim.write_mem(tmp_path / "cfg.hex", cfg, 32)
    sim.write_mem(tmp_path / "in.hex", x.T, 18)
    vvp = sim.build("tb_engine", ["delay_sum_engine.v"], tmp_path,
                    {"NI_LOG2": ni_log2, "NO_LOG2": no_log2, "OUT_SHL": 6})
    sim.run(vvp, {"CFG": tmp_path / "cfg.hex", "IN": tmp_path / "in.hex",
                  "OUT": tmp_path / "out.txt", "NCFG": len(cfg), "NFR": t})
    got, _ = sim.read_rows(tmp_path / "out.txt")
    ref = hw.engine_model(x, delays, gains, out_shl=6).T
    assert got.shape == ref.shape
    assert np.array_equal(got, ref)


def test_engine_bank_switching(tmp_path):
    """Частичная смена таблиц, запись во время копирования банков и повторный commit."""
    rng = np.random.default_rng(5)
    ni, no, t, sw1, sw2 = 2, 16, 240, 80, 160
    x = np.stack([bandpass_noise(t / hw.FS, hw.FS, 300, 9000, rng=rng) for _ in range(ni)])
    x = np.round(x / np.abs(x).max() * 0.5 * 2**17).astype(np.int64)
    d1 = rng.integers(3 * 32, 150 * 32, size=(no, ni))
    g1 = rng.integers(-2**16, 2**16, size=(no, ni))

    def word(sel, idx, val):
        return (sel << 31) | (idx << 24) | (int(val) & 0xFFFFFF)

    cfg1 = [word(0, o * ni + i, d1[o, i]) for o in range(no) for i in range(ni)]
    cfg1 += [word(1, o * ni + i, g1[o, i]) for o in range(no) for i in range(ni)]
    d2, g2 = d1.copy(), g1.copy()
    cfg2 = []
    for o in (0, 5, 11):                        # меняем только часть таблицы
        d2[o, 1] = 200 * 32 + 7
        g2[o, 0] = -30000
        cfg2 += [word(0, o * ni + 1, d2[o, 1]), word(1, o * ni + 0, g2[o, 0])]
    d3, g3 = d2.copy(), g2.copy()
    g3[7, 1] = 50000                              # запись во время копирования банков
    extra = word(1, 7 * ni + 1, g3[7, 1])

    sim.write_mem(tmp_path / "cfg.hex", cfg1, 32)
    sim.write_mem(tmp_path / "cfg2.hex", cfg2, 32)
    sim.write_mem(tmp_path / "in.hex", x.T, 18)
    vvp = sim.build("tb_engine", ["delay_sum_engine.v"], tmp_path, {"NI_LOG2": 1, "NO_LOG2": 4, "OUT_SHL": 6})
    sim.run(vvp, {"CFG": tmp_path / "cfg.hex", "IN": tmp_path / "in.hex", "OUT": tmp_path / "out.txt",
                  "NCFG": len(cfg1), "NFR": t, "CFG2": tmp_path / "cfg2.hex", "NCFG2": len(cfg2),
                  "SW1": sw1, "SW2": sw2, "EXTRA": f"{extra:08x}"})
    got, _ = sim.read_rows(tmp_path / "out.txt")
    refs = [hw.engine_model(x, d, g, out_shl=6).T for d, g in ((d1, g1), (d2, g2), (d3, g3))]
    assert np.array_equal(got[:sw1], refs[0][:sw1])
    assert np.array_equal(got[sw1:sw2], refs[1][sw1:sw2])      # EXTRA ещё не активна
    assert np.array_equal(got[sw2:], refs[2][sw2:])            # и не потерялась


def test_fd_coefficients_accuracy():
    """Модель ядра с единичным весом ≈ идеальная дробная задержка (ошибка < -60 дБ)."""
    t = 2000
    x = bandpass_noise(t / hw.FS, hw.FS, 300, 5000, rng=7)
    xi = np.round(x / np.abs(x).max() * 0.5 * 2**17).astype(np.int64)
    d = 17.40625  # 17 + 13/32
    y = hw.engine_model(xi[None], np.array([[hw.delay_reg(d)]]), np.array([[hw.UNITY]]), out_shl=0)[0]
    ideal = fractional_delay(xi.astype(float), d / hw.FS, hw.FS)
    mid = slice(300, t - 300)
    err = 10 * np.log10(np.mean((y[mid] - ideal[mid]) ** 2) / np.mean(ideal[mid] ** 2))
    assert err < -60


@pytest.fixture(scope="module")
def core_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("core")
    f_tone, tx_az, src_az = 3000.0, 30.0, -20.0
    cmds = []
    cmds += hw.gen_commands(0, hw.MODE_SINE, freq=f_tone, amp=0.5, env_ms=2)
    cmds += hw.gen_commands(1, hw.MODE_OFF)
    cmds += hw.tx_beam_commands(0, az_deg=tx_az)
    cmds += hw.tx_beam_commands(1, az_deg=0, gains=np.zeros(hw.N_ELEM))
    cmds += hw.rx_beam_commands(0, az_deg=src_az)
    cmds += hw.rx_beam_commands(1, az_deg=40)
    cmds += [hw.encode_write(hw.REG_COMMIT, 3), hw.encode_write(hw.REG_CTRL, 3),
             hw.encode_read(hw.REG_ID), hw.encode_read(hw.REG_PEAK + 0)]
    stream = b"".join(cmds)

    # плоская волна с направления src_az на 16 микрофонах, 17-й — тихий синус
    n_fr = 900
    pos = hw.element_positions()
    s = bandpass_noise(n_fr / hw.FS, hw.FS, 1500, 4300, rng=11)
    s = s / np.abs(s).max() * 0.05 * 2**23
    proj = pos @ hw.direction(src_az) / hw.C_SOUND
    mic = fractional_delay(np.tile(s, (16, 1)), proj.max() - proj, hw.FS)
    cal = 1000 * np.sin(2 * np.pi * 1000 * np.arange(n_fr) / hw.FS)
    mic = np.round(np.vstack([mic, cal])).astype(np.int64)
    sim.write_mem(tmp / "cmd.hex", list(stream), 8)
    sim.write_mem(tmp / "mic.hex", mic.T, 24)

    vvp = sim.build("tb_core", sim.CORE_SOURCES, tmp)
    sim.run(vvp, {"CMD": tmp / "cmd.hex", "MIC": tmp / "mic.hex", "TXO": tmp / "tx.txt",
                  "MONO": tmp / "mon.txt", "RSPO": tmp / "rsp.txt", "NCMD": len(stream), "NFR": 700},
            timeout=1800)
    return dict(tmp=tmp, f=f_tone, tx_az=tx_az, src_az=src_az, mic=mic)


def test_core_uart_readback(core_run):
    rsp = [int(v, 16) for v in (core_run["tmp"] / "rsp.txt").read_text().split()]
    assert len(rsp) == 14
    addr, data = hw.decode_response(bytes(rsp[:7]))
    assert (addr, data) == (hw.REG_ID, hw.ID_VALUE)
    addr, data = hw.decode_response(bytes(rsp[7:]))
    assert addr == hw.REG_PEAK and data > 0


def test_core_tx_beam_phases(core_run):
    text = (core_run["tmp"] / "tx.txt").read_text()
    assert "L!=R" not in text
    tx, _ = sim.read_rows(core_run["tmp"] / "tx.txt")
    y = tx[-400:].T.astype(float)                        # (16, 400)
    f_q = hw.phase_inc(core_run["f"]) / 2**32 * hw.FS    # точная частота DDS
    win = np.hanning(y.shape[1])
    e = win * np.exp(-2j * np.pi * f_q * np.arange(y.shape[1]) / hw.FS)
    a = y @ e
    amp = np.abs(a)
    assert np.all(np.abs(amp / amp.mean() - 1) < 0.002)
    assert amp.mean() / (win.sum() / 2) == pytest.approx(0.25 * 2**23, rel=0.01)
    d = hw.delay_reg(hw.beam_delays(core_run["tx_az"])) / hw.PHASES
    expected = -2 * np.pi * f_q * (d - d[0]) / hw.FS
    measured = np.angle(a / a[0])
    err = np.angle(np.exp(1j * (measured - expected)))
    assert np.max(np.abs(np.rad2deg(err))) < 0.5


def test_core_rx_bit_exact_and_directive(core_run):
    mon, _ = sim.read_rows(core_run["tmp"] / "mon.txt")
    mic18 = core_run["mic"][:16] >> 6
    d0 = hw.delay_reg(hw.beam_delays(core_run["src_az"]))
    d1 = hw.delay_reg(hw.beam_delays(40))
    delays = np.stack([d0, d1])
    gains = np.full((2, 16), int(hw.gain_reg(1 / 16)))
    ref = hw.engine_model(mic18, delays, gains, out_shl=6).T  # (T, 2)
    win = slice(len(mon) - 200, len(mon))
    match = [lag for lag in range(0, 8)
             if np.array_equal(mon[win], ref[win.start - lag: win.stop - lag])]
    assert match, "RX output does not match the model at any lag"
    p = np.mean(mon[win].astype(float) ** 2, axis=0)
    assert 10 * np.log10(p[0] / p[1]) > 10


def _run_gen(tmp_path, cmds, n):
    """Прогнать генератор с командами gen_commands(0, ...) и вернуть n отсчётов."""
    words = []
    for c in cmds:
        addr, data = (c[1] << 8 | c[2]) - hw.GEN_BASE[0], (c[3] << 16) | (c[4] << 8) | c[5]
        words.append((addr << 24) | data)
    sim.write_mem(tmp_path / "cfg.hex", words, 28)
    vvp = sim.build("tb_sig_gen", ["sig_gen.v"], tmp_path)
    sim.run(vvp, {"CFG": tmp_path / "cfg.hex", "OUT": tmp_path / "out.txt",
                  "NCFG": len(words), "NFR": n})
    return sim.to_signed([int(v, 16) for v in (tmp_path / "out.txt").read_text().split()], 18)


def test_sig_gen_band_noise(tmp_path):
    y = _run_gen(tmp_path, hw.gen_commands(0, hw.MODE_NOISE, amp=0.5, band=(1500, 4300), env_ms=1), 8192)
    y = y[1024:].astype(float)
    spec = np.abs(np.fft.rfft(y * np.hanning(y.size))) ** 2
    f = np.fft.rfftfreq(y.size, 1 / hw.FS)
    inband = spec[(f > 1500) & (f < 4300)].sum()
    low = spec[f < 300].sum()
    high = spec[f > 15000].sum()
    assert 10 * np.log10(inband / low) > 15
    assert 10 * np.log10(inband / high) > 15
    assert 0.01 * 2**17 < y.std() < 0.5 * 2**17


def test_sig_gen_chirp_and_burst(tmp_path):
    dur, per = 0.02, 0.05
    y = _run_gen(tmp_path, hw.gen_commands(0, hw.MODE_CHIRP, amp=0.5, chirp=(2000, 4000, dur),
                                           burst=(dur, per), env_ms=0.2), 6000)
    y = y.astype(float)
    n_per, n_on = int(round(per * hw.FS)), int(round(dur * hw.FS))
    seg = y[2 * n_per: 3 * n_per]
    # пачка: энергия сосредоточена в первых n_on отсчётах периода
    assert np.sum(seg[:n_on] ** 2) > 100 * np.sum(seg[n_on + 50:] ** 2)
    # мгновенная частота растёт от ~2 до ~4 кГц
    from scipy.signal import hilbert
    ph = np.unwrap(np.angle(hilbert(seg[:n_on])))
    fi = np.diff(ph) / (2 * np.pi) * hw.FS
    assert np.median(fi[30:120]) == pytest.approx(2200, abs=250)
    assert np.median(fi[-120:-30]) == pytest.approx(3800, abs=250)
