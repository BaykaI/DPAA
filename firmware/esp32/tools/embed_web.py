"""Упаковка веб-страницы в прошивку: web/index.html -> src/web_page.h (gzip, массив байтов).

Запуск:  python tools/embed_web.py      (PlatformIO вызывает его сам перед сборкой)
Сжатие детерминированное (mtime = 0), поэтому файл меняется только вместе со страницей.
"""
import gzip
from pathlib import Path

try:
    HERE = Path(__file__).resolve().parents[1]
except NameError:                     # PlatformIO выполняет скрипт через SCons, без __file__
    Import("env")                     # noqa: F821
    HERE = Path(env["PROJECT_DIR"])   # noqa: F821
SRC = HERE / "web" / "index.html"
DST = HERE / "src" / "web_page.h"


def render() -> str:
    data = gzip.compress(SRC.read_bytes(), compresslevel=9, mtime=0)
    rows = [", ".join(f"0x{b:02x}" for b in data[i:i + 20]) for i in range(0, len(data), 20)]
    body = ",\n  ".join(rows)
    return ("// Сгенерировано tools/embed_web.py из web/index.html — не редактировать вручную.\n"
            "#pragma once\n#include <stddef.h>\n#include <stdint.h>\n\n"
            f"// {SRC.stat().st_size} байт страницы, {len(data)} байт в gzip\n"
            f"static const uint8_t WEB_PAGE_GZ[] = {{\n  {body}\n}};\n"
            f"static const size_t WEB_PAGE_GZ_LEN = {len(data)};\n")


def main():
    text = render()
    if not DST.exists() or DST.read_text() != text:
        DST.write_text(text)
        print("web_page.h обновлён:", DST)


# PlatformIO: extra_scripts = pre:tools/embed_web.py
if __name__ in ("__main__", "SCons.Script"):
    main()
