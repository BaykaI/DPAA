#pragma once
#include "Arduino.h"
enum wifi_mode_t { WIFI_OFF, WIFI_STA, WIFI_AP, WIFI_AP_STA };
struct WiFiClass {
  bool mode(wifi_mode_t) { return true; }
  bool softAPConfig(IPAddress, IPAddress, IPAddress) { return true; }
  bool softAP(const char*, const char* = nullptr, int = 1, int = 0, int = 4) { return true; }
  bool setSleep(bool) { return true; }
};
extern WiFiClass WiFi;
