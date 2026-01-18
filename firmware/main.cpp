#include <Arduino.h>
#include <PubSubClient.h>
#include <ESP8266WiFi.h>

// ###### WiFi and MQTT details ######### //
const char * ssid = "DLINK2025";
const char * password = "25071981aAbBcC%.";
const char * mqtt_server = "192.168.1.34";
const int    mqtt_port = 1883;
const char * mqtt_user = "iriia";
const char * mqtt_pass = "0000";
 
WiFiClient espClient;
PubSubClient client(espClient);

 // ##### PIR Sensor and its topic
 #define PIR_PIN 12 // GPIO pin for pir sensor
 #define LED1_PIN 16 // First LED ON/OFF control
 #define LED2_PIN 4 // Second LED, PWM control
 
 #define PIR_TOPIC "home/node1/motion" // MQTT topic to send motion alerts
 #define LED1_TOPIC "home/node1/led1"
 #define LED2_TOPIC "home/node1/led2"

 // PWM brightness levels
 const int brightnessLevels[6] = {0, 15, 55, 100, 170, 250};

 // Handle received MQTT messages
 void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == LED1_TOPIC) {
    if (message == "on") {
      digitalWrite(LED1_PIN, HIGH);
      Serial.println("LED 1 is turned ON.");
    } else if (message == "off") {
      digitalWrite(LED1_PIN, LOW);
      Serial.println("LED 1 is turned OFF.");
    }
  } else if (String(topic) == LED2_TOPIC) {
    int level = message.toInt();
    if (level >= 0 && level <= 5) {
      analogWrite(LED2_PIN, brightnessLevels[level]);
      Serial.print("LED 2 brightness is set to: ");
      Serial.println(level);
    }
  } else {
    Serial.println("Topic does not match !!");
  }
  
 }

 // Timer Variable for motion detection
 unsigned long now = millis();
 unsigned long lastTrig = 0;
 volatile bool motionDetected = false;
 const uint8_t period = 10; // Time in seconds to send "no motion" alert after motion detection.


 // ##### ISR for motion detection ####
 IRAM_ATTR void motion_detection() {
  Serial.println(" Warning: motion was detected !!");
  motionDetected = true;
  lastTrig = millis(); // Captures the time of detection
  String payload = "{\"motion\": \"Motion detected\"}";
  client.publish(PIR_TOPIC, payload.c_str()); 

 }

 
 // ######  Connect to WiFi ######
 void connect_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.print(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi Connected!");
  Serial.println(WiFi.localIP());
 }


 // ###### Reconnect to MQTT Broker  ######
 void mqtt_broker_reconnect() {
  while (!client.connected()) {
    Serial.println(" Attempting MQTT broker cnnection ...");
    if (client.connect("node x", mqtt_user, mqtt_pass)) {
      Serial.println("Connected to MQTT Broker");
      // Subscribe to LED control topics
      client.subscribe(LED1_TOPIC);
      client.subscribe(LED2_TOPIC);
      Serial.println("Subscribed to LED control topics");
    } else {
      Serial.print("failed, rc= ");
      Serial.print(client.state());
      delay(5000);
    }
  }
}



void setup() {
  Serial.begin(115200);

  // Initialize GPIO for PIR sensor and LEDs
  pinMode(PIR_PIN, INPUT);
  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);
  analogWriteRange(255); // set range for PWM

  // connect to WiFi
  connect_wifi();

  // set up the MQTT connection
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  // Attach interrupt for PIR sensor
  attachInterrupt(digitalPinToInterrupt(PIR_PIN), motion_detection, RISING);

}

void loop() {
  if (!client.connected()) {
    mqtt_broker_reconnect();
  }
  client.loop();

  now = millis();

  // Timer logic to send "No motion" alert after the set period
  if (motionDetected && (now - lastTrig > 1000 * period)) {
    Serial.println("No motion detected, sending event to MQTT");
    String payload = "{\"motion\": \"No motion detected\"}";
    client.publish(PIR_TOPIC, payload.c_str());
    motionDetected = false; // Reset motion detection
  }

}