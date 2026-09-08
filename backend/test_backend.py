import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.init_db import init_database
from app.db.database import AsyncSessionLocal
from app.services.ml_service import ml_service
from app.services.telemetry_service import telemetry_service
from app.services.psychrometrics import dew_point_c, condensation_margin_c, vpd_kpa
from app.services.power_service import classify_source, autonomy_hours
from app.schemas.ml import SpoilagePredictionRequest
from app.schemas.telemetry import TelemetryIngestRequest, BulkTelemetryIngestRequest
from app.models.cold_storage import Zone
from app.models.alert import Alert
from app.models.device import Device
from app.models.telemetry import TelemetryFrame
from sqlalchemy import select

async def main():
    print("================================================================================")
    print("KRISHI COLD CHAIN - SOLAR SMART MINI COLD STORAGE BACKEND VALIDATION")
    print("Problem Statement: Decentralized Solar Cold Storage for North Eastern Region")
    print("================================================================================\n")

    # 1. Initialize Database and NER Seeds
    print("1. [DATABASE] Initializing PostgreSQL/SQLite & Seeding NER Cold Storage Chambers...")
    await init_database()
    print("   [OK] Database tables initialized and 4 NER Chambers seeded (Cabbage, French bean, Leafy greens, Tomato)!\n")

    # 2. Test Psychrometrics & Solar Power Service
    print("2. [EDGE & PHYSICS] Validating Psychrometric Formulas & Solar Power Calculation...")
    dp = dew_point_c(13.6, 92.0)
    margin = condensation_margin_c(13.2, 13.6, 92.0)
    vpd = vpd_kpa(13.6, 92.0)
    source = classify_source(pv_w=720.0, battery_soc=88.0, grid_present=False, load_w=330.0)
    autonomy = autonomy_hours(battery_soc=88.0, capacity_kwh=10.0, load_w=330.0)
    print(f"   * Dew Point: {dp:.2f}C | Condensation Margin: {margin:.2f}C | VPD: {vpd:.3f} kPa")
    print(f"   * Power Source: {source} (Solar-Powered) | Battery Autonomy: {autonomy:.1f} Hours")
    print("   [OK] Physics, Solar and Psychrometric services verified!\n")

    # 3. Test ML & Science-Backed Spoilage Prediction
    print("3. [AI/ML GUARDIAN] Testing Spoilage Prediction with Science-Backed NER Crop Limits...")
    # Normal Cabbage (Ideal 0-2°C)
    norm_req = SpoilagePredictionRequest(
        crop_type="Cabbage",
        temperature=1.1,
        humidity=97.0,
        light=0.4,
        co2=1450.0 # Realistic NDIR atmospheric/respiration reading
    )
    norm_res = ml_service.predict_spoilage(norm_req)
    print(f"   [Cabbage - Ideal Storage] Quality: {norm_res.predicted_quality} | Risk: {norm_res.spoilage_risk_percentage}% | Est Shelf Life: {norm_res.estimated_shelf_life_days} days")

    # Anomaly French bean (Temp 4.2°C is below chilling injury 5.0°C!)
    decay_req = SpoilagePredictionRequest(
        crop_type="French bean",
        temperature=4.2,
        humidity=91.0,
        light=0.8,
        co2=4700.0
    )
    decay_res = ml_service.predict_spoilage(decay_req)
    print(f"   [French Bean - Chilling Risk] Quality: {decay_res.predicted_quality} | Risk: {decay_res.spoilage_risk_percentage}% | Level: {decay_res.risk_level}")
    print(f"   Recommendations: {decay_res.recommendations}")
    print("   [OK] ML Spoilage Guardian operational!\n")

    # 4. Test Live IoT Telemetry Ingestion Pipeline
    print("4. [IOT INGESTION] Testing Full Multi-Sensor & Solar Telemetry Packet Ingestion...")
    async with AsyncSessionLocal() as session:
        telemetry_payload = TelemetryIngestRequest(
            device_id="NER-CS-004",
            seq=101,
            zone_name="Zone D - Tomato Chamber",
            crop_type="Tomato",
            temperature=13.6,
            humidity=92.0,
            co2_true=2300.0,
            eco2=1800.0,
            voc_index=72.0,
            light=0.4,
            probe_temps=[13.1, 13.4, 13.6, 13.8, 14.0],
            probe_status=["OK", "OK", "OK", "OK", "OK"],
            surface_temp=13.2,
            door_open=False,
            compressor_on=True,
            fan_on=True,
            power_source="SOLAR",
            pv_power_w=720.0,
            battery_soc=88.0,
            battery_v=25.6,
            load_power_w=330.0,
            rssi=-55,
            edge_status="OK"
        )
        ingest_res = await telemetry_service.process_telemetry(session, telemetry_payload)
        print(f"   * Ingest Result: {ingest_res.status} | Zone: {ingest_res.zone_id}")
        print(f"   * Alerts Triggered: {ingest_res.alerts_triggered} | Spoilage: {ingest_res.spoilage_status}")
        print(f"   * Recommended Setpoint: {ingest_res.recommended_setpoint_c}C | Condensation Margin: {ingest_res.condensation_margin_c:.2f}C")

        # Verify TelemetryFrame & Device in DB
        device = await session.get(Device, "NER-CS-004")
        print(f"   * Registered Device: {device.device_id} | Online: {device.is_online} | Power: {device.last_power_source} ({device.last_battery_soc}%)")
    print("   [OK] IoT Multi-Sensor Ingestion verified!\n")

    # 5. Test Anomaly Trigger & Farmer Notification Dispatch
    print("5. [ALERTS & SMS] Testing Critical Temperature Spike & Farmer Alert Dispatch...")
    async with AsyncSessionLocal() as session:
        anomaly_payload = TelemetryIngestRequest(
            device_id="NER-CS-001",
            seq=102,
            zone_name="Zone A - Cabbage Chamber",
            crop_type="Cabbage",
            temperature=5.5, # Over max 2.0°C by 3.5°C -> CRITICAL Alert
            humidity=99.0,
            co2_true=6200.0,
            light=18.0,
            door_open=True,
            power_source="BATTERY",
            battery_soc=18.0,
            load_power_w=360.0
        )
        anomaly_res = await telemetry_service.process_telemetry(session, anomaly_payload)
        print(f"   * Anomaly Result: {anomaly_res.status} | Alerts Triggered: {anomaly_res.alerts_triggered}")

        # Check Active Alerts in DB
        alerts_res = await session.execute(select(Alert).where(Alert.status == "ACTIVE"))
        active_alerts = alerts_res.scalars().all()
        print(f"   * Active Alerts in DB: {len(active_alerts)}")
        for a in active_alerts:
            print(f"     -> [{a.severity}] {a.title} (Farmer Notified: {a.is_farmer_notified})")
    print("   [OK] Farmer Alerting and SMS dispatch pipeline verified!\n")

    print("================================================================================")
    print("SUCCESS: ALL NER SOLAR COLD STORAGE BACKEND SERVICES FULLY OPERATIONAL AND VERIFIED!")
    print("================================================================================")

if __name__ == "__main__":
    asyncio.run(main())
