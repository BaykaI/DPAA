#pragma once
#include "Arduino.h"
struct MDNSResponder {
  bool begin(const char*) { return true; }
  void addService(const char*, const char*, uint16_t) {}
};
extern MDNSResponder MDNS;
