"""Проверки аппаратной модели: протокол, таблицы лучей, амплитудное распределение."""
import numpy as np
import pytest

from dpaa import direction, hw, steering_vector
from dpaa.patterns import array_factor, db

ANG = np.linspace(-90, 90, 3601)


def decode_writes(frames):
    """Кадры записи -> словарь {адрес: данные} (для проверки таблиц)."""
    regs = {}
    for f in frames:
        assert f[0] == hw.SYNC_CMD
        chk = 0x5A
        for b in f[1:6]:
            chk ^= b
        assert chk == f[6]
        regs[(f[1] << 8) | f[2]] = (f[3] << 16) | (f[4] << 8) | f[5]
    return regs


def signed(v, bits=18):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >= 1 << (bits - 1) else v


def sidelobe_level(pattern_db):
    """Максимум вне главного лепестка (границы — первые минимумы по обе стороны)."""
    i0 = int(np.argmax(pattern_db))
    lo = i0
    while lo > 0 and pattern_db[lo - 1] <= pattern_db[lo]:
        lo -= 1
    hi = i0
    while hi < len(pattern_db) - 1 and pattern_db[hi + 1] <= pattern_db[hi]:
        hi += 1
    return max(pattern_db[:lo].max(initial=-200), pattern_db[hi + 1:].max(initial=-200))


def tx_gains(regs, beam=0):
    return np.array([signed(regs[hw.TX_GAIN + o * hw.TX_BEAMS + beam]) for o in range(hw.N_ELEM)])


def test_read_frame_roundtrip():
    f = bytearray(hw.encode_read(0x0105))
    f[0] = hw.SYNC_RSP  # ответ имеет тот же формат
    f[3:6] = b"\x12\x34\x56"
    chk = 0x5A
    for b in f[1:6]:
        chk ^= b
    f[6] = chk
    assert hw.decode_response(bytes(f)) == (0x0105, 0x123456)


@pytest.mark.parametrize("kind,sll", [("taylor", 35), ("chebyshev", 30)])
def test_tx_taper_lowers_sidelobes(kind, sll):
    regs = decode_writes(hw.tx_beam_commands(0, az_deg=20, taper=kind, sll_db=sll))
    g = tx_gains(regs)
    assert g.max() == hw.gain_reg(0.5)
    assert np.allclose(g, g[::-1], atol=1)                 # симметрия
    pos = hw.element_positions()
    af = db(array_factor(pos, 3500, ANG, steer_az=20, weights=g / hw.UNITY))
    uni = db(array_factor(pos, 3500, ANG, steer_az=20))
    assert sidelobe_level(af) < -sll + 1.5
    assert sidelobe_level(uni) > -14                        # равномерное: ≈ −13 дБ


def test_elements_off_and_custom_weights():
    regs = decode_writes(hw.tx_beam_commands(0, off=[0, 5]))
    g = tx_gains(regs)
    assert g[0] == 0 and g[5] == 0 and np.all(g[[1, 2, 3, 4, 6]] == hw.gain_reg(0.5))
    w = np.r_[np.ones(8), -np.ones(8)]
    g = tx_gains(decode_writes(hw.tx_beam_commands(0, gains=0.5 * w)))
    a = steering_vector(hw.element_positions(), 3000, direction(ANG))
    af = np.abs((g / hw.UNITY) @ a)
    assert af[np.argmin(np.abs(ANG))] < 1e-3 * af.max()     # разностная ДН: ноль по нормали


def test_rx_weights_unity_gain_towards_beam():
    regs = decode_writes(hw.rx_beam_commands(0, az_deg=-10, taper="taylor", sll_db=30))
    g = np.array([signed(regs[hw.RX_GAIN + i]) for i in range(hw.N_MICS)])
    assert g.sum() / hw.UNITY == pytest.approx(1.0, abs=1e-3)


def test_element_weights_validation():
    with pytest.raises(ValueError):
        hw.element_weights(16, weights=[1, 2, 3])
    with pytest.raises(ValueError):
        hw.element_weights(4, off=[0, 1, 2, 3])
