"""Эталонные векторы для проверки C#-приложения (software/DpaaControl) бит в бит.

Всё считается функциями dpaa/hw.py и tools/dpaa_ctl.py — той же моделью, с которой
сверяется прошивка ПЛИС. Результат: software/DpaaControl/tests/Dpaa.Core.Tests/golden.json.

Запуск:  python scripts/make_csharp_golden.py
"""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import dpaa_ctl  # noqa: E402
from dpaa import hw  # noqa: E402
from dpaa.patterns import taper  # noqa: E402

OUT = ROOT / "software" / "DpaaControl" / "tests" / "Dpaa.Core.Tests" / "golden.json"


def hexs(frames):
    return [f.hex() for f in frames]


class Capture:
    """Подмена dpaa_ctl.Link: собирает кадры вместо отправки."""

    def __init__(self):
        self.ser = None
        self.frames = []

    def send(self, frames):
        self.frames += list(frames)


def ctl_args(**kw):
    base = dict(amp=0.25, taper="uniform", sll=30.0, weights=None, off=None, noise=False, chirp=False,
                tone=3000.0)
    base.update(kw)
    return argparse.Namespace(**base)


def run(cmd, **kw):
    link = Capture()
    cmd(link, ctl_args(**kw))
    return hexs(link.frames)


def main():
    g = {}
    g["protocol"] = [dict(addr=a, data=d, write=hw.encode_write(a, d).hex(), read=hw.encode_read(a).hex())
                     for a, d in [(0, 0), (2, 3), (0x1000, 0x1234), (0x1081, 0xFE0000), (0x209F, 0xFFFFFF),
                                  (0x7FFF, 0xABCDEF), (0x0010, 131071)]]
    g["phase_inc"] = [dict(f=f, inc=hw.phase_inc(f)) for f in [0, 1, 500, 1500, 2000, 3000, 4000, 4300,
                                                                  12345.678, 24000]]
    g["biquad"] = [dict(lo=lo, hi=hi, coef=hw.biquad_bandpass(lo, hi))
                   for lo, hi in [(1500, 4300), (1000, 3000), (2000, 5000), (300, 8000)]]
    g["gain_reg"] = [dict(x=x, reg=int(hw.gain_reg(x))) for x in [0, 1, -1, 0.5, 1 / 3, -0.123456, 1.99999,
                                                                    2.5, -3, 0.5 / 65536, 1.5 / 65536]]
    g["windows"] = [dict(kind=k, n=n, sll=s, w=list(taper(n, k, s)))
                    for k in ["uniform", "taylor", "chebyshev", "hann"] for n in [16, 15, 8]
                    for s in [20.0, 30.0, 40.0]]

    beams = []
    for az in [-90, -60, -35, -12.3, 0, 17, 30, 45, 60, 89.9]:
        beams.append(dict(az=az, focus=None, tx=[int(v) for v in hw.delay_reg(hw.beam_delays(az))],
                          rx=[int(v) for v in hw.delay_reg(hw.beam_delays(az, positions=hw.mic_positions()))]))
    for f in [(0, 1, 0), (0.3, 1, 0), (-0.2, 0.5, 0), (0, 0.3, 0), (1.5, 2.5, 0)]:
        beams.append(dict(az=0, focus=list(f), tx=[int(v) for v in hw.delay_reg(hw.beam_delays(0, focus=f))],
                          rx=[int(v) for v in hw.delay_reg(hw.beam_delays(0, focus=f,
                                                                         positions=hw.mic_positions()))]))
    g["delays"] = beams

    gen = []
    for beam, mode, kw in [(0, hw.MODE_SINE, dict(freq=3000, amp=0.25)),
                           (1, hw.MODE_SINE, dict(freq=2500, amp=0.5)),
                           (0, hw.MODE_NOISE, dict(amp=0.25, band=(1500, 4300))),
                           (1, hw.MODE_CHIRP, dict(amp=0.3, chirp=(2000, 4000, 0.05), burst=(0.05, 0.3))),
                           (0, hw.MODE_CHIRP, dict(amp=0.1, chirp=(4000, 1500, 0.1))),
                           (0, hw.MODE_OFF, dict()),
                           (1, hw.MODE_SINE, dict(freq=1234.5, amp=0.123, env_ms=20))]:
        gen.append(dict(beam=beam, mode=mode, freq=kw.get("freq"), amp=kw.get("amp", 0.5),
                        chirp=kw.get("chirp"), burst=kw.get("burst"), band=kw.get("band"),
                        env_ms=kw.get("env_ms", 5.0), frames=hexs(hw.gen_commands(beam, mode, **kw))))
    g["gen"] = gen

    sc = []

    def add(name, cmd, **kw):
        sc.append(dict(name=name, args={k: v for k, v in kw.items()}, frames=run(cmd, **kw)))

    add("beam", dpaa_ctl.cmd_beam, az=30.0, tone=3000.0)
    add("beam", dpaa_ctl.cmd_beam, az=-20.0, noise=True, amp=0.4)
    add("beam", dpaa_ctl.cmd_beam, az=10.0, chirp=True, amp=0.9)
    add("beam", dpaa_ctl.cmd_beam, az=20.0, taper="taylor", sll=35.0, tone=2500.0)
    add("beam", dpaa_ctl.cmd_beam, az=0.0, taper="chebyshev", sll=25.0, off="1,3,5,7,9,11,13,15", tone=4000.0)
    add("beam", dpaa_ctl.cmd_beam, az=0.0, weights="1,1,1,1,1,1,1,1,-1,-1,-1,-1,-1,-1,-1,-1")
    add("beam", dpaa_ctl.cmd_beam, az=-45.0, taper="hann", off="16")
    add("focus", dpaa_ctl.cmd_focus, x=0.3, y=1.0, tone=3000.0)
    add("focus", dpaa_ctl.cmd_focus, x=-0.5, y=0.6, noise=True, taper="taylor", sll=30.0)
    add("two", dpaa_ctl.cmd_two, az1=-35.0, az2=35.0, tone1=2500.0, tone2=3500.0)
    add("two", dpaa_ctl.cmd_two, az1=-10.0, az2=50.0, tone1=3000.0, tone2=2000.0, taper="hann", amp=0.3)
    add("listen", dpaa_ctl.cmd_listen, left=-30.0, right=30.0)
    add("listen", dpaa_ctl.cmd_listen, left=-60.0, right=15.0, taper="taylor", sll=30.0, off="2")
    add("listen", dpaa_ctl.cmd_listen, left=0.0, right=0.0, weights="1,2,3,4,5,6,7,8,8,7,6,5,4,3,2,1")
    g["scenarios"] = sc

    # поэлементный тест: начало и один шаг (без паузы — link.ser is None)
    link = Capture()
    with contextlib.redirect_stdout(io.StringIO()):     # cmd_elements печатает номера элементов
        dpaa_ctl.cmd_elements(link, argparse.Namespace(tone=2000.0, amp=0.25, dwell=0.0))
    g["elements"] = hexs(link.frames)
    # шаг сканирования (dpaa_ctl.cmd_sweep: подготовка и одно обновление луча)
    a = ctl_args(tone=3000.0, lo=-60.0, hi=60.0, period=6.0)
    link = Capture()
    link.send(dpaa_ctl.source_cmds(0, a, a.amp) + hw.gen_commands(1, hw.MODE_OFF)
              + hw.tx_beam_commands(1, gains=np.zeros(hw.N_ELEM)) + [hw.encode_write(hw.REG_CTRL, 3)])
    g["sweep_setup"] = hexs(link.frames)
    g["sweep_step"] = [dict(az=az, frames=hexs(dpaa_ctl.tx_beam(0, a, az_deg=az) + dpaa_ctl.commit()))
                       for az in [-60.0, -12.5, 0.0, 33.3]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(g, ensure_ascii=False, indent=1))
    print("saved", OUT, f"({OUT.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
