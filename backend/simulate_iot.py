"""
IoT Cold Storage Telemetry Simulator
Sends realistic sensor readings (Temperature, Humidity, Light, CO2) to the backend API every few seconds.
Can simulate normal operating conditions or trigger specific emergency anomalies (Temperature spikes, CO2 decay).
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
import asyncio

API_BASE_URL = "http://localhost:8000/api/v1"

DATA_FILE = Path(__file__).resolve().parents[1] / "config" / "ner_demo_telemetry.json"
NER_DEMO_PACKETS = json.loads(DATA_FILE.read_text(encoding="utf-8"))

async def send_telemetry_loop():
    print("🚀 Starting IoT Sensor Telemetry Simulator (Target: http://localhost:8000)...")
    base_seq = int(time.time()) % 1000000
    seq_counter = base_seq

    async with httpx.AsyncClient(timeout=10.0) as client:
        cycle = 0
        while True:
            for packet in NER_DEMO_PACKETS:
                seq_counter += 1
                payload = dict(packet)
                payload["seq"] = seq_counter
                payload["sampled_at"] = datetime.now(timezone.utc).isoformat()

                try:
                    res = await client.post(f"{API_BASE_URL}/telemetry/ingest", json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        alerts = data.get("alerts_triggered", 0)
                        alert_tag = f" | ⚠️ ALERTS: {alerts}" if alerts > 0 else " | [HEALTHY]"
                        power_tag = f"🔋 {payload.get('power_source', 'GRID')} ({payload.get('battery_soc', 0):.0f}%)"
                        print(f"[{payload.get('crop_type', 'Produce')}] T={payload['temperature']}°C | RH={payload['humidity']}% | CO2={payload.get('co2_true', payload.get('co2', 'N/A'))}ppm | {power_tag} -> {data.get('spoilage_status', 'OK')}{alert_tag}")
                    else:
                        print(f"Failed ({res.status_code}): {res.text}")
                except Exception as e:
                    print(f"Error connecting to backend: {e}")

            cycle += 1
            await asyncio.sleep(3.0)

if __name__ == "__main__":
    asyncio.run(send_telemetry_loop())

