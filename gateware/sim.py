"""Запуск RTL-симуляций (Icarus Verilog) из Python: стимулы, прогон, разбор результатов."""
import shutil
import subprocess
from pathlib import Path

import numpy as np

GW = Path(__file__).resolve().parent
RTL = GW / "rtl"
TB = GW / "tb"

CORE_SOURCES = ["i2s_clkgen.v", "i2s_tx.v", "i2s_rx.v", "uart_rx.v", "uart_tx.v",
                "uart_cmd.v", "sig_gen.v", "delay_sum_engine.v", "dpaa_core.v"]


def have_iverilog():
    return shutil.which("iverilog") is not None and shutil.which("vvp") is not None


def build(top, sources, workdir, params=None):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / f"{top}.vvp"
    cmd = ["iverilog", "-g2012", "-o", str(out), "-s", top]
    for k, v in (params or {}).items():
        cmd.append(f"-P{top}.{k}={v}")
    cmd += [str(RTL / s) for s in sources] + [str(TB / f"{top}.v")]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out


def run(vvp_file, plusargs, timeout=600):
    # $readmemh ищет *.hex относительно текущего каталога — запускаем из rtl/
    args = ["vvp", "-n", str(vvp_file)] + [f"+{k}={v}" for k, v in plusargs.items()]
    res = subprocess.run(args, cwd=RTL, check=True, capture_output=True, text=True, timeout=timeout)
    return res.stdout


def write_mem(path, values, bits):
    mask = (1 << bits) - 1
    digits = (bits + 3) // 4
    Path(path).write_text("".join(f"{int(v) & mask:0{digits}x}\n" for v in np.ravel(values)))


def to_signed(v, bits):
    v = np.asarray(v, dtype=np.int64)
    return np.where(v >= 1 << (bits - 1), v - (1 << bits), v)


def read_rows(path, bits=24):
    """Строки файла (hex через пробел) -> массив int со знаком; комментарии '#' — маркеры."""
    rows, marks = [], {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("#"):
            marks[line[1:].strip()] = len(rows)
            continue
        if line.strip():
            rows.append([int(t, 16) if "x" not in t else 0 for t in line.split()])
    return to_signed(np.array(rows), bits), marks
