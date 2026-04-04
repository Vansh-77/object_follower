#include <Arduino.h>
#include <WiFi.h>
#include <AsyncUDP.h>
#include <ArduinoJson.h>

// ---------------- WiFi ----------------
const char* SSID     = "Vanshh";
const char* PASSWORD = "x36tjbzq";

// ---------------- Motor Pins ----------------
#define PWM_M1  14
#define IN1_M1  27
#define IN2_M1  26
#define PWM_M2  25
#define IN1_M2  33
#define IN2_M2  32

// ---------------- PWM Config ----------------
#define PWM_FREQ  1200
#define PWM_RES   8

// ---------------- UDP ----------------
#define PORT 5005
AsyncUDP udp;

// ---------------- State ----------------
float vx = 0, omega = 0;
unsigned long last_cmd_time = 0;
const unsigned long FAILSAFE_MS = 500;

// ---------------- Motor Control ----------------
void motor(int pwm_pin, int in1, int in2, float speed) {
    speed = constrain(speed, -15.0, 15.0);
    int duty = (int)(abs(speed) / 100.0 * 255);
    duty = constrain(duty, 0, 255);

    if (speed > 0) {
        digitalWrite(in1, HIGH);
        digitalWrite(in2, LOW);
    } else if (speed < 0) {
        digitalWrite(in1, LOW);
        digitalWrite(in2, HIGH);
    } else {
        digitalWrite(in1, LOW);
        digitalWrite(in2, LOW);
        duty = 0;
    }
    ledcWrite(pwm_pin, duty);  // ✅ pin directly in core 3.x
}

void control_bot(float vx, float omega) {
    float left  = (vx - omega) * 1.25;
    float right = (vx + omega);
    left  = constrain(left,  -15.0, 15.0);
    right = constrain(right, -15.0, 15.0);
    if (abs(left)  < 1) left  = 0;
    if (abs(right) < 1) right = 0;
    motor(PWM_M1, IN1_M1, IN2_M1, left);
    motor(PWM_M2, IN1_M2, IN2_M2, right);
}

void stop_all() {
    motor(PWM_M1, IN1_M1, IN2_M1, 0);
    motor(PWM_M2, IN1_M2, IN2_M2, 0);
}

// ---------------- Setup ----------------
void setup() {
    Serial.begin(115200);

    pinMode(IN1_M1, OUTPUT); pinMode(IN2_M1, OUTPUT);
    pinMode(IN1_M2, OUTPUT); pinMode(IN2_M2, OUTPUT);

    // ✅ New core 3.x API — attach pin directly
    ledcAttach(PWM_M1, PWM_FREQ, PWM_RES);
    ledcAttach(PWM_M2, PWM_FREQ, PWM_RES);

    stop_all();

    WiFi.begin(SSID, PASSWORD);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nConnected! IP: " + WiFi.localIP().toString());

    if (udp.listen(PORT)) {
        Serial.println("Listening on UDP port " + String(PORT));
        udp.onPacket([](AsyncUDPPacket packet) {
            StaticJsonDocument<128> doc;
            DeserializationError err = deserializeJson(doc, packet.data(), packet.length());
            if (err) return;
            vx    = doc["linear"]  | 0.0f;
            omega = doc["angular"] | 0.0f;
            last_cmd_time = millis();
            Serial.printf("vx: %.2f  omega: %.2f\n", vx, omega);
        });
    }
}

// ---------------- Loop ----------------
void loop() {
    if (millis() - last_cmd_time > FAILSAFE_MS) {
        stop_all();
        return;
    }
    control_bot(vx, omega);
}