# Cold Storage Backend Service (FastAPI)

High-performance, async FastAPI backend powering the **Solar-Powered Smart Mini Cold Storage System for the North Eastern Region (NER)**.

---

## ⚡ Quick Reference

- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **WebSocket Feeds**: `ws://localhost:8000/ws` and `ws://localhost:8000/ws/{zone_id}`

---

## 🚀 Commands

### 1. Run Verification Test Suite
```powershell
& "d:\Hackathon_2026\.venv\Scripts\python.exe" test_backend.py
```

### 2. Start Uvicorn Server
```powershell
& "d:\Hackathon_2026\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

### 3. Run Real-Time IoT Telemetry Simulator
```powershell
& "d:\Hackathon_2026\.venv\Scripts\python.exe" simulate_iot.py
```

---

## 🏗️ Architecture & Modules

1. **`app/api/v1/`**:
   - `telemetry.py`: Ingestion endpoints (`/ingest`, `/bulk`) with deduplication & replay tracking.
   - `zones.py`: Chamber control (`/setpoint`, `/mode`, `/crop`).
   - `devices.py`: Edge IoT node health & fleet monitoring (`/devices`, `/devices/{id}/health`).
   - `dashboard.py`: Live aggregate summaries, chamber gauges, and historical telemetry.
   - `alerts.py`: Active alert listings, acknowledgement, and resolution audits.
   - `farmers.py`: Farmer profiles and allocated crop batches.
2. **`app/services/`**:
   - `psychrometrics.py`: Dew point, VPD, absolute humidity, and condensation margin.
   - `power_service.py`: Solar PV vs battery classification and autonomy hours remaining.
   - `watchdog_service.py`: Automated background heartbeat & power-loss monitor.
   - `ml_service.py`: AI/ML spoilage risk and shelf-life prediction.
   - `alert_service.py`: Multi-threshold bounds evaluation & SMS alerting.
   - `cache_service.py`: Redis in-memory cache, distributed locking (`SET NX EX`), and Pub/Sub.
   - `smschef_service.py`: Cellular SMS gateway dispatch with console simulation fallback.
3. **`app/models/`**:
   - `telemetry.py`: Wide `TelemetryFrame` model (with `uq_frame_device_seq`) and `SensorTelemetryLog`.
   - `cold_storage.py`: `ColdStorage` and `Zone` models with chilling injury and freezing points.
   - `device.py`: `Device` fleet registry model.
   - `sensor.py`, `alert.py`, `crop_batch.py`, `user.py`.

