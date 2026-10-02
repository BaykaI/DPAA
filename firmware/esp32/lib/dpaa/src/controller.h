// Контроллер пульта: состояние экспоната, веб-API, сканирование, поэлементный тест,
// автопилот для музея и опрос уровней. Не зависит от Arduino: время и канал к ПЛИС
// передаются снаружи, поэтому логика проверяется на компьютере (test/host).
#pragma once

#include <cstdint>
#include <map>
#include <string>

#include "dpaa_core.h"

namespace dpaa {

/// Канал к ПЛИС (на ESP32 — UART1 1 Мбит/с, на компьютере — симулятор).
class Link {
 public:
  virtual ~Link() = default;
  virtual void send(const Frames& frames) = 0;
  virtual bool read(int addr, int32_t& value) = 0;
};

enum class Mode { Beam, Sweep, Focus, Two, Elements, Listen, Demo };
const char* mode_name(Mode m);
bool mode_from_name(const std::string& s, Mode& m);

/// Настройки, которые хранятся в энергонезависимой памяти ESP32.
struct Settings {
  double max_amp = 0.3;          // потолок громкости для посетителей (не больше kMaxAmp)
  bool demo = true;              // автопилот, когда экспонатом никто не пользуется
  uint32_t demo_idle_s = 90;     // через сколько секунд без касаний включается автопилот
};

using Query = std::map<std::string, std::string>;
Query parse_query(const std::string& qs);  // "a=1&b=2" -> {a:1, b:2} (с декодированием %XX и '+')

class Controller {
 public:
  explicit Controller(Link& link);

  /// Запрос веб-API: "/api/state", "/api/set", "/api/stop". Возвращает JSON состояния.
  std::string handle(const std::string& path, const Query& q, uint32_t now_ms);
  /// Вызывать часто (каждые 1–10 мс): сканирование, тест, автопилот, отправка, опрос уровней.
  void tick(uint32_t now_ms);

  Settings& settings() { return settings_; }
  /// true, если настройки изменились и их пора сохранить (флаг сбрасывается).
  bool take_settings_dirty();
  std::string state_json() const;

  // параметры (открыты для тестов)
  Mode mode = Mode::Beam;
  bool running = false;
  Source src;
  double amp = 0.2;
  double az = 0;
  double sweep_from = -60, sweep_to = 60, sweep_period = 6;
  double fx = 0.3, fy = 1.0;
  double az1 = -35, az2 = 35, tone1 = 2500;
  Source src2{SourceKind::Chirp, 3500};
  double elem_tone = 2000, dwell = 0.7;
  int element = -1;
  double left = -30, right = 30;
  Distribution dist;
  std::string error;

  // состояние ПЛИС
  bool fpga_ok = false;
  int32_t fpga_id = 0, fpga_frames = 0;
  double peaks_db[kNMics + 1] = {};

 private:
  bool apply(bool start, uint32_t now_ms);        // собрать кадры текущего режима и отправить
  bool build(Frames& out, Mode m, bool start);    // кадры режима (без отправки)
  void stop();
  void set_params(const Query& q);
  void demo_step(uint32_t now_ms);
  void poll(uint32_t now_ms);

  Link& link_;
  Settings settings_;
  bool settings_dirty_ = false;
  bool weights_bad_ = false;
  bool id_checked_ = false;
  bool dirty_ = false;
  uint32_t last_touch_ = 0, last_send_ = 0, last_poll_ = 0, last_id_ = 0;
  uint32_t mode_start_ = 0, element_t_ = 0;
  double sweep_now_ = 0;
  // автопилот
  int demo_idx_ = -1;
  uint32_t demo_t_ = 0;
  Mode demo_mode_ = Mode::Sweep;
};

}  // namespace dpaa
