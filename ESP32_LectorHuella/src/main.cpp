/*
  Puente ESP32 <-> AS608 para GestorLocal (WiFi por router + USB).

  Cableado (UART2 de la ESP32):
    AS608 TX  -> GPIO16 (RX2)
    AS608 RX  -> GPIO17 (TX2)
    AS608 VCC -> 3.3V
    AS608 GND -> GND

  Canales: si hay un cliente TCP conectado y autenticado se responde por WiFi;
  si no, por el puerto USB. Mismo protocolo en ambos (texto, una línea por mensaje):
    PC -> ESP32:  AUTH:<clave> (solo WiFi) | PING | ENROLL:<id> | MATCH | CANCEL
    ESP32 -> PC:  OK:AUTH | ERR:AUTH | PONG | PONG:SIN_SENSOR | MSG:<texto>
                  OK:ENROLL:<id> | ERR:ENROLL:<motivo>
                  MATCH:<id>:<confianza> | NOMATCH | OK:MATCH:FIN

  Descubrimiento: el PC envía "HUELLA?" por UDP (broadcast) y la ESP32 responde
  "HUELLA!<puerto>" desde su IP, así el PC la encuentra sin conocer la IP.
*/
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Adafruit_Fingerprint.h>
#include "config.h"

#define SENSOR_RX 16
#define SENSOR_TX 17
#define TIMEOUT_DEDO 15000   // ms esperando que pongan/quiten el dedo

HardwareSerial sensorSerial(2);
Adafruit_Fingerprint finger(&sensorSerial);

WiFiServer servidor(PUERTO_TCP);
WiFiClient cliente;
WiFiUDP udp;
Stream* io = &Serial;            // canal activo (USB o WiFi)
Stream* ioAnterior = &Serial;
bool autenticado = false;
bool redIniciada = false;
unsigned long ultimoIntentoWifi = 0;
String bufferLinea;

// Lee una línea del canal activo sin bloquear. true si llegó una línea completa.
bool leerLinea(String &salida) {
  while (io->available()) {
    char c = io->read();
    if (c == '\n') {
      salida = bufferLinea;
      salida.trim();
      bufferLinea = "";
      return true;
    }
    if (c != '\r') bufferLinea += c;
  }
  return false;
}

// true si el PC pidió cancelar o si se perdió la conexión WiFi.
bool cancelado() {
  if (io != (Stream*)&Serial && !cliente.connected()) return true;
  String l;
  while (leerLinea(l)) {
    if (l == "CANCEL") return true;
  }
  return false;
}

// Espera un dedo y lo convierte en características en el buffer 1 o 2.
const char* capturar(uint8_t buffer) {
  unsigned long t0 = millis();
  while (finger.getImage() != FINGERPRINT_OK) {
    if (cancelado()) return "cancelado";
    if (millis() - t0 > TIMEOUT_DEDO) return "tiempo agotado";
    delay(50);
  }
  if (finger.image2Tz(buffer) != FINGERPRINT_OK) return "imagen de mala calidad, intenta de nuevo";
  return nullptr;
}

const char* esperarSinDedo() {
  unsigned long t0 = millis();
  while (finger.getImage() != FINGERPRINT_NOFINGER) {
    if (cancelado()) return "cancelado";
    if (millis() - t0 > TIMEOUT_DEDO) return "tiempo agotado";
    delay(50);
  }
  return nullptr;
}

void fallo(const char* motivo) {
  io->print("ERR:ENROLL:");
  io->println(motivo);
}

void enrolar(uint8_t id) {
  const char* err;

  io->println("MSG:Coloca el dedo en el lector");
  if ((err = capturar(1))) { fallo(err); return; }

  // Evita que la misma huella quede guardada en dos usuarios distintos
  if (finger.fingerFastSearch() == FINGERPRINT_OK && finger.fingerID != id) {
    fallo("esa huella ya está registrada en otro usuario");
    return;
  }

  io->println("MSG:Retira el dedo");
  if ((err = esperarSinDedo())) { fallo(err); return; }

  io->println("MSG:Coloca el mismo dedo otra vez");
  if ((err = capturar(2))) { fallo(err); return; }

  if (finger.createModel() != FINGERPRINT_OK) { fallo("las dos lecturas no coinciden"); return; }
  if (finger.storeModel(id) != FINGERPRINT_OK) { fallo("no se pudo guardar en el lector"); return; }

  io->print("OK:ENROLL:");
  io->println(id);
}

// Modo asistencia: queda escuchando hasta recibir CANCEL (o perder la conexión).
void emparejar() {
  io->println("MSG:Lector listo. Coloca tu dedo");
  while (true) {
    if (cancelado()) { io->println("OK:MATCH:FIN"); return; }
    if (finger.getImage() != FINGERPRINT_OK) { delay(50); continue; }

    if (finger.image2Tz(1) == FINGERPRINT_OK && finger.fingerFastSearch() == FINGERPRINT_OK) {
      io->print("MATCH:");
      io->print(finger.fingerID);
      io->print(":");
      io->println(finger.confidence);
    } else {
      io->println("NOMATCH");
    }

    // Espera a que retire el dedo antes de volver a leer
    while (finger.getImage() != FINGERPRINT_NOFINGER) {
      if (cancelado()) { io->println("OK:MATCH:FIN"); return; }
      delay(50);
    }
  }
}

// Arranca el servidor TCP y el descubrimiento UDP cuando hay WiFi; reintenta si se cae.
void mantenerWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!redIniciada) {
      servidor.begin();
      udp.begin(PUERTO_DESCUBRIMIENTO);
      redIniciada = true;
      Serial.print("LOG:WiFi conectado. IP: ");
      Serial.println(WiFi.localIP());
    }
  } else if (millis() - ultimoIntentoWifi > 10000) {
    ultimoIntentoWifi = millis();
    Serial.println("LOG:Sin WiFi, reintentando...");
    WiFi.reconnect();
  }
}

// Responde a "HUELLA?" para que el PC encuentre la IP de la ESP32.
void responderDescubrimiento() {
  if (!redIniciada) return;
  if (udp.parsePacket() <= 0) return;
  char buf[16] = {0};
  udp.read(buf, sizeof(buf) - 1);
  if (strcmp(buf, "HUELLA?") == 0) {
    udp.beginPacket(udp.remoteIP(), udp.remotePort());
    udp.print("HUELLA!");
    udp.print(PUERTO_TCP);
    udp.endPacket();
  }
}

void setup() {
  Serial.begin(115200);
  sensorSerial.begin(57600, SERIAL_8N1, SENSOR_RX, SENSOR_TX);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname("lector-huella");
  WiFi.setSleep(false);              // más estable y con menos latencia
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_CLAVE);
  Serial.println("LOG:Conectando al WiFi...");
}

void loop() {
  mantenerWifi();
  responderDescubrimiento();

  // Un cliente nuevo reemplaza al anterior (evita conexiones colgadas)
  if (redIniciada) {
    WiFiClient nuevo = servidor.available();
    if (nuevo) {
      if (cliente) cliente.stop();
      cliente = nuevo;
      autenticado = false;
      bufferLinea = "";
    }
  }

  bool porRed = cliente && cliente.connected();
  io = porRed ? (Stream*)&cliente : (Stream*)&Serial;
  if (io != ioAnterior) { bufferLinea = ""; ioAnterior = io; }

  String l;
  if (!leerLinea(l)) { delay(2); return; }

  // Por WiFi, el primer mensaje debe ser la clave
  if (porRed && !autenticado) {
    if (l == String("AUTH:") + TOKEN_LECTOR) {
      autenticado = true;
      io->println("OK:AUTH");
    } else {
      io->println("ERR:AUTH");
      cliente.stop();
    }
    return;
  }

  if (l == "PING") {
    io->println(finger.verifyPassword() ? "PONG" : "PONG:SIN_SENSOR");
  } else if (l.startsWith("ENROLL:")) {
    int id = l.substring(7).toInt();
    if (id < 1 || id > 127) fallo("ID fuera de rango");
    else enrolar((uint8_t)id);
  } else if (l == "MATCH") {
    emparejar();
  }
}