# 🛰️ Kaset Vision: Autonomous Rice Disease Detection
> **Project by Thasia Electronics** > *Grade 8-9 School Innovation Project (Thailand)*

An integrated IoT system using a **Raspberry Pi 5**, **YOLOv8**, and **Azure Cloud** to detect rice diseases via drone and alert farmers in real-time via the **LINE Messaging API**.

---

## 🏗️ System Architecture
This project uses a **Hybrid Edge-Cloud** architecture to ensure reliability and a permanent connection.

* **Edge (Raspberry Pi 5):** Handles real-time video, YOLOv8 disease inference, and MAVLink drone control.
* **Cloud (Azure App Service):** Hosts the permanent Webhook URL for the LINE Bot bridge.
* **Interface (LINE Bot):** The mobile dashboard for farmers to receive alerts.

## ✨ Key Features
* **Real-time AI Detection:** Custom-trained YOLO model optimized for rice leaf blast and brown spot.
* **Autonomous Grid Mission:** Auto-calculates "lawnmower" flight patterns based on field area (Rai).
* **Permanent Webhook:** Cloud-hosted bridge ensures the farmer never loses connection.
* **Emergency Protocols:** MAVLink-based Emergency Kill switch via LINE command.

## 🛠️ Tech Stack
| Category | Technology |
| :--- | :--- |
| **Languages** | Python 3.13 |
| **AI / Vision** | Ultralytics (YOLOv8), OpenCV (Headless) |
| **Hardware** | Raspberry Pi 5, ArduPilot (F4 V3S), PiCamera2 |
| **Cloud / API** | Microsoft Azure, LINE Messaging API, Flask |

## 🚀 Deployment
### 1. Cloud Setup (Azure)
1. Push the `app.py` and `requirements.txt` to GitHub.
2. Connect GitHub to your **Azure App Service**.
3. Set your `LINE_CHANNEL_SECRET` and `LINE_CHANNEL_ACCESS_TOKEN` in Azure Environment Variables.

### 2. Edge Setup (Raspberry Pi 5)
1. Connect the Pi to the Flight Controller via `/dev/ttyACM0`.
2. Run the local drone server:
   ```bash
   python drone_server.py
