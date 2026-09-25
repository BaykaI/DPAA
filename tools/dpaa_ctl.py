"""Управление акустической ЦАФАР с ноутбука (USB-UART ULX3S, 1 Мбод).

Примеры:
  python tools/dpaa_ctl.py --port /dev/ttyUSB0 id
  python tools/dpaa_ctl.py beam --az 30 --tone 3000          # луч на 30°, тон 3 кГц
  python tools/dpaa_ctl.py beam --az -20 --noise              # полосовой шум 1.5–4.3 кГц
  python tools/dpaa_ctl.py sweep --from -60 --to 60 --period 6
  python tools/dpaa_ctl.py two-beams --az1 -35 --az2 35       # два луча, два сигнала
  python tools/dpaa_ctl.py focus --x 0.3 --y 1.0              # фокус в точку
  python tools/dpaa_ctl.py elements                           # по очереди «пищит» каждый элемент
  python tools/dpaa_ctl.py listen --left -30 --right 30       # лучи приёма в наушники
  python tools/dpaa_ctl.py peaks                              # уровни микрофонов
  python tools/dpaa_ctl.py mute

Без --port команды печатаются в hex (сухой прогон, железо не нужно).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dpaa import hw  # noqa: E402

MAX_AMP = 0.5  # ограничение громкости (безопасность слуха), доля полной шкалы


class Link:
    def __init__(self, port=None, baud=1_000_000):
        self.ser = None
        if port:
            try:
                import serial
            except ImportError:
                sys.exit("нужен pyserial:  pip install pyserial")
            self.ser = serial.Serial(port, baud, timeout=0.2)

    def send(self, frames):
        data = b"".join(frames)
        if self.ser is None:
            for i in range(0, len(data), 7):
                print(data[i:i + 7].hex(" "))
        else:
            self.ser.write(data)
            self.ser.flush()

    def read(self, addr):
        if self.ser is None:
            print(hw.encode_read(addr).hex(" "), "(чтение)")
            return None
        self.ser.reset_input_buffer()
        self.ser.write(hw.encode_read(addr))
        rsp = self.ser.read(7)
        a, d = hw.decode_response(rsp)
        if a != addr:
            raise IOError(f"ответ на адрес {a:#x}, ожидался {addr:#x}")
        return d


def commit(tx=True, rx=False):
    return [hw.encode_write(hw.REG_COMMIT, (1 if tx else 0) | (2 if rx else 0))]


def source_cmds(beam, args, amp):
    amp = min(amp, MAX_AMP)
    if getattr(args, "noise", False):
        return hw.gen_commands(beam, hw.MODE_NOISE, amp=amp, band=(1500, 4300))
    if getattr(args, "chirp", False):
        return hw.gen_commands(beam, hw.MODE_CHIRP, amp=amp, chirp=(2000, 4000, 0.05), burst=(0.05, 0.3))
    return hw.gen_commands(beam, hw.MODE_SINE, freq=args.tone, amp=amp)


def cmd_beam(link, args):
    link.send(source_cmds(0, args, args.amp) + hw.gen_commands(1, hw.MODE_OFF)
              + hw.tx_beam_commands(0, az_deg=args.az)
              + hw.tx_beam_commands(1, gains=np.zeros(hw.N_ELEM))
              + commit() + [hw.encode_write(hw.REG_CTRL, 3)])


def cmd_focus(link, args):
    link.send(source_cmds(0, args, args.amp)
              + hw.tx_beam_commands(0, focus=(args.x, args.y, 0.0))
              + hw.tx_beam_commands(1, gains=np.zeros(hw.N_ELEM))
              + commit() + [hw.encode_write(hw.REG_CTRL, 3)])


def cmd_two(link, args):
    a = argparse.Namespace(tone=args.tone1, noise=False, chirp=False)
    b = argparse.Namespace(tone=args.tone2, noise=False, chirp=True)
    link.send(source_cmds(0, a, args.amp) + source_cmds(1, b, args.amp)
              + hw.tx_beam_commands(0, az_deg=args.az1)
              + hw.tx_beam_commands(1, az_deg=args.az2)
              + commit() + [hw.encode_write(hw.REG_CTRL, 3)])


def cmd_sweep(link, args):
    link.send(source_cmds(0, args, args.amp) + hw.gen_commands(1, hw.MODE_OFF)
              + hw.tx_beam_commands(1, gains=np.zeros(hw.N_ELEM))
              + [hw.encode_write(hw.REG_CTRL, 3)])
    rate = 50.0  # обновлений луча в секунду
    t0 = time.time()
    try:
        while link.ser is not None or time.time() - t0 < 1 / rate:
            t = time.time() - t0
            ph = (t / args.period) % 1.0
            az = args.lo + (args.hi - args.lo) * (1 - abs(2 * ph - 1))
            link.send(hw.tx_beam_commands(0, az_deg=az) + commit())
            time.sleep(1 / rate)
    except KeyboardInterrupt:
        pass


def cmd_elements(link, args):
    link.send(hw.gen_commands(0, hw.MODE_SINE, freq=args.tone, amp=min(args.amp, MAX_AMP))
              + hw.gen_commands(1, hw.MODE_OFF) + [hw.encode_write(hw.REG_CTRL, 1)])
    for e in range(hw.N_ELEM):
        g = np.zeros(hw.N_ELEM)
        g[e] = 1.0
        print(f"элемент {e + 1}")
        link.send(hw.tx_beam_commands(0, gains=g) + commit())
        if link.ser is not None:
            time.sleep(args.dwell)
    link.send([hw.encode_write(hw.REG_CTRL, 0)])


def cmd_listen(link, args):
    link.send(hw.rx_beam_commands(0, az_deg=args.left) + hw.rx_beam_commands(1, az_deg=args.right)
              + commit(tx=False, rx=True) + [hw.encode_write(hw.REG_CTRL, 2)])


def cmd_peaks(link, args):
    for i in range(hw.N_MICS + 1):
        v = link.read(hw.REG_PEAK + i)
        if v is not None:
            db = 20 * np.log10(max(v, 1) / 2**23)
            name = f"мик {i + 1:2d}" if i < hw.N_MICS else "калибр."
            print(f"{name}: {v:8d}  ({db:6.1f} дБ ПШ)  " + "#" * max(0, int((db + 90) / 3)))


def cmd_id(link, args):
    v = link.read(hw.REG_ID)
    if v is not None:
        print(f"ID = {v:#08x}", "OK" if v == hw.ID_VALUE else "НЕОЖИДАННО")
        print("кадров:", link.read(hw.REG_FRAMES))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="последовательный порт ULX3S (например, /dev/ttyUSB0, COM5)")
    ap.add_argument("--amp", type=float, default=0.25, help=f"громкость 0..{MAX_AMP}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("id")
    sub.add_parser("peaks")
    sub.add_parser("mute")
    p = sub.add_parser("beam")
    p.add_argument("--az", type=float, default=0.0)
    p.add_argument("--tone", type=float, default=3000.0)
    p.add_argument("--noise", action="store_true")
    p.add_argument("--chirp", action="store_true")
    p = sub.add_parser("focus")
    p.add_argument("--x", type=float, default=0.0)
    p.add_argument("--y", type=float, default=1.0)
    p.add_argument("--tone", type=float, default=3000.0)
    p.add_argument("--noise", action="store_true")
    p = sub.add_parser("sweep")
    p.add_argument("--from", dest="lo", type=float, default=-60.0)
    p.add_argument("--to", dest="hi", type=float, default=60.0)
    p.add_argument("--period", type=float, default=6.0)
    p.add_argument("--tone", type=float, default=3000.0)
    p.add_argument("--noise", action="store_true")
    p = sub.add_parser("two-beams")
    p.add_argument("--az1", type=float, default=-35.0)
    p.add_argument("--az2", type=float, default=35.0)
    p.add_argument("--tone1", type=float, default=2500.0)
    p.add_argument("--tone2", type=float, default=3500.0)
    p = sub.add_parser("elements")
    p.add_argument("--tone", type=float, default=2000.0)
    p.add_argument("--dwell", type=float, default=0.7)
    p = sub.add_parser("listen")
    p.add_argument("--left", type=float, default=-30.0)
    p.add_argument("--right", type=float, default=30.0)
    args = ap.parse_args(argv)

    link = Link(args.port)
    {"id": cmd_id, "peaks": cmd_peaks, "beam": cmd_beam, "focus": cmd_focus, "sweep": cmd_sweep,
     "two-beams": cmd_two, "elements": cmd_elements, "listen": cmd_listen,
     "mute": lambda lk, a: lk.send([hw.encode_write(hw.REG_CTRL, 0)])}[args.cmd](link, args)


if __name__ == "__main__":
    main()
