// Заглушки Arduino-ESP32 — только для проверки компиляции src/main.cpp на компьютере
// (tests/test_esp32.py). Сигнатуры повторяют arduino-esp32 2.0.x; настоящая сборка — PlatformIO.
#pragma once
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <string>

typedef const char* PGM_P;
#define SERIAL_8N1 0x800001c

class String {
 public:
  String(const char* s = "") : s_(s) {}
  String(const std::string& s) : s_(s) {}
  const char* c_str() const { return s_.c_str(); }
  unsigned int length() const { return unsigned(s_.size()); }
  String operator+(const char* o) const { return String(s_ + o); }
  friend String operator+(const String& a, const String& b) { return String(a.s_ + b.s_); }
 private:
  std::string s_;
};

class IPAddress {
 public:
  IPAddress(uint8_t, uint8_t, uint8_t, uint8_t) {}
  String toString() const { return String("192.168.4.1"); }
};

class HardwareSerial {
 public:
  void begin(unsigned long, uint32_t = SERIAL_8N1, int8_t = -1, int8_t = -1) {}
  size_t setRxBufferSize(size_t n) { return n; }
  size_t setTxBufferSize(size_t n) { return n; }
  size_t write(const uint8_t*, size_t n) { return n; }
  int available() { return 0; }
  int read() { return -1; }
  size_t printf(const char*, ...) { return 0; }
};
extern HardwareSerial Serial, Serial1;

struct EspClass {
  void restart() {}
};
extern EspClass ESP;

unsigned long millis();
unsigned long micros();
void delay(uint32_t);
