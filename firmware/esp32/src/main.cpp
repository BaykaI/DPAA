// Wi-Fi-пульт акустической ЦАФАР на ESP32-S3-DevKitC-1.
//
//   планшет --Wi-Fi--> ESP32 (точка доступа, веб-страница) --UART1 1 Мбит/с--> ПЛИС
//
// Вся логика — в lib/dpaa (контроллер и ядро, проверены на компьютере против Python-модели),
// здесь только «железо»: UART, Wi-Fi, веб-сервер, хранение настроек.
//
// Подключение к распределительной плате (разъём J25, docs/hardware/wiring.md):
//   GPIO17 (TX UART1) -> J25.2 -> ПЛИС esp_rx;   GPIO18 (RX UART1) <- J25.1 <- ПЛИС esp_tx;   GND -> J25.3
#include <Arduino.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>

#include "controller.h"
#include "web_page.h"

namespace {

constexpr int kUartTx = 17;
constexpr int kUartRx = 18;
constexpr uint32_t kUartBaud = 1000000;
constexpr uint32_t kReadTimeoutUs = 3000;      // ответ ПЛИС приходит через ~0.2 мс
constexpr uint32_t kSaveDelayMs = 3000;        // настройки пишем во флеш не чаще, чем раз в 3 с
const char* const kDefaultSsid = "DPAA";
const char* const kDefaultPass = "dpaa2026";   // не короче 8 символов (требование WPA2)
const IPAddress kIp(192, 168, 4, 1);

/// Канал к ПЛИС через UART1. ПЛИС отвечает сразу в оба порта (ноутбуку и ESP32),
/// поэтому перед чтением входной буфер очищается, а ответ проверяется по адресу.
class UartLink : public dpaa::Link {
 public:
  explicit UartLink(HardwareSerial& s) : s_(s) {}

  void send(const dpaa::Frames& frames) override {
    for (const dpaa::Frame& f : frames) s_.write(f.b, dpaa::kFrameLen);
  }

  bool read(int addr, int32_t& value) override {
    while (s_.available()) s_.read();
    const dpaa::Frame req = dpaa::encode_read(addr);
    s_.write(req.b, dpaa::kFrameLen);
    uint8_t buf[dpaa::kFrameLen];
    int n = 0;
    const uint32_t t0 = micros();
    while (micros() - t0 < kReadTimeoutUs) {
      if (!s_.available()) continue;
      const uint8_t b = uint8_t(s_.read());
      if (n == 0 && b != 0x5A) continue;        // ждём начало кадра ответа
      buf[n++] = b;
      if (n == dpaa::kFrameLen) {
        int a = 0;
        int32_t d = 0;
        if (dpaa::decode_response(buf, a, d) && a == addr) {
          value = d;
          return true;
        }
        n = 0;                                  // чужой или повреждённый ответ — ищем дальше
      }
    }
    return false;
  }

 private:
  HardwareSerial& s_;
};

UartLink link(Serial1);
dpaa::Controller ctl(link);
WebServer server(80);
DNSServer dns;
Preferences prefs;
uint32_t settings_changed_at = 0;
bool settings_pending = false;

void load_settings() {
  prefs.begin("dpaa", true);
  dpaa::Settings& s = ctl.settings();
  s.max_amp = prefs.getFloat("maxamp", float(s.max_amp));
  s.demo = prefs.getBool("demo", s.demo);
  s.demo_idle_s = prefs.getUInt("idle", s.demo_idle_s);
  prefs.end();
}

void save_settings() {
  prefs.begin("dpaa", false);
  const dpaa::Settings& s = ctl.settings();
  prefs.putFloat("maxamp", float(s.max_amp));
  prefs.putBool("demo", s.demo);
  prefs.putUInt("idle", s.demo_idle_s);
  prefs.end();
}

void handle_api() {
  dpaa::Query q;
  for (int i = 0; i < server.args(); i++) q[server.argName(i).c_str()] = server.arg(i).c_str();
  const std::string json = ctl.handle(server.uri().c_str(), q, millis());
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json; charset=utf-8", json.c_str());
}

void handle_page() {
  server.sendHeader("Content-Encoding", "gzip");
  server.sendHeader("Cache-Control", "no-cache");
  server.send_P(200, "text/html; charset=utf-8", reinterpret_cast<const char*>(WEB_PAGE_GZ), WEB_PAGE_GZ_LEN);
}

/// Смена имени и пароля сети: /api/wifi?ssid=...&pass=... (пароль от 8 символов), затем перезагрузка.
void handle_wifi() {
  const String ssid = server.arg("ssid"), pass = server.arg("pass");
  if (ssid.length() == 0 || ssid.length() > 32 || pass.length() < 8 || pass.length() > 63) {
    server.send(400, "text/plain; charset=utf-8", "нужны ssid (1-32 символа) и pass (8-63 символа)");
    return;
  }
  prefs.begin("dpaa", false);
  prefs.putString("ssid", ssid);
  prefs.putString("pass", pass);
  prefs.end();
  server.send(200, "text/plain; charset=utf-8", "сохранено, перезагрузка");
  delay(300);
  ESP.restart();
}

/// Любой другой адрес (проверки «есть ли интернет» телефонов и планшетов) — на страницу пульта:
/// так при подключении к сети страница открывается сама.
void handle_other() {
  server.sendHeader("Location", String("http://") + kIp.toString() + "/");
  server.send(302, "text/plain", "");
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial1.setRxBufferSize(256);
  Serial1.setTxBufferSize(1024);                // таблица луча (≈ 560 байт) уходит без ожидания
  Serial1.begin(kUartBaud, SERIAL_8N1, kUartRx, kUartTx);

  load_settings();
  prefs.begin("dpaa", true);
  const String ssid = prefs.getString("ssid", kDefaultSsid);
  const String pass = prefs.getString("pass", kDefaultPass);
  prefs.end();

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(kIp, kIp, IPAddress(255, 255, 255, 0));
  WiFi.softAP(ssid.c_str(), pass.c_str(), 6, 0, 8);
  WiFi.setSleep(false);                         // без энергосбережения — меньше задержка «руля»
  dns.start(53, "*", kIp);
  MDNS.begin("dpaa");                           // http://dpaa.local/
  MDNS.addService("http", "tcp", 80);

  server.on("/", HTTP_GET, handle_page);
  server.on("/api/state", HTTP_GET, handle_api);
  server.on("/api/set", HTTP_GET, handle_api);
  server.on("/api/stop", HTTP_GET, handle_api);
  server.on("/api/wifi", HTTP_GET, handle_wifi);
  server.onNotFound(handle_other);
  server.begin();

  ctl.handle("/api/stop", dpaa::Query(), millis());   // после включения — тишина
  Serial.printf("DPAA: Wi-Fi \"%s\", http://%s/ или http://dpaa.local/\n", ssid.c_str(), kIp.toString().c_str());
}

void loop() {
  dns.processNextRequest();
  server.handleClient();
  ctl.tick(millis());
  if (ctl.take_settings_dirty()) {
    settings_pending = true;
    settings_changed_at = millis();
  }
  if (settings_pending && millis() - settings_changed_at >= kSaveDelayMs) {
    settings_pending = false;
    save_settings();
  }
}
