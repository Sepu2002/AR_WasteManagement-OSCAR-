
#include <WiFi.h>
#include <WebServer.h>

// ---------------------------------------------------------------- //
//                       CONFIGURATION                              //
// ---------------------------------------------------------------- //

// 1. WiFi Credentials (CHANGE THESE)
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// 2. Hardware Pin Definitions
const int trigPin = 5;  // Connect Sensor TRIG to D5
const int echoPin = 18; // Connect Sensor ECHO to D18

// 3. Calibration (Measure your trashcan!)
// The distance from the sensor (top) to the bottom of the empty can in cm.
const int EMPTY_DEPTH_CM = 78; 
// The distance from the sensor to the "full" line (usually about 5cm from the top).
const int FULL_OFFSET_CM = 20; 

// ---------------------------------------------------------------- //

WebServer server(80);

// Smoothing Settings
const int numReadings = 50;   // Number of samples to keep (50 samples @ 100ms = 5 seconds)
float readings[numReadings];  // Array to store the readings
int readIndex = 0;            // Index of the current reading
float total = 0;              // Running total
float averageDistance = 0;    // The smoothed average

// Variable to store the last valid raw reading
float currentDistance = 0;
int fillPercentage = 0;

// Function to read the HC-SR04 Sensor
float getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // Added timeout (30000us = 30ms) to prevent blocking if sensor disconnects
  long duration = pulseIn(echoPin, HIGH, 30000);
  
  // If timeout (0 duration), return last good value
  if (duration == 0) return currentDistance;

  // Calculate distance in cm (Speed of sound is 0.034 cm/us)
  float distance = duration * 0.034 / 2;
  
  // Filter out crazy readings (sensor glitches)
  if (distance > 400 || distance < 2) {
    return currentDistance; // Return last known good value
  }
  
  currentDistance = distance; // Update last known good
  return distance;
}

// Function to generate the HTML page
String getHTML() {
  String ptr = "<!DOCTYPE html> <html>\n";
  ptr += "<head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, user-scalable=no\">\n";
  ptr += "<title>Smart Trashcan</title>\n";
  ptr += "<style>html { font-family: Helvetica; display: inline-block; margin: 0px auto; text-align: center;}\n";
  ptr += "body{margin-top: 50px;} h1 {color: #444444;margin: 50px auto 30px;} h3 {color: #444444;margin-bottom: 50px;}\n";
  
  // CSS for the Trash Can Graphic
  ptr += ".can-container { width: 150px; height: 300px; border: 5px solid #333; border-radius: 0 0 15px 15px; border-top: none; position: relative; margin: 0 auto; background-color: #f0f0f0; overflow: hidden; }\n";
  // Note: We removed the C++ color logic here because JavaScript will handle it now
  ptr += ".fill-level { width: 100%; position: absolute; bottom: 0; transition: height 0.2s ease; background-color: #4CAF50; }\n";
  ptr += "</style>\n";
  
  // JavaScript to update data without refreshing the page
  ptr += "<script>\n";
  ptr += "setInterval(function() {\n";
  ptr += "  fetch('/data').then(response => response.json()).then(data => {\n";
  ptr += "    document.getElementById('status').innerText = data.percent + '% Full';\n";
  ptr += "    document.getElementById('dist').innerText = 'Distance: ' + data.distance + ' cm';\n";
  ptr += "    var bar = document.getElementById('bar');\n";
  ptr += "    bar.style.height = data.percent + '%';\n";
  ptr += "    // Dynamic Coloring\n";
  ptr += "    if(data.percent > 80) bar.style.backgroundColor = '#F44336';\n"; // Red
  ptr += "    else if(data.percent > 50) bar.style.backgroundColor = '#FFC107';\n"; // Yellow
  ptr += "    else bar.style.backgroundColor = '#4CAF50';\n"; // Green
  ptr += "  });\n";
  ptr += "}, 500);\n"; // Updates every 500 milliseconds (0.5 seconds)
  ptr += "</script>\n";
  
  ptr += "</head>\n";
  ptr += "<body>\n";
  ptr += "<h1>Smart Trashcan</h1>\n";
  
  ptr += "<div class=\"can-container\">\n";
  ptr += "  <div id=\"bar\" class=\"fill-level\"></div>\n";
  ptr += "</div>\n";
  
  ptr += "<h3 id=\"status\">Loading...</h3>\n";
  ptr += "<p id=\"dist\">Waiting for sensor...</p>\n";
  
  ptr += "</body>\n";
  ptr += "</html>\n";
  return ptr;
}

// Serves the HTML file (Only happens once on load)
void handle_OnConnect() {
  server.send(200, "text/html", getHTML()); 
}

// New function: Serves only the JSON data (Happens every 0.5s)
void handle_Data() {
  // Use the SMOOTHED average for the web display
  int trashHeight = EMPTY_DEPTH_CM - averageDistance;
  if(trashHeight < 0) trashHeight = 0;
  
  fillPercentage = (trashHeight * 100) / (EMPTY_DEPTH_CM - FULL_OFFSET_CM);
  
  // Clamp percentage
  if(fillPercentage > 100) fillPercentage = 100;
  if(fillPercentage < 0) fillPercentage = 0;

  // Create JSON string
  String json = "{\"distance\": " + String(averageDistance) + ", \"percent\": " + String(fillPercentage) + "}";
  server.send(200, "application/json", json);
}

void handle_NotFound() {
  server.send(404, "text/plain", "Not found");
}

void setup() {
  Serial.begin(115200);
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  // Initialize smoothing array
  // We pre-fill it with a single reading so the average starts instantly correct
  // rather than ramping up from 0.
  float initialReading = getDistance();
  if (initialReading == 0) initialReading = EMPTY_DEPTH_CM; // Fallback if sensor fails on boot
  
  for (int i = 0; i < numReadings; i++) {
    readings[i] = initialReading;
    total += initialReading;
  }
  averageDistance = initialReading;

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.print("Connected to ");
  Serial.println(ssid);
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  server.on("/", handle_OnConnect);
  server.on("/data", handle_Data); // Route for the background updates
  server.onNotFound(handle_NotFound);

  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  // -------------------------
  // 1. SMOOTHING ALGORITHM
  // -------------------------
  
  // Subtract the last reading
  total = total - readings[readIndex];
  
  // Read from the sensor
  readings[readIndex] = getDistance();
  
  // Add the reading to the total
  total = total + readings[readIndex];
  
  // Advance to the next position in the array
  readIndex = readIndex + 1;

  // If we're at the end of the array...
  if (readIndex >= numReadings) {
    // ...wrap around to the beginning
    readIndex = 0;
  }

  // Calculate the average
  averageDistance = total / numReadings;

  // -------------------------
  // 2. WEB SERVER
  // -------------------------
  server.handleClient();
  
  // -------------------------
  // 3. TIMING
  // -------------------------
  // 100ms delay = 10 readings per second
  // 50 readings total = 5 seconds of data history
  delay(100); 
}