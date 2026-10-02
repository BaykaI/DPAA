// Ядро управления акустической ЦАФАР: протокол UART, форматы регистров ПЛИС,
// задержки лучей, амплитудные распределения и сценарии.
//
// Перенос dpaa/hw.py и tools/dpaa_ctl.py на C++17 без зависимостей от Arduino:
// тот же код собирается для ESP32-S3 и на компьютере (test/host), где кадры сверяются
// с Python-моделью бит в бит (tests/test_esp32.py).
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace dpaa {

// --- тактирование и решётка ---
constexpr double kFClk = 50000000.0;        // системная частота ПЛИС
constexpr int kFrameClks = 1024;            // 64 такта BCLK на кадр I2S
constexpr double kFs = kFClk / kFrameClks;  // 48 828.125 Гц
constexpr double kSoundSpeed = 343.0;       // м/с
constexpr int kNElem = 16;
constexpr int kNMics = 16;
constexpr double kPitch = 0.04;             // шаг решётки 40 мм
constexpr double kMicOffsetZ = 0.0298;      // микрофон выше центра динамика

// --- ядро дробной задержки ---
constexpr int kW = 18;
constexpr int kTaps = 8;
constexpr int kTapCenter = 3;
constexpr int kPhaseBits = 5;
constexpr int kPhases = 1 << kPhaseBits;
constexpr int kCoefFrac = 16;
constexpr int kDepth = 256;
constexpr int kMaxDelay = kDepth - kTaps;
constexpr int kUnity = 1 << kCoefFrac;

// --- карта регистров ---
constexpr int kRegId = 0x0000;
constexpr int kRegFrames = 0x0001;
constexpr int kRegCtrl = 0x0002;
constexpr int kRegCommit = 0x0003;
constexpr int kGenBase[2] = {0x0010, 0x0020};
constexpr int kRegPeak = 0x0100;
constexpr int kTxDelay = 0x1000, kTxGain = 0x1080;
constexpr int kRxDelay = 0x2000, kRxGain = 0x2080;
constexpr int32_t kIdValue = 0xDAA001;
constexpr int kTxBeams = 2;

enum GenReg {
  kGenMode = 0, kGenIncLo, kGenIncHi, kGenAmp, kGenRateLo, kGenRateHi, kGenChirpLen, kGenPeriod,
  kGenOnLen, kGenEnvStep, kGenB0, kGenB1, kGenB2, kGenA1, kGenA2, kGenFilt
};
enum class GenMode { Off = 0, Sine = 1, Noise = 2, Chirp = 3 };

constexpr double kMaxAmp = 0.5;   // потолок громкости генератора (как MAX_AMP в dpaa_ctl.py)
constexpr double kTxLevel = 0.5;  // максимальный вес элемента на передачу

// --- протокол UART: A5 A1 A0 D2 D1 D0 CHK, ответ 5A A1 A0 D2 D1 D0 CHK ---
constexpr int kFrameLen = 7;
struct Frame {
  uint8_t b[kFrameLen];
};
using Frames = std::vector<Frame>;

Frame encode_write(int addr, int64_t data);
Frame encode_read(int addr);
Frame encode_response(int addr, int32_t data);  // так отвечает ПЛИС (для симулятора)
bool decode_response(const uint8_t* f, int& addr, int32_t& data);
bool decode_request(const uint8_t* f, int& addr, int32_t& data, bool& read);
std::string hex(const Frame& f);
std::string hex(const Frames& fs);  // кадры через пробел

// --- фиксированная точка и форматы регистров ---
double round_even(double x);  // половинки — к чётному, как numpy.round
int64_t quantize(double x, int frac = kCoefFrac, int bits = kW);
int32_t gain_reg(double gain);
bool delay_reg(double samples, int32_t& reg);  // false — вне диапазона [3, 248) отсчётов
uint32_t phase_inc(double freq_hz);
void biquad_bandpass(double f_lo, double f_hi, int32_t out[5]);

// --- геометрия ---
struct Vec3 {
  double x = 0, y = 0, z = 0;
};
void element_positions(Vec3 out[kNElem]);
void mic_positions(Vec3 out[kNMics]);
// Задержки луча в отсчётах (минимальная = 4): на азимут az (focus == nullptr) или в точку focus.
void beam_delays(double az_deg, const Vec3* focus, const Vec3* pos, int n, double out[]);

// --- амплитудное распределение ---
enum class Taper { Uniform = 0, Taylor = 1, Chebyshev = 2, Hann = 3 };
void taper_window(int n, Taper kind, double sll_db, double out[]);

struct Distribution {
  Taper taper = Taper::Uniform;
  double sll_db = 30;
  bool use_weights = false;   // свои веса (могут быть отрицательными)
  double weights[kNElem] = {};
  uint32_t off_mask = 0;      // бит i = 1 — элемент i выключен
  // Нормированные веса (max |w| = 1). false — все элементы выключены.
  bool element_weights(int n, double out[]) const;
};

// --- сигнал генератора ---
enum class SourceKind { Tone = 0, Noise = 1, Chirp = 2 };
struct Source {
  SourceKind kind = SourceKind::Tone;
  double tone_hz = 3000;
};

// --- кадры: таблицы лучей и генераторы (функции hw.py); false — задержка вне диапазона ---
bool tx_beam(Frames& out, int beam, double az_deg, const Vec3* focus, const double* gains,
             const Distribution* dist, double level = kTxLevel);
bool rx_beam(Frames& out, int output, double az_deg, const Vec3* focus, const double* gains,
             const Distribution* dist);
struct Chirp {
  double f0, f1, dur;
};
struct Burst {
  double on, period;
};
struct Band {
  double lo, hi;
};
void gen(Frames& out, int beam, GenMode mode, const double* freq, double amp, const Chirp* chirp = nullptr,
         const Burst* burst = nullptr, const Band* band = nullptr, double env_ms = 5.0);
void source_commands(Frames& out, int beam, const Source& src, double amp);
Frame ctrl(int value);
Frame commit(bool tx = true, bool rx = false);

// --- сценарии (кадр в кадр как tools/dpaa_ctl.py); false — ошибка параметров ---
bool scenario_beam(Frames& out, const Source& src, double az, const Distribution& d, double amp);
bool scenario_focus(Frames& out, const Source& src, double x, double y, const Distribution& d, double amp);
bool scenario_two(Frames& out, const Source& s1, double az1, const Source& s2, double az2,
                  const Distribution& d, double amp);
bool scenario_sweep_setup(Frames& out, const Source& src, double amp);
bool scenario_sweep_step(Frames& out, double az, const Distribution& d);
double sweep_angle(double t_sec, double lo, double hi, double period);
void scenario_elements_setup(Frames& out, double tone_hz, double amp);
void scenario_element_step(Frames& out, int e);
bool scenario_listen(Frames& out, double left, double right, const Distribution& d);
void scenario_mute(Frames& out);

}  // namespace dpaa
