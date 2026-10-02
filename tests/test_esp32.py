"""Прошивка ESP32 (firmware/esp32): ядро и контроллер, собранные на компьютере.

* кадры, задержки, окна, генераторы и сценарии сверяются с dpaa/hw.py и tools/dpaa_ctl.py
  бит в бит — по эталонам golden.json (общие с C#-пультом) и по случайным конфигурациям;
* контроллер веб-API проверяется в режиме «ESP32 + симулятор ПЛИС»: запуск, живое
  обновление, сканирование, поэлементный тест, автопилот, тишина, ограничение громкости.

Нужен g++ (C++17); без него тесты пропускаются.
"""
import argparse
import contextlib
import io
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware" / "esp32"
GOLDEN = ROOT / "software" / "DpaaControl" / "tests" / "Dpaa.Core.Tests" / "golden.json"
sys.path.insert(0, str(ROOT / "tools"))
import dpaa_ctl  # noqa: E402
from dpaa import hw  # noqa: E402
from dpaa.patterns import taper as window  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="нужен g++")


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    exe = tmp_path_factory.mktemp("esp32") / "dpaa_host"
    src = sorted(str(p) for p in (FW / "lib" / "dpaa" / "src").glob("*.cpp"))
    subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{FW / 'lib' / 'dpaa' / 'src'}",
                    str(FW / "test" / "host" / "dpaa_host.cpp"), *src, "-o", str(exe)], check=True)
    return exe


def vec(host, lines):
    """Пакетный режим: одна строка запроса -> одна строка ответа."""
    r = subprocess.run([str(host), "vec"], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    return r.stdout.splitlines()


def q(**kw):
    return "&".join(f"{k}={v}" for k, v in kw.items() if v is not None)


# ------------------------------------------------------------------ эталоны golden.json
@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text())


def test_protocol_phase_gain_biquad(host, golden):
    lines, exp = [], []
    for c in golden["protocol"]:
        lines.append(q(t="protocol", addr=c["addr"], data=c["data"]))
        exp.append(f"{c['write']} {c['read']}")
    for c in golden["phase_inc"]:
        lines.append(q(t="phase", f=repr(c["f"])))
        exp.append(str(c["inc"]))
    for c in golden["gain_reg"]:
        lines.append(q(t="gain", x=repr(c["x"])))
        exp.append(str(c["reg"]))
    for c in golden["biquad"]:
        lines.append(q(t="biquad", lo=c["lo"], hi=c["hi"]))
        exp.append(" ".join(map(str, c["coef"])))
    assert vec(host, lines) == exp


def test_windows(host, golden):
    cases = golden["windows"]
    out = vec(host, [q(t="window", kind=c["kind"], n=c["n"], sll=c["sll"]) for c in cases])
    for c, line in zip(cases, out):
        np.testing.assert_allclose([float(v) for v in line.split()], c["w"], atol=1e-12, err_msg=str(c))


def test_delays(host, golden):
    lines, exp = [], []
    for c in golden["delays"]:
        f = c["focus"]
        lines.append(q(t="delays", az=c["az"], **({} if f is None else dict(fx=f[0], fy=f[1], fz=f[2]))))
        exp.append(" ".join(map(str, c["tx"])) + " | " + " ".join(map(str, c["rx"])))
    assert vec(host, lines) == exp


def test_generators(host, golden):
    lines, exp = [], []
    for c in golden["gen"]:
        kw = dict(t="gen", beam=c["beam"], mode=c["mode"], freq=c["freq"], amp=c["amp"], env=c["env_ms"])
        if c["chirp"]:
            kw.update(c0=c["chirp"][0], c1=c["chirp"][1], c2=c["chirp"][2])
        if c["burst"]:
            kw.update(b0=c["burst"][0], b1=c["burst"][1])
        if c["band"]:
            kw.update(lo=c["band"][0], hi=c["band"][1])
        lines.append(q(**kw))
        exp.append(" ".join(c["frames"]))
    assert vec(host, lines) == exp


def scenario_line(name, a):
    kw = dict(t="scenario", name=name)
    for k, v in a.items():
        if k in ("noise", "chirp"):
            kw[k] = 1 if v else None
        elif v is not None:
            kw[k] = v
    return q(**kw)


def test_scenarios(host, golden):
    cases = golden["scenarios"]
    out = vec(host, [scenario_line(c["name"], c["args"]) for c in cases])
    for c, line in zip(cases, out):
        assert line == " ".join(c["frames"]), f"{c['name']} {c['args']}"
    assert vec(host, [q(t="scenario", name="elements", tone=2000, amp=0.25)])[0] == " ".join(golden["elements"])
    assert vec(host, [q(t="scenario", name="sweep_setup", tone=3000, amp=0.25)])[0] == " ".join(golden["sweep_setup"])
    for c in golden["sweep_step"]:
        assert vec(host, [q(t="scenario", name="sweep_step", az=c["az"])])[0] == " ".join(c["frames"])


# ------------------------------------------------------------------ случайные конфигурации
class Capture:
    ser = None

    def __init__(self):
        self.frames = []

    def send(self, frames):
        self.frames += list(frames)


def python_frames(cmd, **kw):
    base = dict(amp=0.25, taper="uniform", sll=30.0, weights=None, off=None, noise=False, chirp=False, tone=3000.0)
    base.update(kw)
    link = Capture()
    with contextlib.redirect_stdout(io.StringIO()):
        cmd(link, argparse.Namespace(**base))
    return " ".join(f.hex() for f in link.frames)


def test_random_beams_match_python(host):
    rnd = random.Random(2026)
    lines, exp = [], []
    for _ in range(300):
        kw = dict(az=round(rnd.uniform(-85, 85), 3), tone=round(rnd.uniform(300, 7000), 1),
                  amp=round(rnd.uniform(0, 0.7), 3), taper=rnd.choice(["uniform", "taylor", "chebyshev", "hann"]),
                  sll=float(rnd.randint(18, 50)))
        kind = rnd.random()
        if kind < 0.2:
            kw["noise"] = True
        elif kind < 0.3:
            kw["chirp"] = True
        if rnd.random() < 0.3:
            off = sorted(rnd.sample(range(1, 17), rnd.randint(1, 8)))
            kw["off"] = ",".join(map(str, off))
        if rnd.random() < 0.15:
            kw["weights"] = ",".join(f"{rnd.uniform(-1, 1):.3f}" for _ in range(16))
        name = rnd.choice(["beam", "focus", "listen"])
        if name == "focus":
            kw.update(x=round(rnd.uniform(-1, 1), 3), y=round(rnd.uniform(0.3, 2.5), 3))
            cmd = dpaa_ctl.cmd_focus
        elif name == "listen":
            kw.update(left=round(rnd.uniform(-80, 80), 2), right=round(rnd.uniform(-80, 80), 2))
            cmd = dpaa_ctl.cmd_listen
        else:
            cmd = dpaa_ctl.cmd_beam
        exp.append(python_frames(cmd, **kw))
        lines.append(scenario_line(name, kw))
    out = vec(host, lines)
    bad = [(ln, o, e) for ln, o, e in zip(lines, out, exp) if o != e]
    assert not bad, f"{len(bad)} несовпадений, первое: {bad[0][0]}"


def test_python_windows_reference():
    """Самопроверка: окна в golden.json — те же, что даёт dpaa.patterns сейчас."""
    g = json.loads(GOLDEN.read_text())
    for c in g["windows"][:6]:
        np.testing.assert_allclose(window(c["n"], c["kind"], c["sll"]), c["w"])


# ------------------------------------------------------------------ контроллер веб-API
class Esp:
    """dpaa_host serve: ESP32 + симулятор ПЛИС, время задаётся явно."""

    def __init__(self, host):
        self.p = subprocess.Popen([str(host), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def _frames(self):
        line = self.p.stdout.readline().split()
        assert line[0] == "FRAMES"
        return line[2:]

    def get(self, now, url):
        self.p.stdin.write(f"{now} {url}\n")
        self.p.stdin.flush()
        state = json.loads(self.p.stdout.readline())
        return state, self._frames()

    def tick(self, now):
        self.p.stdin.write(f"tick {now}\n")
        self.p.stdin.flush()
        return self._frames()

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=5)


@pytest.fixture
def esp(host):
    e = Esp(host)
    yield e
    e.close()


def test_controller_beam_matches_dpaa_ctl(esp):
    st, fr = esp.get(0, "/api/set?mode=beam&az=30&tone=2500&amp=0.25&maxamp=0.5&run=1")
    assert st["run"] and st["mode"] == "beam" and st["err"] == ""
    assert " ".join(fr) == python_frames(dpaa_ctl.cmd_beam, az=30.0, tone=2500.0, amp=0.25)
    # живое обновление: параметры уходят в ближайший такт, не чаще 25 раз в секунду
    st, fr = esp.get(10, "/api/set?az=-20&taper=1&sll=35")
    assert fr == []
    assert esp.tick(20) == []
    fr = esp.tick(45)
    assert " ".join(fr) == python_frames(dpaa_ctl.cmd_beam, az=-20.0, tone=2500.0, amp=0.25, taper="taylor", sll=35.0)
    st, fr = esp.get(50, "/api/stop")
    assert not st["run"] and fr == [hw.encode_write(hw.REG_CTRL, 0).hex()]


def test_controller_amp_limited_for_visitors(esp):
    st, fr = esp.get(0, "/api/set?mode=beam&amp=0.5&run=1")          # потолок по умолчанию 0.3
    assert st["maxamp"] == 0.3
    amp_frames = [f for f in fr if f.startswith("a50013")]
    assert amp_frames == [hw.encode_write(0x13, int(0.3 * ((1 << 17) - 1))).hex()]


def test_controller_sweep_and_state(esp):
    st, fr = esp.get(0, "/api/set?mode=sweep&sf=-40&st=40&sp=4&run=1")
    assert st["mode"] == "sweep" and len(fr) > 40
    angles = []
    for t in range(20, 4000, 20):
        fr = esp.tick(t)
        assert len(fr) == 33                                          # 16 задержек + 16 весов + «применить»
        angles.append(esp.get(t, "/api/state")[0]["cur"])
    assert min(angles) == pytest.approx(-40, abs=1) and max(angles) == pytest.approx(40, abs=1)


def test_controller_elements_cycle(esp):
    esp.get(0, "/api/set?mode=elements&dw=0.5&run=1")
    seen = []
    for t in range(10, 8500, 10):
        if esp.tick(t):
            seen.append(esp.get(t, "/api/state")[0]["el"])
    assert seen[:16] == list(range(1, 16)) + [0]


def test_controller_demo_after_idle_and_visitor_takes_over(esp):
    esp.get(0, "/api/set?idle=10&demo=1")
    assert esp.tick(5000) == []
    fr = esp.tick(10_000)
    st = esp.get(10_000, "/api/state")[0]
    assert st["mode"] == "demo" and st["run"] and st["demo_mode"] == "sweep" and len(fr) > 33
    sent = sum(len(esp.tick(t)) for t in range(10_020, 70_000, 20))
    assert sent > 1000
    st, fr = esp.get(70_000, "/api/set?mode=beam&az=10&run=1")       # посетитель коснулся экрана
    assert st["mode"] == "beam" and st["demo_mode"] == "" and len(fr) == 80


def test_controller_errors(esp):
    st, fr = esp.get(0, "/api/set?mode=beam&off=65535&run=1")
    assert st["err"] == "все элементы выключены" and fr == []
    st, fr = esp.get(10, "/api/set?off=0&cw=1&w=1,2,3")
    assert st["err"] == "нужно 16 весов через запятую"
    st, fr = esp.get(20, "/api/set?w=" + "%2C".join(["1"] * 8 + ["-1"] * 8))
    assert st["err"] == "" and st["w"][8] == -1


def test_controller_reports_fpga_and_peaks(esp):
    esp.get(0, "/api/set?mode=beam&az=0&run=1")
    esp.tick(400)
    on = esp.get(400, "/api/state")[0]
    assert on["fpga"] and len(on["peaks"]) == 17
    esp.get(500, "/api/set?az=60")
    esp.tick(600)
    esp.tick(1000)
    off = esp.get(1000, "/api/state")[0]
    assert on["peaks"][16] > off["peaks"][16] + 10                   # зонд на нормали


# ------------------------------------------------------------------ сборка прошивки
def test_main_compiles_against_arduino_stubs():
    """Проверка src/main.cpp без тулчейна ESP32: заглушки повторяют API arduino-esp32 2.0.x.
    Настоящая сборка под ESP32-S3 — PlatformIO (pio run, см. .github/workflows/ci.yml)."""
    subprocess.run(["g++", "-std=c++17", "-fsyntax-only", "-Wall", "-Wextra", "-Werror",
                    f"-I{FW / 'test' / 'stubs'}", f"-I{FW / 'lib' / 'dpaa' / 'src'}", str(FW / "src" / "main.cpp")],
                   check=True)


def test_embedded_page_is_up_to_date():
    sys.path.insert(0, str(FW / "tools"))
    import embed_web
    assert (FW / "src" / "web_page.h").read_text() == embed_web.render(), \
        "страница изменилась — запустите python firmware/esp32/tools/embed_web.py"
