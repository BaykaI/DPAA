#include "controller.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace dpaa {

namespace {
constexpr double kPi = 3.14159265358979323846;
constexpr uint32_t kSendPeriodMs = 40;    // живое обновление луча — до 25 раз в секунду
constexpr uint32_t kSweepPeriodMs = 20;   // сканирование — 50 обновлений в секунду
constexpr uint32_t kPollPeriodMs = 300;   // опрос уровней микрофонов
constexpr uint32_t kIdPeriodMs = 2000;    // проверка связи с ПЛИС
constexpr uint32_t kDemoStepMs = 15000;   // длительность одного номера автопилота
constexpr int kDemoSteps = 4;

double clampd(double v, double lo, double hi) { return std::min(std::max(v, lo), hi); }

bool get(const Query& q, const char* k, double& v) {
  auto it = q.find(k);
  if (it == q.end() || it->second.empty()) return false;
  char* end = nullptr;
  const double x = std::strtod(it->second.c_str(), &end);
  if (end == it->second.c_str() || !std::isfinite(x)) return false;
  v = x;
  return true;
}

int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

std::string url_decode(const std::string& s) {
  std::string r;
  for (size_t i = 0; i < s.size(); i++) {
    if (s[i] == '+') {
      r += ' ';
    } else if (s[i] == '%' && i + 2 < s.size() && hexval(s[i + 1]) >= 0 && hexval(s[i + 2]) >= 0) {
      r += char(hexval(s[i + 1]) * 16 + hexval(s[i + 2]));
      i += 2;
    } else {
      r += s[i];
    }
  }
  return r;
}

void append(std::string& s, const char* fmt, double v) {
  char buf[48];
  std::snprintf(buf, sizeof buf, fmt, v);
  s += buf;
}
}  // namespace

const char* mode_name(Mode m) {
  switch (m) {
    case Mode::Beam: return "beam";
    case Mode::Sweep: return "sweep";
    case Mode::Focus: return "focus";
    case Mode::Two: return "two";
    case Mode::Elements: return "elements";
    case Mode::Listen: return "listen";
    case Mode::Demo: return "demo";
  }
  return "beam";
}

bool mode_from_name(const std::string& s, Mode& m) {
  for (Mode x : {Mode::Beam, Mode::Sweep, Mode::Focus, Mode::Two, Mode::Elements, Mode::Listen, Mode::Demo})
    if (s == mode_name(x)) {
      m = x;
      return true;
    }
  return false;
}

Query parse_query(const std::string& qs) {
  Query q;
  size_t i = 0;
  while (i <= qs.size()) {
    size_t amp = qs.find('&', i);
    if (amp == std::string::npos) amp = qs.size();
    const std::string kv = qs.substr(i, amp - i);
    if (!kv.empty()) {
      const size_t eq = kv.find('=');
      if (eq == std::string::npos)
        q[url_decode(kv)] = "";
      else
        q[url_decode(kv.substr(0, eq))] = url_decode(kv.substr(eq + 1));
    }
    i = amp + 1;
  }
  return q;
}

Controller::Controller(Link& link) : link_(link) {}

bool Controller::take_settings_dirty() {
  const bool d = settings_dirty_;
  settings_dirty_ = false;
  return d;
}

// ------------------------------------------------------------------ веб-API
std::string Controller::handle(const std::string& path, const Query& q, uint32_t now_ms) {
  if (path == "/api/state") return state_json();
  if (path == "/api/stop") {
    last_touch_ = now_ms;
    stop();
    return state_json();
  }
  if (path != "/api/set") return "{\"error\":\"неизвестный запрос\"}";

  last_touch_ = now_ms;
  const Mode before = mode;
  const bool was_demo = mode == Mode::Demo;
  set_params(q);
  auto it = q.find("mode");
  Mode m;
  if (it != q.end() && mode_from_name(it->second, m)) mode = m;
  if (was_demo && mode == Mode::Demo) mode = Mode::Beam;   // посетитель коснулся — автопилот уступает
  if (mode == Mode::Demo) mode = Mode::Beam;                // автопилот включается только сам

  it = q.find("run");
  if (it != q.end()) {
    if (it->second == "1") {
      running = true;
      mode_start_ = now_ms;
      element = mode == Mode::Elements ? 0 : -1;
      element_t_ = now_ms;
      sweep_now_ = sweep_from;
      apply(true, now_ms);
    } else {
      stop();
    }
  } else if (running && (mode != before || was_demo)) {
    mode_start_ = now_ms;
    element = mode == Mode::Elements ? 0 : -1;
    element_t_ = now_ms;
    sweep_now_ = sweep_from;
    apply(true, now_ms);                                    // сменился сценарий — запускаем его сразу
  } else {
    dirty_ = true;                                          // параметры уйдут в ближайший такт
    Frames check;
    build(check, mode, true);                               // проверка параметров: ошибку покажет state_json
  }
  return state_json();
}

void Controller::set_params(const Query& q) {
  double v;
  if (get(q, "src", v)) src.kind = SourceKind(int(clampd(v, 0, 2)));
  if (get(q, "tone", v)) src.tone_hz = clampd(v, 200, 8000);
  if (get(q, "amp", v)) amp = clampd(v, 0, kMaxAmp);
  if (get(q, "az", v)) az = clampd(v, -85, 85);
  if (get(q, "sf", v)) sweep_from = clampd(v, -85, 85);
  if (get(q, "st", v)) sweep_to = clampd(v, -85, 85);
  if (get(q, "sp", v)) sweep_period = clampd(v, 1, 60);
  if (get(q, "fx", v)) fx = clampd(v, -2, 2);
  if (get(q, "fy", v)) fy = clampd(v, 0.15, 4);
  if (get(q, "az1", v)) az1 = clampd(v, -85, 85);
  if (get(q, "az2", v)) az2 = clampd(v, -85, 85);
  if (get(q, "t1", v)) tone1 = clampd(v, 200, 8000);
  if (get(q, "s2", v)) src2.kind = SourceKind(int(clampd(v, 0, 2)));
  if (get(q, "t2", v)) src2.tone_hz = clampd(v, 200, 8000);
  if (get(q, "et", v)) elem_tone = clampd(v, 200, 8000);
  if (get(q, "dw", v)) dwell = clampd(v, 0.1, 5);
  if (get(q, "left", v)) left = clampd(v, -85, 85);
  if (get(q, "right", v)) right = clampd(v, -85, 85);
  if (get(q, "taper", v)) dist.taper = Taper(int(clampd(v, 0, 3)));
  if (get(q, "sll", v)) dist.sll_db = clampd(v, 15, 60);
  if (get(q, "off", v)) dist.off_mask = uint32_t(clampd(v, 0, 0xFFFF));
  if (get(q, "cw", v)) dist.use_weights = v != 0;
  auto it = q.find("w");
  if (it != q.end()) {
    double w[kNElem];
    int n = 0;
    const char* p = it->second.c_str();
    while (*p && n < kNElem + 1) {
      char* end = nullptr;
      const double x = std::strtod(p, &end);
      if (end == p) break;
      if (n < kNElem) w[n] = x;
      n++;
      p = end;
      while (*p == ',' || *p == ';' || *p == ' ') p++;
    }
    weights_bad_ = n != kNElem;
    if (!weights_bad_) std::copy(w, w + kNElem, dist.weights);
  }
  // настройки экспоната
  if (get(q, "maxamp", v)) {
    settings_.max_amp = clampd(v, 0, kMaxAmp);
    settings_dirty_ = true;
  }
  if (get(q, "demo", v)) {
    settings_.demo = v != 0;
    settings_dirty_ = true;
  }
  if (get(q, "idle", v)) {
    settings_.demo_idle_s = uint32_t(clampd(v, 10, 3600));
    settings_dirty_ = true;
  }
}

// ------------------------------------------------------------------ кадры режимов
bool Controller::build(Frames& out, Mode m, bool start) {
  const double a = std::min(amp, settings_.max_amp);
  double tmp[kNElem];
  if (m != Mode::Elements && m != Mode::Demo && !dist.element_weights(kNElem, tmp)) {
    error = "все элементы выключены";
    return false;
  }
  bool ok = true;
  switch (m) {
    case Mode::Beam: ok = scenario_beam(out, src, az, dist, a); break;
    case Mode::Sweep:
      if (start) ok = scenario_sweep_setup(out, src, a);
      ok = ok && scenario_sweep_step(out, sweep_now_, dist);
      break;
    case Mode::Focus: ok = scenario_focus(out, src, fx, fy, dist, a); break;
    case Mode::Two: ok = scenario_two(out, Source{SourceKind::Tone, tone1}, az1, src2, az2, dist, a); break;
    case Mode::Elements:
      scenario_elements_setup(out, elem_tone, a);
      if (start) scenario_element_step(out, std::max(0, element));
      break;
    case Mode::Listen: ok = scenario_listen(out, left, right, dist); break;
    case Mode::Demo: break;
  }
  if (!ok) {
    error = "задержка вне диапазона: точка фокуса слишком далеко";
    return false;
  }
  error.clear();
  return true;
}

bool Controller::apply(bool start, uint32_t now_ms) {
  Frames f;
  if (!build(f, mode, start)) return false;
  if (!f.empty()) link_.send(f);
  last_send_ = now_ms;
  dirty_ = false;
  return true;
}

void Controller::stop() {
  if (mode == Mode::Demo) mode = Mode::Beam;
  running = false;
  element = -1;
  dirty_ = false;
  Frames f;
  scenario_mute(f);
  link_.send(f);
}

// ------------------------------------------------------------------ такт
void Controller::tick(uint32_t now_ms) {
  poll(now_ms);

  // автопилот не перебивает служебные режимы: поэлементный тест и приём в наушники
  const bool service = running && (mode == Mode::Elements || mode == Mode::Listen);
  if (settings_.demo && mode != Mode::Demo && !service && now_ms - last_touch_ >= settings_.demo_idle_s * 1000u) {
    mode = Mode::Demo;
    running = true;
    demo_idx_ = -1;
  }
  if (!running) return;

  switch (mode) {
    case Mode::Demo:
      demo_step(now_ms);
      break;
    case Mode::Sweep:
      if (now_ms - last_send_ >= kSweepPeriodMs) {
        sweep_now_ = sweep_angle((now_ms - mode_start_) / 1000.0, sweep_from, sweep_to, sweep_period);
        Frames f;
        if (dirty_) {        // мог смениться сигнал — полная настройка
          dirty_ = false;
          if (build(f, Mode::Sweep, true)) link_.send(f);
        } else if (scenario_sweep_step(f, sweep_now_, dist)) {
          link_.send(f);
        }
        last_send_ = now_ms;
      }
      break;
    case Mode::Elements:
      if (dirty_ && now_ms - last_send_ >= kSendPeriodMs) apply(false, now_ms);
      if (now_ms - element_t_ >= uint32_t(dwell * 1000)) {
        element = (element + 1) % kNElem;
        element_t_ = now_ms;
        Frames f;
        scenario_element_step(f, element);
        link_.send(f);
      }
      break;
    default:
      if (dirty_ && now_ms - last_send_ >= kSendPeriodMs) apply(false, now_ms);
      break;
  }
}

// Автопилот: четыре номера по 15 с, тихо (не громче 0.2 и не громче потолка для посетителей).
void Controller::demo_step(uint32_t now_ms) {
  bool start = false;
  if (demo_idx_ < 0 || now_ms - demo_t_ >= kDemoStepMs) {
    demo_idx_ = (demo_idx_ + 1) % kDemoSteps;
    demo_t_ = now_ms;
    start = true;
  }
  const double a = std::min(0.2, settings_.max_amp);
  const double t = (now_ms - demo_t_) / 1000.0;
  const Distribution uniform;
  Frames f;
  switch (demo_idx_) {
    case 0:  // маятник тоном 2.5 кГц
    case 3:  // маятник шумом — луч «слышно» шире всего спектра
      demo_mode_ = Mode::Sweep;
      if (start || now_ms - last_send_ >= kSweepPeriodMs) {
        const Source s{demo_idx_ == 0 ? SourceKind::Tone : SourceKind::Noise, 2500};
        sweep_now_ = sweep_angle(t, -60, 60, demo_idx_ == 0 ? 6 : 8);
        if (start) scenario_sweep_setup(f, s, a);
        scenario_sweep_step(f, sweep_now_, uniform);
      }
      break;
    case 1:  // два луча: тон налево, ЛЧМ-пачки направо
      demo_mode_ = Mode::Two;
      if (start)
        scenario_two(f, Source{SourceKind::Tone, 2500}, -35, Source{SourceKind::Chirp, 3500}, 35, uniform, a);
      break;
    case 2:  // «прожектор»: точка фокуса гуляет по залу в метре от решётки
      demo_mode_ = Mode::Focus;
      if (start || now_ms - last_send_ >= 100) {
        sweep_now_ = 0.6 * std::sin(2 * kPi * t / 8);
        scenario_focus(f, Source{SourceKind::Tone, 3000}, sweep_now_, 1.0, uniform, a);
      }
      break;
  }
  if (!f.empty()) {
    link_.send(f);
    last_send_ = now_ms;
  }
}

// ------------------------------------------------------------------ опрос ПЛИС
void Controller::poll(uint32_t now_ms) {
  // связь проверяется по идентификатору раз в 2 с; пока её нет, уровни не опрашиваются,
  // чтобы ожидание ответа не тормозило веб-сервер
  if (!id_checked_ || now_ms - last_id_ >= kIdPeriodMs) {
    id_checked_ = true;
    last_id_ = now_ms;
    int32_t id = 0;
    fpga_ok = link_.read(kRegId, id) && id == kIdValue;
    fpga_id = id;
  }
  if (!fpga_ok || now_ms - last_poll_ < kPollPeriodMs) return;
  last_poll_ = now_ms;
  for (int i = 0; i <= kNMics; i++) {
    int32_t v = 0;
    if (!link_.read(kRegPeak + i, v)) {
      fpga_ok = false;
      return;
    }
    peaks_db[i] = 20 * std::log10(std::max<int32_t>(v, 1) / double(1 << 23));
  }
  int32_t fr = 0;
  if (link_.read(kRegFrames, fr)) fpga_frames = fr;
}

// ------------------------------------------------------------------ состояние для веб-страницы
std::string Controller::state_json() const {
  std::string s = "{";
  s += std::string("\"fpga\":") + (fpga_ok ? "true" : "false");
  append(s, ",\"frames\":%.0f", double(fpga_frames));
  s += std::string(",\"mode\":\"") + mode_name(mode) + "\"";
  s += std::string(",\"run\":") + (running ? "true" : "false");
  s += std::string(",\"demo_mode\":\"") + (mode == Mode::Demo ? mode_name(demo_mode_) : "") + "\"";
  s += ",\"err\":\"" + (weights_bad_ ? std::string("нужно 16 весов через запятую") : error) + "\"";
  append(s, ",\"src\":%.0f", double(int(src.kind)));
  append(s, ",\"tone\":%.6g", src.tone_hz);
  append(s, ",\"amp\":%.6g", amp);
  append(s, ",\"az\":%.6g", az);
  append(s, ",\"sf\":%.6g", sweep_from);
  append(s, ",\"st\":%.6g", sweep_to);
  append(s, ",\"sp\":%.6g", sweep_period);
  append(s, ",\"cur\":%.4g", sweep_now_);
  append(s, ",\"fx\":%.6g", fx);
  append(s, ",\"fy\":%.6g", fy);
  append(s, ",\"az1\":%.6g", az1);
  append(s, ",\"az2\":%.6g", az2);
  append(s, ",\"t1\":%.6g", tone1);
  append(s, ",\"s2\":%.0f", double(int(src2.kind)));
  append(s, ",\"t2\":%.6g", src2.tone_hz);
  append(s, ",\"et\":%.6g", elem_tone);
  append(s, ",\"dw\":%.6g", dwell);
  append(s, ",\"el\":%.0f", double(element));
  append(s, ",\"left\":%.6g", left);
  append(s, ",\"right\":%.6g", right);
  append(s, ",\"taper\":%.0f", double(int(dist.taper)));
  append(s, ",\"sll\":%.6g", dist.sll_db);
  append(s, ",\"off\":%.0f", double(dist.off_mask));
  s += std::string(",\"cw\":") + (dist.use_weights ? "true" : "false");
  s += ",\"w\":[";
  for (int i = 0; i < kNElem; i++) append(s, i ? ",%.4g" : "%.4g", dist.weights[i]);
  s += "]";
  // фактические нормированные веса элементов — по ним страница рисует лепесток
  double gw[kNElem] = {};
  if (mode == Mode::Elements) {
    if (element >= 0) gw[element] = 1;
  } else if (mode == Mode::Demo) {
    std::fill(gw, gw + kNElem, 1.0);                        // автопилот — равномерное распределение
  } else if (!dist.element_weights(kNElem, gw)) {
    std::fill(gw, gw + kNElem, 0.0);
  }
  s += ",\"gw\":[";
  for (int i = 0; i < kNElem; i++) append(s, i ? ",%.4g" : "%.4g", gw[i]);
  s += "]";
  append(s, ",\"maxamp\":%.6g", settings_.max_amp);
  s += std::string(",\"demo\":") + (settings_.demo ? "true" : "false");
  append(s, ",\"idle\":%.0f", double(settings_.demo_idle_s));
  s += ",\"peaks\":[";
  for (int i = 0; i <= kNMics; i++) append(s, i ? ",%.1f" : "%.1f", peaks_db[i]);
  s += "]}";
  return s;
}

}  // namespace dpaa
