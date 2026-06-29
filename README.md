# Project OSCAR 🗑️
**Optimized Smart Collection and Routing — Intelligent Waste Collection System**

A proof-of-concept for demand-driven garbage collection. Instead of trucks driving fixed routes regardless of bin fill level, each bin reports its status in real time and an AR heads-up display lets drivers see fill levels at a glance — without stepping out of the truck.

---

## The Problem

Municipal waste trucks follow fixed routes on fixed schedules. A driver will stop at every bin on the route whether it's empty or completely full. This wastes fuel, driver time, and contributes unnecessary emissions — especially on routes where many bins aren't ready for collection yet.

## The Solution (Two-Part)

### Part 1 — IoT Sensor Network *(designed, partially implemented)*
Each trash bin is equipped with:
- **ESP32** microcontroller with WiFi
- **HC-SR04** ultrasonic sensor measuring fill depth
- **Solar panel + battery** for autonomous power

The ESP32 runs a web server that serves live fill level data as JSON (`/data`). A central system can poll all nodes and build an optimized real-time collection route — only dispatching trucks to bins that actually need emptying.

### Part 2 — AR Truck HUD *(fully implemented)*
A Python + OpenCV application that overlays fill level information directly onto a camera feed using **AprilTag fiducial markers** mounted on each bin.

The driver sees a color-coded 3D prism floating over each bin showing how full it is — green (under 50%), yellow (50–80%), red (over 80%) — plus a city grid sidebar showing dispatch status and estimated truck ETAs.

No phone required to check an app. No radio calls. The information is spatially anchored to the physical bin in the driver's field of view.

---

## Demo

> 📸 *Add photos/video here — see `/assets/`*

---

## Repo Structure

```
project-oscar/
├── firmware/
│   └── IOT_TrashBin.ino       # ESP32 firmware (Arduino IDE)
├── ar-client/
│   ├── supersystem_AR.py      # Full AR HUD with city grid interface
│   └── AR_Trash.py            # Earlier single-bin prototype
├── assets/
│   ├── photos/
│   └── videos/
├── requirements.txt
└── README.md
```

---

## How It Works

### ESP32 Firmware
The firmware takes a 50-sample rolling average of ultrasonic readings (5 seconds of history) to smooth out sensor noise. It converts the raw distance to a fill percentage using two calibration constants:

```
EMPTY_DEPTH_CM = 78   # distance from sensor to empty bin bottom
FULL_OFFSET_CM = 20   # minimum clearance before "full"
```

The `/data` endpoint returns:
```json
{ "distance": 34.2, "percent": 73 }
```

### AR Client
1. Camera feed is captured and each frame is scanned for **AprilTag 36h11** markers (ID 1 = one bin).
2. `cv2.solvePnP` computes the 6-DOF pose of each detected tag.
3. A 3D prism is projected onto the image using the tag's pose, scaled by the live fill percentage from the ESP32.
4. The city grid sidebar shows dispatch status thresholds:
   - **> 90% full** → `DISPATCHED` (truck routed, ETA shown)
   - **> 75% full** → `QUEUED` (pending dispatch)
   - **≤ 75%** → `IDLE`

---

## Setup

### ESP32 Firmware

1. Open `firmware/IOT_TrashBin.ino` in Arduino IDE.
2. Install board support: **ESP32 by Espressif** via Board Manager.
3. Fill in your WiFi credentials:
```cpp
const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
```
4. Adjust calibration for your specific bin:
```cpp
const int EMPTY_DEPTH_CM = 78;  // measure your bin
const int FULL_OFFSET_CM = 20;
```
5. Flash to the ESP32. Note the IP address printed to Serial Monitor.

### AR Client

```bash
git clone https://github.com/Sepu2002/project-oscar.git
cd project-oscar
pip install -r requirements.txt
```

Update the ESP32 IP in `supersystem_AR.py`:
```python
ESP32_IP = "http://YOUR_ESP32_IP"
```

Run:
```bash
python ar-client/supersystem_AR.py
```

> **Note:** `pygrabber` (used for camera listing) is Windows-only. On macOS/Linux, remove the `pygrabber` import and replace `get_available_cameras()` with `cv2.VideoCapture(0)`.

Print an **AprilTag 36h11, ID 1** marker and attach it to the front face of the bin. A 16.5 cm printed tag works at typical truck-cab distances.

---

## Hardware

| Component | Purpose |
|---|---|
| ESP32 (any variant) | WiFi + web server |
| HC-SR04 | Ultrasonic distance sensor |
| Solar panel + LiPo battery | Autonomous power |
| AprilTag (printed) | AR pose anchor |

---

## Known Limitations & Future Work

- **Single-bin demo:** The current implementation tracks one tag (ID 1). A full deployment would assign unique IDs to each bin and aggregate data across a city grid backend.
- **Camera calibration:** Intrinsics are approximated from frame dimensions. Proper calibration would improve pose accuracy at longer distances.
- **Route optimization:** The dispatch logic is simulated. A real system would integrate with a routing API (e.g. Google Maps Routes or OR-Tools).
- **DICOM-style protocol:** Future work could standardize the bin data format and build a city-wide dashboard.

---

## Authors

**Santiago Sepúlveda Landeros** · [GitHub](https://github.com/Sepu2002) · [LinkedIn](https://linkedin.com/in/[yourhandle])

*Mechatronics Engineering — Universidad Panamericana*
