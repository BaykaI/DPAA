#pragma once
#include "Arduino.h"
class Preferences {
 public:
  bool begin(const char*, bool = false) { return true; }
  void end() {}
  float getFloat(const char*, float d = 0) { return d; }
  size_t putFloat(const char*, float) { return 4; }
  bool getBool(const char*, bool d = false) { return d; }
  size_t putBool(const char*, bool) { return 1; }
  uint32_t getUInt(const char*, uint32_t d = 0) { return d; }
  size_t putUInt(const char*, uint32_t) { return 4; }
  String getString(const char*, String d = String()) { return d; }
  size_t putString(const char*, const String&) { return 0; }
};
