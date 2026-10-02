// Сборка ядра прошивки на компьютере (без ESP32) — для проверки бит в бит и веб-страницы.
//
//   dpaa_host vec    — построчно читает запросы (строка запроса "t=...&...") и печатает
//                      кадры/числа; tests/test_esp32.py сравнивает их с Python-моделью;
//   dpaa_host serve  — изображает ESP32 с симулятором ПЛИС: строки "<мс> /api/...?..."
//                      и "tick <мс>"; печатает JSON ответа и строку "FRAMES n кадры...".
//
// Сборка: g++ -std=c++17 -O2 -I../../lib/dpaa/src dpaa_host.cpp ../../lib/dpaa/src/*.cpp -o dpaa_host
#include <cmath>
#include <complex>
#include <cstdio>
#include <iostream>
#include <map>
#include <string>

#include "controller.h"
#include "dpaa_core.h"

using namespace dpaa;

namespace {

double num(const Query& q, const char* k, double def) {
  auto it = q.find(k);
  return it == q.end() || it->second.empty() ? def : std::strtod(it->second.c_str(), nullptr);
}

std::string str(const Query& q, const char* k, const char* def = "") {
  auto it = q.find(k);
  return it == q.end() ? def : it->second;
}

Taper taper_by_name(const std::string& s) {
  if (s == "taylor") return Taper::Taylor;
  if (s == "chebyshev") return Taper::Chebyshev;
  if (s == "hann") return Taper::Hann;
  return Taper::Uniform;
}

// Распределение из ключей dpaa_ctl.py: taper, sll, off ("1,3,5" — номера с 1), weights.
Distribution dist_from(const Query& q) {
  Distribution d;
  d.taper = taper_by_name(str(q, "taper", "uniform"));
  d.sll_db = num(q, "sll", 30);
  std::string off = str(q, "off");
  for (size_t i = 0; i < off.size();) {
    size_t j = off.find(',', i);
    if (j == std::string::npos) j = off.size();
    d.off_mask |= 1u << (std::stoi(off.substr(i, j - i)) - 1);
    i = j + 1;
  }
  std::string w = str(q, "weights");
  if (!w.empty()) {
    d.use_weights = true;
    int n = 0;
    for (size_t i = 0; i < w.size() && n < kNElem;) {
      size_t j = w.find(',', i);
      if (j == std::string::npos) j = w.size();
      d.weights[n++] = std::stod(w.substr(i, j - i));
      i = j + 1;
    }
  }
  return d;
}

Source source_from(const Query& q) {
  Source s;
  s.tone_hz = num(q, "tone", 3000);
  if (str(q, "noise") == "1") s.kind = SourceKind::Noise;
  else if (str(q, "chirp") == "1") s.kind = SourceKind::Chirp;
  return s;
}

std::string vec(const Query& q) {
  const std::string t = str(q, "t");
  Frames f;
  char buf[64];
  if (t == "protocol") {
    const int a = int(num(q, "addr", 0));
    const int64_t d = int64_t(num(q, "data", 0));
    return hex(encode_write(a, d)) + " " + hex(encode_read(a));
  }
  if (t == "phase") return std::to_string(phase_inc(num(q, "f", 0)));
  if (t == "gain") return std::to_string(gain_reg(num(q, "x", 0)));
  if (t == "biquad") {
    int32_t c[5];
    biquad_bandpass(num(q, "lo", 0), num(q, "hi", 0), c);
    std::string s;
    for (int i = 0; i < 5; i++) s += (i ? " " : "") + std::to_string(c[i]);
    return s;
  }
  if (t == "window") {
    const int n = int(num(q, "n", 16));
    double w[64];
    taper_window(n, taper_by_name(str(q, "kind")), num(q, "sll", 30), w);
    std::string s;
    for (int i = 0; i < n; i++) {
      std::snprintf(buf, sizeof buf, "%s%.17g", i ? " " : "", w[i]);
      s += buf;
    }
    return s;
  }
  if (t == "delays") {
    Vec3 focus{num(q, "fx", 0), num(q, "fy", 0), num(q, "fz", 0)};
    const Vec3* fp = q.count("fy") ? &focus : nullptr;
    Vec3 pe[kNElem], pm[kNMics];
    element_positions(pe);
    mic_positions(pm);
    double d[kNElem];
    std::string s;
    int32_t r;
    beam_delays(num(q, "az", 0), fp, pe, kNElem, d);
    for (int i = 0; i < kNElem; i++) s += (delay_reg(d[i], r) ? std::to_string(r) : "ERR") + " ";
    s += "|";
    beam_delays(num(q, "az", 0), fp, pm, kNMics, d);
    for (int i = 0; i < kNMics; i++) s += " " + (delay_reg(d[i], r) ? std::to_string(r) : "ERR");
    return s;
  }
  if (t == "gen") {
    const double freq = num(q, "freq", 0);
    const Chirp ch{num(q, "c0", 0), num(q, "c1", 0), num(q, "c2", 0)};
    const Burst bu{num(q, "b0", 0), num(q, "b1", 0)};
    const Band ba{num(q, "lo", 0), num(q, "hi", 0)};
    gen(f, int(num(q, "beam", 0)), GenMode(int(num(q, "mode", 0))), q.count("freq") ? &freq : nullptr,
        num(q, "amp", 0.5), q.count("c0") ? &ch : nullptr, q.count("b0") ? &bu : nullptr,
        q.count("lo") ? &ba : nullptr, num(q, "env", 5.0));
    return hex(f);
  }
  if (t == "scenario") {
    const std::string name = str(q, "name");
    const Distribution d = dist_from(q);
    const double amp = num(q, "amp", 0.25);
    bool ok = true;
    if (name == "beam") ok = scenario_beam(f, source_from(q), num(q, "az", 0), d, amp);
    else if (name == "focus") ok = scenario_focus(f, source_from(q), num(q, "x", 0), num(q, "y", 1), d, amp);
    else if (name == "two")
      ok = scenario_two(f, Source{SourceKind::Tone, num(q, "tone1", 2500)}, num(q, "az1", -35),
                        Source{SourceKind::Chirp, num(q, "tone2", 3500)}, num(q, "az2", 35), d, amp);
    else if (name == "listen") ok = scenario_listen(f, num(q, "left", -30), num(q, "right", 30), d);
    else if (name == "elements") {
      scenario_elements_setup(f, num(q, "tone", 2000), amp);
      for (int e = 0; e < kNElem; e++) scenario_element_step(f, e);
      scenario_mute(f);
    } else if (name == "sweep_setup") ok = scenario_sweep_setup(f, source_from(q), amp);
    else if (name == "sweep_step") ok = scenario_sweep_step(f, num(q, "az", 0), d);
    else return "UNKNOWN";
    return ok ? hex(f) : "ERROR";
  }
  return "UNKNOWN";
}

// Симулятор ПЛИС: образ регистров; уровни микрофонов — свой динамик и зонд на нормали в 2.5 м.
class SimLink : public Link {
 public:
  Frames sent;
  int32_t frames_counter = 0;
  std::map<int, int32_t> regs;

  void send(const Frames& fs) override {
    for (const Frame& f : fs) {
      int a;
      int32_t d;
      bool rd;
      if (decode_request(f.b, a, d, rd) && !rd) regs[a] = d;
      sent.push_back(f);
    }
  }

  bool read(int addr, int32_t& v) override {
    if (addr == kRegId) v = kIdValue;
    else if (addr == kRegFrames) v = (frames_counter += 14648) & 0xFFFFFF;   // ≈ 0.3 с кадров
    else if (addr == kRegCtrl) v = reg(kRegCtrl) & 3;
    else if (addr >= kRegPeak && addr <= kRegPeak + kNMics) v = peak(addr - kRegPeak);
    else v = 0;
    return true;
  }

 private:
  int32_t reg(int a) const {
    auto it = regs.find(a);
    return it == regs.end() ? 0 : it->second;
  }
  static double s18(int32_t v) {
    v &= 0x3FFFF;
    return (v >= 0x20000 ? v - 0x40000 : v) / double(kUnity);
  }
  int32_t peak(int mic) const {
    double level = 3e-4;
    if (reg(kRegCtrl) & 1) {
      Vec3 pos[kNElem];
      element_positions(pos);
      for (int beam = 0; beam < kTxBeams; beam++) {
        const int b = kGenBase[beam];
        if ((reg(b + kGenMode) & 3) == 0) continue;
        const double amp = reg(b + kGenAmp) / double((1 << 17) - 1);
        const uint32_t inc = uint32_t(reg(b + kGenIncLo)) | (uint32_t(reg(b + kGenIncHi)) << 16);
        const double f = (reg(b + kGenMode) & 3) == 1 && inc ? inc / 4294967296.0 * kFs : 3000;
        std::complex<double> s = 0;
        double norm = 0;
        for (int n = 0; n < kNElem; n++) {
          const double g = s18(reg(kTxGain + n * kTxBeams + beam));
          const double tau = (reg(kTxDelay + n * kTxBeams + beam) & 0xFFFF) / double(kPhases) / kFs;
          if (mic == n) level += 0.6 * amp * std::fabs(g);
          const double dx = pos[n].x, dy = 2.5;
          const double r = std::sqrt(dx * dx + dy * dy);
          s += g * std::polar(1.0, -2 * M_PI * f * (tau + r / kSoundSpeed));
          norm += std::fabs(g);
        }
        if (mic == kNMics) level += 0.25 * amp * norm / kNElem * std::abs(s) / std::max(norm, 1e-9);
      }
    }
    return int32_t(std::min(1.0, level) * (1 << 23));
  }
};

int serve() {
  SimLink link;
  Controller c(link);
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.rfind("tick ", 0) == 0) {
      c.tick(uint32_t(std::stoul(line.substr(5))));
    } else {
      const size_t sp = line.find(' ');
      const uint32_t now = uint32_t(std::stoul(line.substr(0, sp)));
      std::string url = line.substr(sp + 1), path = url, qs;
      const size_t qm = url.find('?');
      if (qm != std::string::npos) {
        path = url.substr(0, qm);
        qs = url.substr(qm + 1);
      }
      std::cout << c.handle(path, parse_query(qs), now) << "\n";
    }
    std::cout << "FRAMES " << link.sent.size() << (link.sent.empty() ? "" : " ") << hex(link.sent) << "\n";
    std::cout.flush();
    link.sent.clear();
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  const std::string mode = argc > 1 ? argv[1] : "vec";
  if (mode == "serve") return serve();
  std::string line;
  while (std::getline(std::cin, line)) {
    std::cout << vec(parse_query(line)) << "\n";
    std::cout.flush();
  }
  return 0;
}
