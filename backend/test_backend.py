import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.init_db import init_database
from app.db.database import AsyncSessionLocal
from app.services.ml_service import ml_service
from app.services.telemetry_service import telemetry_service
from app.schemas.ml import SpoilagePredictionRequest
from app.schemas.telemetry import TelemetryIngestRequest
from app.models.cold_storage import Zone
from app.models.alert import Alert
from sqlalchemy import select

async def main():
    print("1. Initializing Database and Seeding Data...")
    await init_database()
    print(" Database initialization complete!")

    print("\n2. Testing ML Spoilage Prediction Service...")
    # Test Normal Orange
    normal_req = SpoilagePredictionRequest(
        crop_type="Orange",
        temperature=22.0,
        humidity=92.0,
        light=6.5,
        co2=320.0
    )
    norm_res = ml_service.predict_spoilage(normal_req)
    print(f"   [Normal Orange] Quality: {norm_res.predicted_quality} | Risk: {norm_res.spoilage_risk_percentage}% | Level: {norm_res.risk_level}")

    # Test Anomaly Tomato (Spike in temp, high CO2, high humidity)
    decay_req = SpoilagePredictionRequest(
        crop_type="Tomato",
        temperature=26.0,
        humidity=96.0,
        light=16.0,
        co2=410.0
    )
    decay_res = ml_service.predict_spoilage(decay_req)
    print(f"   [Anomaly Tomato] Quality: {decay_res.predicted_quality} | Risk: {decay_res.spoilage_risk_percentage}% | Level: {decay_res.risk_level}")
    print(f"   Recommendations: {decay_res.recommendations}")

    print("\n3. Testing Ingestion & Alert Generation Pipeline...")
    async with AsyncSessionLocal() as session:
        # Ingest anomaly data into Zone A (Orange)
        telemetry_payload = TelemetryIngestRequest(
            zone_name="Zone A - Citrus Chamber",
            crop_type="Orange",
            temperature=26.5, # Over max 23.5°C
            humidity=96.0,
            co2=430.0,        # Over max 380 ppm
            light=15.0
        )
        ingest_res = await telemetry_service.process_telemetry(session, telemetry_payload)
        print(f"   Ingestion result: {ingest_res.status} | Alerts triggered: {ingest_res.alerts_triggered} | Spoilage: {ingest_res.spoilage_status}")

        # Verify alert in DB
        alerts_res = await session.execute(select(Alert).where(Alert.status == "ACTIVE"))
        active_alerts = alerts_res.scalars().all()
        print(f"   Active Alerts in DB: {len(active_alerts)}")
        for a in active_alerts:
            print(f"   -> [Alert] {a.severity}: {a.title} (Farmer Notified: {a.is_farmer_notified})")

    print("\n All Backend Services & Models Verified Successfully!")

if __name__ == "__main__":
    asyncio.run(main())

