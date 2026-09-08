# Solar-Powered Smart Mini Cold Storage System (NER)
### Decentralized Post-Harvest Cold-Chain Platform for the North Eastern Region

An end-to-end, IoT-enabled, solar-powered decentralized cold storage monitoring and spoilage prevention platform engineered specifically for rural, remote, and off-grid farming clusters in the North Eastern Region (NER) of India.

The system integrates real-time psychrometric physics, multi-sensor IoT spatial telemetry, solar/battery autonomy tracking, Machine Learning-driven spoilage risk assessment, automated farmer cellular alerts (SMS/WhatsApp), and real-time WebSocket dashboards to dramatically reduce post-harvest losses for perishable horticultural produce.

---

## 📐 System Architecture

```mermaid
flowchart TD
    subgraph Edge_IoT["📡 IoT Edge & Sensing Layer (ESP32 / LoRa / Simulators)"]
        Sensors["Multi-Probe Temp Sensors (5-Point Array)<br/>Surface Temp Probe<br/>SCD40 CO₂ / VOC Sensors<br/>Light / Door Hall Sensor"]
        SolarEdge["Solar MPPT Controller & Battery BMS<br/>(PV Watts, Battery Voltage, SoC %)"]
    end

    subgraph Backend_Layer["⚡ FastAPI High-Performance Backend Core"]
        Ingest["/api/v1/telemetry/ingest<br/>(Deduplicated Ingestion Engine)"]
        
        subgraph RealTime_Physics["🌡️ Physics & Solar Energy Engine"]
            Psychro["Psychrometrics Engine<br/>(Dew Point, VPD, Condensation Margin)"]
            PowerService["Solar Power Engine<br/>(Power Source Classifier & Battery Autonomy)"]
            Watchdog["Active Watchdog Service<br/>(Heartbeat Monitor & Outage Detector)"]
        end

        subgraph ML_Intelligence["🧠 AI/ML Spoilage Guardian"]
            MLEngine["Crop Respiration & Thermal Stress Model<br/>(Quality Status, Spoilage Risk %, Shelf Life)"]
            ThresholdEngine["Dynamic NER Safety Evaluator<br/>(Chilling Injury & Freezing Protection)"]
        end

        subgraph DualTier_Storage["💾 High-Throughput Data Layer"]
            PostgreSQL[("🐘 PostgreSQL 16<br/>System of Record & Wide Telemetry Frames")]
            Redis[("⚡ Redis In-Memory Cache<br/>Live Metrics, Pub/Sub & Lock Debouncer")]
        end

        subgraph Alert_Dispatch["📲 Notification & Live Streaming"]
            AlertService["Alert Orchestrator<br/>(5-min Redis NX Debounce Window)"]
            SMSChef["SMS Chef Cellular Gateway / Simulator<br/>(Direct SMS to Registered Farmers)"]
            WSManager["WebSocket Connection Manager<br/>(/ws & /ws/{zone_id})"]
        end
    end

    subgraph Client_Layer["🖥️ Frontend & Farmer Interface"]
        WebDashboard["React + Vite Real-time Dashboard<br/>(Live Gauges, Solar Metrics, Psychrometric Charts)"]
        FarmerPhone["Farmer Mobile Phone<br/>(Instant SMS / WhatsApp Critical Alerts)"]
    end

    %% Data Pipeline
    Sensors -->|HTTP JSON / Replay Packets| Ingest
    SolarEdge -->|Solar & Battery Telemetry| Ingest

    Ingest --> Psychro
    Ingest --> PowerService
    Ingest --> MLEngine
    Ingest --> ThresholdEngine

    ThresholdEngine --> AlertService
    AlertService --> SMSChef
    SMSChef -->|Cellular Network| FarmerPhone

    Ingest -->|Persist Frame & Sensor Logs| PostgreSQL
    Ingest -->|Sub-millisecond Cache & Pub/Sub| Redis
    
    Ingest --> WSManager
    WSManager -->|Live Telemetry Stream| WebDashboard
    WebDashboard -->|REST APIs| Backend_Layer
```

---

## 🌟 Core Backend Capabilities

### 1. 🌿 Science-Backed NER Horticultural Crop Profiles
Configured according to ICAR (Indian Council of Agricultural Research) & USDA standards for 8 major North Eastern produce varieties:
- **Leafy vegetables & Brassicas**: Cabbage, Leafy greens (Mustard greens, Spinach, Coriander).
- **Temperate & Sub-tropical Perishables**: French bean, Tomato, Khasi mandarin, Green chilli, Pineapple, Fresh Ginger.
- Dynamic enforcement of **Chilling Injury Floors** (e.g. French bean $\ge 5.0^\circ\text{C}$, Tomato $\ge 10.0^\circ\text{C}$) and **Freezing Points** (e.g. Cabbage $-0.9^\circ\text{C}$).

### 2. 🔬 Real-Time Psychrometric Physics Engine
Calculates ambient moisture thermodynamics on every incoming sensor frame:
- **Dew Point ($T_d$)**: Magnus-Tetens approximation.
- **Condensation Margin**: $T_{\text{surface}} - T_{\text{dewpoint}}$ (Flags moisture condensation risks before mold & rot develop).
- **Vapor Pressure Deficit ($\text{VPD}$)**: In $\text{kPa}$, tracking transpiration stress.
- **Absolute Humidity**: Water vapor content in $\text{g/m}^3$.
- **Thermal Stratification**: Spatial gradient $\Delta T = \max(T_{\text{probes}}) - \min(T_{\text{probes}})$ across multi-point sensor probes.

### 3. ☀️ Solar PV & Battery Autonomy Tracking
- Detects and classifies power sources: `SOLAR` (PV-powered cooling), `BATTERY` (night/overcast operation), or `GRID`.
- Real-time **Battery Autonomy Hours** estimation:
  $$\text{Autonomy Hours} = \frac{\text{Battery SoC \%} \times \text{Nominal Capacity (kWh)}}{\text{Active Cooling Load (kW)}}$$
- Automatic critical alerts when battery SoC drops below safety threshold during extended monsoon cloud cover.

### 4. 🐕 Active Node & Power Watchdog
- Background asyncio worker monitoring IoT node heartbeats.
- Detects sudden power dropouts (`POWER_FAILURE`) or edge node connectivity loss (`NODE_OFFLINE`), immediately notifying the facility operator.

### 5. 🤖 AI/ML Spoilage Guardian
- Predicts produce quality (`Good` / `Bad`), continuous **Spoilage Risk Percentage** ($0-100\%$), and dynamic **Remaining Shelf Life (Days)**.
- Provides actionable mitigation recommendations (e.g., adjust cooling setpoints, open ventilation scrubbers to flush ethylene/$\text{CO}_2$).

### 6. 📱 Instant Cellular Farmer Alerts (SMS Chef Gateway)
- Dispatches direct SMS to registered farmers when safe storage parameters are violated.
- Integrated **Redis distributed lock debouncing (`SET NX EX`)** prevents duplicate alert spamming during ongoing emergencies.
- Built-in graceful simulation fallback when live cellular hardware is offline.

---

## 🗂️ Backend Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── alerts.py           # Active, historical & acknowledgement alert endpoints
│   │   │   ├── analytics.py        # Spoilage distribution & crop health analytics
│   │   │   ├── api_router.py       # Master v1 API router aggregator
│   │   │   ├── dashboard.py       # Overview metrics & live chamber state endpoints
│   │   │   ├── devices.py          # Edge IoT device fleet tracking & health status
│   │   │   ├── farmers.py         # Farmer directory & crop batch allocations
│   │   │   ├── sensors.py         # Sensor configurations, channel metadata & logs
│   │   │   ├── telemetry.py       # Live & bulk idempotent IoT telemetry ingestion
│   │   │   └── zones.py           # Cold storage chambers, setpoints, mode & crop switching
│   │   └── websocket.py           # Live WebSocket stream broker (/ws & /ws/{zone_id})
│   ├── core/
│   │   ├── config.py              # Environment variables, Redis/PostgreSQL URL parsing
│   │   ├── security.py            # Device API key verification dependencies
│   │   └── websocket_manager.py   # Connection pool & multi-channel broadcast manager
│   ├── db/
│   │   ├── database.py            # SQLAlchemy 2.0 async engine & sessionmaker
│   │   └── init_db.py             # Additive migrations & NER seed data initialization
│   ├── models/                    # Database ORM Models (PostgreSQL / SQLite)
│   │   ├── alert.py               # Alerts & AlertNotification models
│   │   ├── cold_storage.py        # ColdStorage facility & Zone models
│   │   ├── crop_batch.py          # Farmer produce batch tracking
│   │   ├── device.py              # IoT device hardware registry & online status
│   │   ├── sensor.py              # Sensor channel metadata model
│   │   ├── telemetry.py           # Wide TelemetryFrame & SensorTelemetryLog models
│   │   └── user.py                # Farmer & Operator profile model
│   ├── schemas/                   # Pydantic validation & OpenAPI request/response models
│   │   ├── alert.py
│   │   ├── dashboard.py
│   │   ├── farmer.py
│   │   ├── ml.py
│   │   ├── sensor.py
│   │   ├── telemetry.py
│   │   └── zone.py
│   ├── services/
│   │   ├── alert_service.py       # Safety threshold evaluation & debounced dispatch
│   │   ├── cache_service.py       # Redis cache, Pub/Sub & distributed locking
│   │   ├── ml_service.py          # Machine learning spoilage risk & shelf-life engine
│   │   ├── power_service.py       # Solar power source & battery autonomy calculator
│   │   ├── psychrometrics.py      # Dew point, VPD, condensation margin & humidity physics
│   │   ├── smschef_service.py     # SMS Chef cellular gateway integration
│   │   ├── telemetry_service.py   # Telemetry ingestion, deduplication & zone resolution
│   │   └── watchdog_service.py    # Background heartbeat & power cut watchdog
│   └── main.py                    # FastAPI application initialization & lifespan lifecycle
├── simulate_iot.py                 # Live multi-chamber IoT sensor telemetry simulator
├── test_backend.py                # Comprehensive automated backend validation suite
├── requirements.txt               # Backend Python dependencies
├── .env                           # Environment configuration
└── README.md                      # Backend specific documentation
```

---

## 🔌 API Endpoint Reference

Interactive documentation is available at **`http://localhost:8000/docs`** (Swagger UI) and **`http://localhost:8000/redoc`** (ReDoc).

### Endpoints Overview

| Category | Method | Endpoint | Description |
| :--- | :---: | :--- | :--- |
| **System** | `GET` | `/health` | Application health and service status |
| **System** | `GET` | `/docs` | Interactive Swagger API explorer |
| **IoT Telemetry** | `POST` | `/api/v1/telemetry/ingest` | Ingest live multi-sensor / solar frame (Idempotent) |
| **IoT Telemetry** | `POST` | `/api/v1/telemetry/bulk` | Ingest buffered batch frames with replay deduplication |
| **Chambers (Zones)** | `GET` | `/api/v1/zones` | List all cold storage chambers with NER thresholds |
| **Chambers (Zones)** | `GET` | `/api/v1/zones/{id}` | Get specific chamber parameters and bounds |
| **Chambers (Zones)** | `POST` | `/api/v1/zones/{id}/setpoint` | Update chamber target temperature & humidity |
| **Chambers (Zones)** | `POST` | `/api/v1/zones/{id}/mode` | Switch operational mode (`AUTO`, `ECO`, `BOOST`, `OFF`) |
| **Chambers (Zones)** | `POST` | `/api/v1/zones/{id}/crop` | Dynamically switch crop & update safe thresholds |
| **Device Fleet** | `GET` | `/api/v1/devices` | List registered IoT hardware nodes & online status |
| **Device Fleet** | `GET` | `/api/v1/devices/{id}/health`| Get battery SoC, signal RSSI & firmware health |
| **Dashboard** | `GET` | `/api/v1/dashboard/summary` | Aggregate metrics (occupancy, active alerts, health) |
| **Dashboard** | `GET` | `/api/v1/dashboard/zones/{id}/live` | Real-time chamber metrics, ML risk & solar power |
| **Dashboard** | `GET` | `/api/v1/dashboard/zones/{id}/history`| Historical time-series telemetry for charting |
| **Alerts** | `GET` | `/api/v1/alerts/active` | List unacknowledged emergency alerts |
| **Alerts** | `GET` | `/api/v1/alerts/history` | Historical audit log of all triggered alerts |
| **Alerts** | `PATCH`| `/api/v1/alerts/{id}/acknowledge`| Acknowledge / resolve an active alert |
| **Farmers** | `GET` | `/api/v1/farmers` | List registered farmers & contact channels |
| **Farmers** | `GET` | `/api/v1/farmers/{id}/batches` | Get crop batches stored by a farmer |
| **WebSockets** | `WS` | `/ws` | Real-time bi-directional telemetry broadcast stream |
| **WebSockets** | `WS` | `/ws/{zone_id}` | Real-time stream filtered to a specific chamber |

---

## 📊 NER Crop Safety Rules Matrix

Storage limits enforced in [`config/storage_rules.yml`](file:///d:/Hackathon_2026/config/storage_rules.yml):

| Crop Variety | Safe Temp Range | Chilling Floor | Freezing Pt | Safe RH Range | Max $\text{CO}_2$ | Shelf Life |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Cabbage** | $0.0^\circ\text{C} - 2.0^\circ\text{C}$ | $0.0^\circ\text{C}$ | $-0.9^\circ\text{C}$ | $95\% - 100\%$ | $5,000\text{ ppm}$ | 90–180 days |
| **Leafy greens** | $0.0^\circ\text{C} - 2.0^\circ\text{C}$ | $-0.4^\circ\text{C}$ | $-0.4^\circ\text{C}$ | $95\% - 100\%$ | $3,000\text{ ppm}$ | 10–21 days |
| **French bean** | $5.0^\circ\text{C} - 7.5^\circ\text{C}$ | $5.0^\circ\text{C}$ | $0.0^\circ\text{C}$ | $92\% - 97\%$ | $4,000\text{ ppm}$ | 14–21 days |
| **Tomato (Mature Green)**| $12.5^\circ\text{C} - 15.0^\circ\text{C}$ | $10.0^\circ\text{C}$ | $0.0^\circ\text{C}$ | $90\% - 95\%$ | $5,000\text{ ppm}$ | 14–28 days |
| **Khasi mandarin** | $4.0^\circ\text{C} - 7.0^\circ\text{C}$ | $3.0^\circ\text{C}$ | $-1.1^\circ\text{C}$ | $85\% - 92\%$ | $4,000\text{ ppm}$ | 30–60 days |
| **Green chilli** | $7.0^\circ\text{C} - 10.0^\circ\text{C}$ | $6.0^\circ\text{C}$ | $-0.7^\circ\text{C}$ | $90\% - 95\%$ | $4,000\text{ ppm}$ | 20–30 days |
| **Pineapple (Kew)** | $8.0^\circ\text{C} - 12.0^\circ\text{C}$ | $7.0^\circ\text{C}$ | $-1.1^\circ\text{C}$ | $85\% - 92\%$ | $5,000\text{ ppm}$ | 14–28 days |
| **Ginger (Fresh)** | $12.0^\circ\text{C} - 14.0^\circ\text{C}$ | $10.0^\circ\text{C}$ | $-1.0^\circ\text{C}$ | $85\% - 90\%$ | $4,000\text{ ppm}$ | 60–150 days |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.11+**
- **PostgreSQL 16** & **Redis** (running in Docker or local VM)
- **Virtual Environment**

---

### 2. Environment Configuration (`backend/.env`)

Configure your database and Redis connection in [`backend/.env`](file:///d:/Hackathon_2026/backend/.env):

```env
# PostgreSQL Connection URL (URL-encode special characters e.g. @ -> %40)
DATABASE_URL=postgresql+asyncpg://postgres:Password%40123%21@192.168.16.128:5432/coldstorage_db

# Redis In-Memory Live Cache & Pub/Sub
REDIS_URL=redis://192.168.16.128:6379/0
ENABLE_REDIS=true

# Optional SMS Chef Gateway (Logs rich alerts to console if left empty)
SMSCHEF_API_URL=https://www.cloud.smschef.com/api/send/sms
SMSCHEF_API_KEY=your_api_key
SMSCHEF_DEVICE_ID=your_device_id
SMSCHEF_SIM_SLOT=1
```

---

### 3. Run Backend Verification Suite

Run the automated test suite to verify database migrations, psychrometric formulas, solar autonomy calculations, ML predictions, and alert pipelines:

```powershell
& "d:\Hackathon_2026\.venv\Scripts\python.exe" backend/test_backend.py
```

---

### 4. Start the FastAPI Server

Launch the Uvicorn ASGI server:

```powershell
& "d:\Hackathon_2026\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

---

### 5. Stream Live IoT Telemetry

To simulate realistic multi-sensor telemetry packets streaming from NER cold storage chambers:

```powershell
cd backend
& "d:\Hackathon_2026\.venv\Scripts\python.exe" simulate_iot.py
```

---

## 📡 Sample IoT Ingestion Payload

Microcontrollers (ESP32 / Raspberry Pi / LoRaWAN Edge Gateways) send JSON packets to `POST /api/v1/telemetry/ingest`:

```json
{
  "device_id": "NER-CS-001",
  "seq": 1042,
  "zone_name": "Zone A - Cabbage Chamber",
  "crop_type": "Cabbage",
  "temperature": 1.1,
  "humidity": 97.0,
  "co2_true": 1450.0,
  "light": 0.4,
  "surface_temp": 0.9,
  "probe_temps": [0.8, 1.0, 1.1, 1.3, 1.4],
  "probe_status": ["OK", "OK", "OK", "OK", "OK"],
  "door_open": false,
  "compressor_on": true,
  "fan_on": true,
  "power_source": "SOLAR",
  "pv_power_w": 680.0,
  "battery_soc": 82.0,
  "battery_v": 25.4,
  "load_power_w": 310.0,
  "rssi": -58,
  "edge_status": "OK"
}
```
