"""«ESP32 на компьютере»: веб-страница пульта + настоящая логика прошивки + симулятор ПЛИС.

Страница web/index.html отдаётся как есть, а запросы /api/... обрабатывает тот же C++-код,
что работает в ESP32 (test/host/dpaa_host.cpp в режиме serve). Нужен g++.

    python firmware/esp32/test/web_mock.py          # http://localhost:8080/
    python firmware/esp32/test/web_mock.py --port 9000

Используется и в автотесте страницы (tests/test_esp32_web.py).
"""
import argparse
import json
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FW = Path(__file__).resolve().parents[1]


def build_host(out_dir=None) -> Path:
    out = Path(out_dir or tempfile.mkdtemp()) / "dpaa_host"
    src = sorted(str(p) for p in (FW / "lib" / "dpaa" / "src").glob("*.cpp"))
    subprocess.run(["g++", "-std=c++17", "-O2", f"-I{FW / 'lib' / 'dpaa' / 'src'}",
                    str(FW / "test" / "host" / "dpaa_host.cpp"), *src, "-o", str(out)], check=True)
    return out


class MockEsp:
    def __init__(self, host_exe: Path, port: int = 0):
        self.proc = subprocess.Popen([str(host_exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True)
        self.lock = threading.Lock()
        self.t0 = time.monotonic()
        self.frames_sent = 0
        self.requests = []
        self._stop = threading.Event()
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/api/"):
                    body = mock.request(self.path).encode()
                    ctype = "application/json; charset=utf-8"
                elif self.path in ("/", "/index.html"):
                    body = (FW / "web" / "index.html").read_bytes()
                    ctype = "text/html; charset=utf-8"
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        threading.Thread(target=self._ticker, daemon=True).start()

    def now_ms(self):
        return int((time.monotonic() - self.t0) * 1000)

    def _exchange(self, line, with_json):
        with self.lock:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            js = self.proc.stdout.readline() if with_json else None
            fr = self.proc.stdout.readline().split()
            self.frames_sent += int(fr[1])
            return js

    def request(self, url):
        self.requests.append(url)
        return self._exchange(f"{self.now_ms()} {url}", True).strip()

    def state(self):
        return json.loads(self.request("/api/state"))

    def _ticker(self):
        while not self._stop.is_set():
            self._exchange(f"tick {self.now_ms()}", False)
            time.sleep(0.02)

    def close(self):
        self._stop.set()
        self.server.shutdown()
        time.sleep(0.05)
        with self.lock:
            self.proc.stdin.close()
        self.proc.wait(timeout=5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    mock = MockEsp(build_host(), args.port)
    print(f"Пульт: http://localhost:{mock.port}/  (Ctrl+C — выход)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mock.close()


if __name__ == "__main__":
    main()
