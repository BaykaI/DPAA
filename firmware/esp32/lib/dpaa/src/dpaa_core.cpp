#include "dpaa_core.h"

#include <algorithm>
#include <cfenv>
#include <cmath>
#include <cstdio>

namespace dpaa {

namespace {
constexpr double kPi = 3.14159265358979323846;

uint8_t checksum(const uint8_t* f) {
  uint8_t c = 0x5A;
  for (int i = 1; i < 6; i++) c ^= f[i];
  return c;
}

Frame w(int addr, int64_t data) { return encode_write(addr, data); }
}  // namespace

// ------------------------------------------------------------------ протокол
Frame encode_write(int addr, int64_t data) {
  addr &= 0x7FFF;
  data &= 0xFFFFFF;
  Frame f{};
  f.b[0] = 0xA5;
  f.b[1] = uint8_t(addr >> 8);
  f.b[2] = uint8_t(addr);
  f.b[3] = uint8_t(data >> 16);
  f.b[4] = uint8_t(data >> 8);
  f.b[5] = uint8_t(data);
  f.b[6] = checksum(f.b);
  return f;
}

Frame encode_read(int addr) {
  Frame f = encode_write(addr, 0);
  f.b[1] |= 0x80;
  f.b[6] ^= 0x80;
  return f;
}

Frame encode_response(int addr, int32_t data) {
  Frame f = encode_read(addr);
  f.b[0] = 0x5A;
  f.b[3] = uint8_t(data >> 16);
  f.b[4] = uint8_t(data >> 8);
  f.b[5] = uint8_t(data);
  f.b[6] = checksum(f.b);
  return f;
}

bool decode_response(const uint8_t* f, int& addr, int32_t& data) {
  if (f[0] != 0x5A || checksum(f) != f[6]) return false;
  addr = ((f[1] & 0x7F) << 8) | f[2];
  data = (int32_t(f[3]) << 16) | (int32_t(f[4]) << 8) | f[5];
  return true;
}

bool decode_request(const uint8_t* f, int& addr, int32_t& data, bool& read) {
  if (f[0] != 0xA5 || checksum(f) != f[6]) return false;
  read = (f[1] & 0x80) != 0;
  addr = ((f[1] & 0x7F) << 8) | f[2];
  data = (int32_t(f[3]) << 16) | (int32_t(f[4]) << 8) | f[5];
  return true;
}

std::string hex(const Frame& f) {
  char s[2 * kFrameLen + 1];
  for (int i = 0; i < kFrameLen; i++) std::snprintf(s + 2 * i, 3, "%02x", f.b[i]);
  return std::string(s, 2 * kFrameLen);
}

std::string hex(const Frames& fs) {
  std::string s;
  for (size_t i = 0; i < fs.size(); i++) {
    if (i) s += ' ';
    s += hex(fs[i]);
  }
  return s;
}

// ------------------------------------------------------------------ фиксированная точка
double round_even(double x) {
  // nearbyint в режиме по умолчанию (FE_TONEAREST) округляет половинки к чётному — как numpy
  return std::nearbyint(x);
}

int64_t quantize(double x, int frac, int bits) {
  int64_t q = int64_t(round_even(x * double(int64_t(1) << frac)));
  const int64_t lo = -(int64_t(1) << (bits - 1)), hi = (int64_t(1) << (bits - 1)) - 1;
  return std::min(std::max(q, lo), hi);
}

int32_t gain_reg(double gain) { return int32_t(quantize(gain)); }

bool delay_reg(double samples, int32_t& reg) {
  const int64_t q = int64_t(round_even(samples * kPhases));
  if (q < int64_t(kTapCenter) * kPhases || q >= int64_t(kMaxDelay) * kPhases) return false;
  reg = int32_t(q);
  return true;
}

uint32_t phase_inc(double freq_hz) {
  return uint32_t(int64_t(round_even(freq_hz / kFs * 4294967296.0)) & 0xFFFFFFFF);
}

void biquad_bandpass(double f_lo, double f_hi, int32_t out[5]) {
  // полосовой Баттерворт 1-го порядка, билинейное преобразование с предыскажением (scipy.signal.butter)
  const double k = 4.0;
  const double w1 = k * std::tan(kPi * f_lo / kFs), w2 = k * std::tan(kPi * f_hi / kFs);
  const double bw = w2 - w1, w0sq = w1 * w2;
  const double a0 = k * k + bw * k + w0sq;
  const double c[5] = {bw * k / a0, 0.0, -bw * k / a0, 2 * (w0sq - k * k) / a0, (k * k - bw * k + w0sq) / a0};
  for (int i = 0; i < 5; i++) out[i] = int32_t(quantize(c[i]));
}

// ------------------------------------------------------------------ геометрия
void element_positions(Vec3 out[kNElem]) {
  for (int i = 0; i < kNElem; i++) out[i] = Vec3{(i - (kNElem - 1) / 2.0) * kPitch, 0.0, 0.0};
}

void mic_positions(Vec3 out[kNMics]) {
  element_positions(out);
  for (int i = 0; i < kNMics; i++) out[i].z += kMicOffsetZ;
}

void beam_delays(double az_deg, const Vec3* focus, const Vec3* pos, int n, double out[]) {
  const double az = az_deg * kPi / 180.0;
  const double ux = std::sin(az), uy = std::cos(az), uz = 0.0;
  double mn = 1e300;
  for (int i = 0; i < n; i++) {
    if (focus) {
      const double dx = pos[i].x - focus->x, dy = pos[i].y - focus->y, dz = pos[i].z - focus->z;
      out[i] = -std::sqrt(dx * dx + dy * dy + dz * dz) / kSoundSpeed;
    } else {
      out[i] = (pos[i].x * ux + pos[i].y * uy + pos[i].z * uz) / kSoundSpeed;
    }
    mn = std::min(mn, out[i]);
  }
  for (int i = 0; i < n; i++) out[i] = (out[i] - mn) * kFs + kTapCenter + 1;
}

// ------------------------------------------------------------------ окна (scipy.signal.windows)
namespace {
void taylor(int m, int nbar, double sll, double out[]) {
  const double b = std::pow(10.0, sll / 20);
  const double a = std::acosh(b) / kPi;
  const double s2 = nbar * nbar / (a * a + (nbar - 0.5) * (nbar - 0.5));
  double fm[16];
  for (int mi = 0; mi < nbar - 1; mi++) {
    const double mm = mi + 1, m2 = mm * mm;
    double numer = (mi % 2 == 0) ? 1 : -1;
    for (int j = 1; j < nbar; j++) numer *= 1 - m2 / s2 / (a * a + (j - 0.5) * (j - 0.5));
    double denom = 2;
    for (int j = 1; j < nbar; j++)
      if (j != mi + 1) denom *= 1 - m2 / (double(j) * j);
    fm[mi] = numer / denom;
  }
  for (int n = 0; n < m; n++) {
    double s = 1;
    for (int mi = 0; mi < nbar - 1; mi++) s += 2 * fm[mi] * std::cos(2 * kPi * (mi + 1) * (n - m / 2.0 + 0.5) / m);
    out[n] = s;
  }
}

void chebwin(int m, double at, double out[]) {
  if (m == 1) {
    out[0] = 1;
    return;
  }
  const double order = m - 1.0;
  const double beta = std::cosh(std::acosh(std::pow(10.0, std::fabs(at) / 20)) / order);
  std::vector<double> p(m), re(m);
  for (int k = 0; k < m; k++) {
    const double x = beta * std::cos(kPi * k / m);
    p[k] = x > 1 ? std::cosh(order * std::acosh(x))
         : x < -1 ? (2 * (m % 2) - 1) * std::cosh(order * std::acosh(-x))
                  : std::cos(order * std::acos(x));
  }
  for (int j = 0; j < m; j++) {  // вещественная часть ДПФ (для чётного m — со сдвигом на пол-отсчёта)
    double s = 0;
    for (int k = 0; k < m; k++) s += p[k] * std::cos(-2 * kPi * j * k / m + (m % 2 == 0 ? kPi * k / m : 0));
    re[j] = s;
  }
  int o = 0;
  if (m % 2 == 1) {
    const int h = (m + 1) / 2;
    for (int j = h - 1; j >= 1; j--) out[o++] = re[j];
    for (int j = 0; j < h; j++) out[o++] = re[j];
  } else {
    const int h = m / 2 + 1;
    for (int j = h - 1; j >= 1; j--) out[o++] = re[j];
    for (int j = 1; j < h; j++) out[o++] = re[j];
  }
}
}  // namespace

void taper_window(int n, Taper kind, double sll_db, double out[]) {
  switch (kind) {
    case Taper::Taylor: taylor(n, 4, sll_db, out); break;
    case Taper::Chebyshev: chebwin(n, sll_db, out); break;
    case Taper::Hann:
      for (int k = 0; k < n; k++) out[k] = 0.5 - 0.5 * std::cos(2 * kPi * (k + 1) / (n + 1));
      break;
    default:
      for (int k = 0; k < n; k++) out[k] = 1;
  }
  double mx = out[0];
  for (int k = 1; k < n; k++) mx = std::max(mx, out[k]);
  for (int k = 0; k < n; k++) out[k] /= mx;
}

bool Distribution::element_weights(int n, double out[]) const {
  if (use_weights)
    for (int i = 0; i < n; i++) out[i] = weights[i];
  else
    taper_window(n, taper, sll_db, out);
  double mx = 0;
  for (int i = 0; i < n; i++) {
    if (off_mask & (1u << i)) out[i] = 0;
    mx = std::max(mx, std::fabs(out[i]));
  }
  if (mx == 0) return false;
  for (int i = 0; i < n; i++) out[i] /= mx;
  return true;
}

// ------------------------------------------------------------------ кадры
bool tx_beam(Frames& out, int beam, double az_deg, const Vec3* focus, const double* gains,
             const Distribution* dist, double level) {
  Vec3 pos[kNElem];
  element_positions(pos);
  double d[kNElem], g[kNElem];
  beam_delays(az_deg, focus, pos, kNElem, d);
  if (gains) {
    std::copy(gains, gains + kNElem, g);
  } else {
    Distribution uniform;
    if (!(dist ? *dist : uniform).element_weights(kNElem, g)) return false;
    for (double& v : g) v *= level;
  }
  int32_t reg[kNElem];
  for (int o = 0; o < kNElem; o++)
    if (!delay_reg(d[o], reg[o])) return false;
  for (int o = 0; o < kNElem; o++) {
    const int idx = o * kTxBeams + beam;
    out.push_back(w(kTxDelay + idx, reg[o]));
    out.push_back(w(kTxGain + idx, gain_reg(g[o])));
  }
  return true;
}

bool rx_beam(Frames& out, int output, double az_deg, const Vec3* focus, const double* gains,
             const Distribution* dist) {
  Vec3 pos[kNMics];
  mic_positions(pos);
  double d[kNMics], g[kNMics];
  beam_delays(az_deg, focus, pos, kNMics, d);
  if (gains) {
    std::copy(gains, gains + kNMics, g);
  } else {
    Distribution uniform;
    if (!(dist ? *dist : uniform).element_weights(kNMics, g)) return false;
    double s = 0;  // единичное усиление в направлении луча; для окон Σ|w| = Σw
    for (double v : g) s += std::fabs(v);
    for (double& v : g) v /= s;
  }
  int32_t reg[kNMics];
  for (int i = 0; i < kNMics; i++)
    if (!delay_reg(d[i], reg[i])) return false;
  for (int i = 0; i < kNMics; i++) {
    const int idx = output * kNMics + i;
    out.push_back(w(kRxDelay + idx, reg[i]));
    out.push_back(w(kRxGain + idx, gain_reg(g[i])));
  }
  return true;
}

void gen(Frames& out, int beam, GenMode mode, const double* freq, double amp, const Chirp* chirp,
         const Burst* burst, const Band* band, double env_ms) {
  const int b = kGenBase[beam];
  if (mode == GenMode::Chirp && chirp) {
    const int64_t n = int64_t(round_even(chirp->dur * kFs));
    const int64_t inc0 = phase_inc(chirp->f0);
    const int64_t rate = int64_t(round_even((double(phase_inc(chirp->f1)) - double(inc0)) / double(n)));
    out.push_back(w(b + kGenIncLo, inc0 & 0xFFFF));
    out.push_back(w(b + kGenIncHi, inc0 >> 16));
    out.push_back(w(b + kGenRateLo, rate & 0xFFFF));
    out.push_back(w(b + kGenRateHi, (rate >> 16) & 0xFFFF));
    out.push_back(w(b + kGenChirpLen, n));
  } else if (freq) {
    const int64_t inc = phase_inc(*freq);
    out.push_back(w(b + kGenIncLo, inc & 0xFFFF));
    out.push_back(w(b + kGenIncHi, inc >> 16));
  }
  if (band) {
    int32_t c[5];
    biquad_bandpass(band->lo, band->hi, c);
    const int offs[5] = {kGenB0, kGenB1, kGenB2, kGenA1, kGenA2};
    for (int i = 0; i < 5; i++) out.push_back(w(b + offs[i], c[i]));
    out.push_back(w(b + kGenFilt, 1));
  } else {
    out.push_back(w(b + kGenFilt, 0));
  }
  const double on = burst ? burst->on : 0, per = burst ? burst->period : 0;
  out.push_back(w(b + kGenPeriod, int64_t(round_even(per * kFs))));
  out.push_back(w(b + kGenOnLen, int64_t(round_even(on * kFs))));
  const int64_t step = std::max<int64_t>(1, int64_t(double(1 << 17) / std::max(1.0, env_ms * 1e-3 * kFs)));
  out.push_back(w(b + kGenEnvStep, step));
  out.push_back(w(b + kGenAmp, int64_t(amp * ((1 << 17) - 1))));
  out.push_back(w(b + kGenMode, int(mode)));
}

void source_commands(Frames& out, int beam, const Source& src, double amp) {
  amp = std::min(amp, kMaxAmp);
  if (src.kind == SourceKind::Noise) {
    const Band band{1500, 4300};
    gen(out, beam, GenMode::Noise, nullptr, amp, nullptr, nullptr, &band);
  } else if (src.kind == SourceKind::Chirp) {
    const Chirp ch{2000, 4000, 0.05};
    const Burst bu{0.05, 0.3};
    gen(out, beam, GenMode::Chirp, nullptr, amp, &ch, &bu);
  } else {
    gen(out, beam, GenMode::Sine, &src.tone_hz, amp);
  }
}

Frame ctrl(int value) { return w(kRegCtrl, value); }
Frame commit(bool tx, bool rx) { return w(kRegCommit, (tx ? 1 : 0) | (rx ? 2 : 0)); }

// ------------------------------------------------------------------ сценарии
namespace {
const double kZeros[kNElem] = {};
}

bool scenario_beam(Frames& out, const Source& src, double az, const Distribution& d, double amp) {
  source_commands(out, 0, src, amp);
  gen(out, 1, GenMode::Off, nullptr, 0.5);
  if (!tx_beam(out, 0, az, nullptr, nullptr, &d) || !tx_beam(out, 1, 0, nullptr, kZeros, nullptr)) return false;
  out.push_back(commit());
  out.push_back(ctrl(3));
  return true;
}

bool scenario_focus(Frames& out, const Source& src, double x, double y, const Distribution& d, double amp) {
  source_commands(out, 0, src, amp);
  const Vec3 f{x, y, 0};
  if (!tx_beam(out, 0, 0, &f, nullptr, &d) || !tx_beam(out, 1, 0, nullptr, kZeros, nullptr)) return false;
  out.push_back(commit());
  out.push_back(ctrl(3));
  return true;
}

bool scenario_two(Frames& out, const Source& s1, double az1, const Source& s2, double az2,
                  const Distribution& d, double amp) {
  source_commands(out, 0, s1, amp);
  source_commands(out, 1, s2, amp);
  if (!tx_beam(out, 0, az1, nullptr, nullptr, &d) || !tx_beam(out, 1, az2, nullptr, nullptr, &d)) return false;
  out.push_back(commit());
  out.push_back(ctrl(3));
  return true;
}

bool scenario_sweep_setup(Frames& out, const Source& src, double amp) {
  source_commands(out, 0, src, amp);
  gen(out, 1, GenMode::Off, nullptr, 0.5);
  if (!tx_beam(out, 1, 0, nullptr, kZeros, nullptr)) return false;
  out.push_back(ctrl(3));
  return true;
}

bool scenario_sweep_step(Frames& out, double az, const Distribution& d) {
  if (!tx_beam(out, 0, az, nullptr, nullptr, &d)) return false;
  out.push_back(commit());
  return true;
}

double sweep_angle(double t_sec, double lo, double hi, double period) {
  const double ph = std::fmod(t_sec / period, 1.0);
  return lo + (hi - lo) * (1 - std::fabs(2 * ph - 1));
}

void scenario_elements_setup(Frames& out, double tone_hz, double amp) {
  gen(out, 0, GenMode::Sine, &tone_hz, std::min(amp, kMaxAmp));
  gen(out, 1, GenMode::Off, nullptr, 0.5);
  out.push_back(ctrl(1));
}

void scenario_element_step(Frames& out, int e) {
  double g[kNElem] = {};
  g[e] = 1.0;
  tx_beam(out, 0, 0, nullptr, g, nullptr);
  out.push_back(commit());
}

bool scenario_listen(Frames& out, double left, double right, const Distribution& d) {
  if (!rx_beam(out, 0, left, nullptr, nullptr, &d) || !rx_beam(out, 1, right, nullptr, nullptr, &d)) return false;
  out.push_back(commit(false, true));
  out.push_back(ctrl(2));
  return true;
}

void scenario_mute(Frames& out) { out.push_back(ctrl(0)); }

}  // namespace dpaa
