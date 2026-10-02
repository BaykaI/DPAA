#pragma once
#include "Arduino.h"
enum HTTPMethod { HTTP_ANY, HTTP_GET, HTTP_POST };
class WebServer {
 public:
  using THandlerFunction = std::function<void(void)>;
  explicit WebServer(int) {}
  void on(const String&, HTTPMethod, THandlerFunction) {}
  void onNotFound(THandlerFunction) {}
  void begin() {}
  void handleClient() {}
  int args() { return 0; }
  String argName(int) { return String(); }
  String arg(int) { return String(); }
  String arg(const String&) { return String(); }
  String uri() { return String(); }
  void sendHeader(const String&, const String&, bool = false) {}
  void send(int, const char* = nullptr, const String& = String("")) {}
  void send_P(int, PGM_P, PGM_P, size_t) {}
};
