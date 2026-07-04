// Representative circuit: Work Room 1 (2 fans + 3 lights)
// This sketch reads the sensed on/off state of each device from a switch
// (standing in for a relay status line / current-sensor trip in a real
// deployment) and mirrors it onto an LED (visual confirmation that the
// ESP32 read the state correctly).
//
// In a real deployment, the block marked "SEND TO BACKEND" below would
// send this same state over WiFi (HTTP POST or MQTT) to the backend API
// instead of printing to Serial.

// Lights
const int LIGHT1_SWITCH = 13, LIGHT1_LED = 14;
const int LIGHT2_SWITCH = 16, LIGHT2_LED = 17;
const int LIGHT3_SWITCH = 18, LIGHT3_LED = 19;
// Fans
const int FAN1_SWITCH = 21, FAN1_LED = 22;
const int FAN2_SWITCH = 23, FAN2_LED = 25;

void setup() {
  Serial.begin(115200);

  pinMode(LIGHT1_SWITCH, INPUT);
  pinMode(LIGHT2_SWITCH, INPUT);
  pinMode(LIGHT3_SWITCH, INPUT);
  pinMode(FAN1_SWITCH, INPUT);
  pinMode(FAN2_SWITCH, INPUT);

  pinMode(LIGHT1_LED, OUTPUT);
  pinMode(LIGHT2_LED, OUTPUT);
  pinMode(LIGHT3_LED, OUTPUT);
  pinMode(FAN1_LED, OUTPUT);
  pinMode(FAN2_LED, OUTPUT);
}

void loop() {
  bool light1 = digitalRead(LIGHT1_SWITCH);
  bool light2 = digitalRead(LIGHT2_SWITCH);
  bool light3 = digitalRead(LIGHT3_SWITCH);
  bool fan1   = digitalRead(FAN1_SWITCH);
  bool fan2   = digitalRead(FAN2_SWITCH);

  digitalWrite(LIGHT1_LED, light1);
  digitalWrite(LIGHT2_LED, light2);
  digitalWrite(LIGHT3_LED, light3);
  digitalWrite(FAN1_LED, fan1);
  digitalWrite(FAN2_LED, fan2);

  // SEND TO BACKEND (real deployment): replace this Serial line with an
  // HTTP POST of the same five booleans to the backend's device-state
  // endpoint, tagged with room="Work Room 1".
  Serial.printf("Light1:%d Light2:%d Light3:%d Fan1:%d Fan2:%d\n",
                light1, light2, light3, fan1, fan2);

  delay(200);
}
