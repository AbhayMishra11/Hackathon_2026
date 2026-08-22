"""
IoT Cold Storage Telemetry Simulator
Sends realistic sensor readings (Temperature, Humidity, Light, CO2) to the backend API every few seconds.
Can simulate normal operating conditions or trigger specific emergency anomalies (Temperature spikes, CO2 decay).
"""

import time
import random
import httpx
import asyncio

API_BASE_URL = "http://localhost:8000/api/v1"

ZONES_SIMULATION = [
    {
        "zone_name": "Zone A - Citrus Chamber",
        "crop_type": "Orange",
        "temp_base": 22.0,
        "humid_base": 92.0,
        "light_base": 7.5,
        "co2_base": 330.0
    },
    {
        "zone_name": "Zone B - Banana Chamber",
        "crop_type": "Banana",
        "temp_base": 25.0,
        "humid_base": 88.0,
        "light_base": 18.0,
        "co2_base": 340.0
    },
    {
        "zone_name": "Zone C - Tomato Chamber",
        "crop_type": "Tomato",
        "temp_base": 23.0,
        "humid_base": 88.0,
        "light_base": 11.0,
        "co2_base": 310.0
    },
    {
        "zone_name": "Zone D - Pineapple Chamber",
        "crop_type": "Pineapple",
        "temp_base": 23.0,
        "humid_base": 85.0,
        "light_base": 12.5,
        "co2_base": 335.0
    }
]

async def send_telemetry_loop():
    print("🚀 Starting IoT Sensor Telemetry Simulator (Target: http://localhost:8000)...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        step = 0
        while True:
            step += 1
            for zone in ZONES_SIMULATION:
                # Every 8th step, simulate an intentional anomaly in Zone A or C to test Farmer Alerts
                is_anomaly = (step % 8 == 0 and zone["crop_type"] in ("Orange", "Tomato"))
                
                temp = zone["temp_base"] + (random.uniform(2.5, 4.0) if is_anomaly else random.uniform(-0.5, 0.6))
                humid = zone["humid_base"] + random.uniform(-2.0, 2.0)
                light = zone["light_base"] + (random.uniform(6.0, 10.0) if is_anomaly else random.uniform(-1.0, 1.0))
                co2 = zone["co2_base"] + (random.uniform(80.0, 120.0) if is_anomaly else random.uniform(-10.0, 15.0))

                payload = {
                    "zone_name": zone["zone_name"],
                    "crop_type": zone["crop_type"],
                    "temperature": round(temp, 2),
                    "humidity": round(humid, 2),
                    "light": round(light, 2),
                    "co2": round(co2, 2)
                }

                try:
                    res = await client.post(f"{API_BASE_URL}/telemetry/ingest", json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        alert_info = f" | ⚠️ ALERTS: {data['alerts_triggered']}" if data['alerts_triggered'] > 0 else ""
                        print(f"[{zone['crop_type']}] T={payload['temperature']}°C H={payload['humidity']}% CO2={payload['co2']}ppm -> {data['spoilage_status']}{alert_info}")
                    else:
                        print(f"Failed ({res.status_code}): {res.text}")
                except Exception as e:
                    print(f"Error connecting to backend: {e}")

            await asyncio.sleep(3.0)

if __name__ == "__main__":
    asyncio.run(send_telemetry_loop())

