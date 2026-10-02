"""Веб-страница пульта ESP32 в настоящем браузере (Chromium через Playwright).

Страница работает с логикой прошивки, собранной на компьютере (firmware/esp32/test/web_mock.py):
нажатия кнопок и движения пальцем по плану зала должны превращаться в кадры для ПЛИС.
Снимки экрана сохраняются в out/esp32_web/. Нужны g++ и playwright (иначе тест пропускается).
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "firmware" / "esp32" / "test"))
playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="нужен g++")

SHOTS = ROOT / "out" / "esp32_web"


@pytest.fixture(scope="module")
def mock(tmp_path_factory):
    from web_mock import MockEsp, build_host
    m = MockEsp(build_host(tmp_path_factory.mktemp("host")))
    yield m
    m.close()


@pytest.fixture(scope="module")
def page(mock):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            exe = next(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"), None)
            if exe is None:
                pytest.skip("нет Chromium для Playwright")
            browser = p.chromium.launch(executable_path=str(exe))
        pg = browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{mock.port}/")
        pg.wait_for_function("document.getElementById('st-fpga').textContent.includes('связь есть')")
        pg.errors = errors
        yield pg
        browser.close()


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def drag_on_hall(page, x_m, y_m):
    """Коснуться плана зала в точке (x, y) метров."""
    box = page.locator("#hall").bounding_box()
    sx = (x_m + 2) / 4 * box["width"] + box["x"]
    sy = box["y"] + box["height"] - (y_m + 0.3) / 4 * box["width"]
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx + 1, sy)
    page.mouse.up()


def test_beam_by_finger(page, mock):
    page.click("[data-mode=beam]")
    page.wait_for_function("document.getElementById('st-run').textContent.includes('звучит')")
    before = mock.frames_sent
    drag_on_hall(page, 1.0, 1.0)                                   # 45° вправо
    page.wait_for_timeout(300)
    st = mock.state()
    assert st["mode"] == "beam" and st["run"] and st["az"] == 45
    assert mock.frames_sent >= before + 80                         # таблица луча ушла в ПЛИС
    shot(page, "1_beam")


def test_scenarios_and_stop(page, mock):
    page.click("[data-mode=sweep]")
    page.wait_for_timeout(1200)
    assert mock.state()["mode"] == "sweep"
    shot(page, "2_sweep")
    page.click("[data-mode=two]")
    drag_on_hall(page, -1.2, 1.0)                                  # ближе к лучу 1 (−35°)
    page.wait_for_timeout(300)
    st = mock.state()
    assert st["mode"] == "two" and st["az1"] == -50
    shot(page, "3_two")
    page.click("[data-mode=focus]")
    drag_on_hall(page, -0.5, 0.8)
    page.wait_for_timeout(300)
    st = mock.state()
    assert st["mode"] == "focus" and abs(st["fx"] + 0.5) < 0.03 and abs(st["fy"] - 0.8) < 0.03
    shot(page, "4_focus")
    page.click("#stop")
    page.wait_for_function("document.getElementById('st-run').textContent === 'тишина'")
    assert not mock.state()["run"]


def test_service_panel(page, mock):
    page.click("#gear")
    page.select_option("#taper", "1")
    page.click("#every2")
    page.click("[data-mode=beam]")
    page.wait_for_timeout(400)
    st = mock.state()
    assert st["taper"] == 1 and st["off"] == 0xAAAA
    shot(page, "5_service")
    page.click("#all-on")
    page.click("#gear")
    assert page.errors == []
