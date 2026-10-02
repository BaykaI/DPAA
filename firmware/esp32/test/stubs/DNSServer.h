#pragma once
#include "Arduino.h"
class DNSServer {
 public:
  bool start(uint16_t, const String&, const IPAddress&) { return true; }
  void processNextRequest() {}
};
