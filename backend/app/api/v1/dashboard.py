from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.db.database import get_db
from app.models.cold_storage import Zone, ColdStorage
from app.models.sensor import Sensor
from app.models.telemetry import SensorTelemetryLog
from app.models.alert import Alert
from app.models.crop_batch import CropBatch
from app.schemas.zone import ZoneLiveStatus
from app.schemas.ml import SpoilagePredictionRequest
from app.services.ml_service import ml_service
from app.services.cache_service import cache_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Monitoring"])

@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Get top-level cold storage summary metrics for the frontend overview page.
    """
    # 1. Total Facilities & Zones
    zones_res = await db.execute(select(Zone))
    zones = zones_res.scalars().all()

    # 2. Active Alerts count
    alerts_query = select(func.count(Alert.alert_id)).where(Alert.status == "ACTIVE")
    active_alerts_count = (await db.execute(alerts_query)).scalar() or 0

    # 3. Critical Warnings count
    critical_alerts_query = select(func.count(Alert.alert_id)).where(
        Alert.status == "ACTIVE", Alert.severity == "CRITICAL"
    )
    critical_alerts_count = (await db.execute(critical_alerts_query)).scalar() or 0

    # 4. Total Produce in Storage (kg)
    total_qty_query = select(func.sum(CropBatch.quantity_kg))
    total_produce_kg = (await db.execute(total_qty_query)).scalar() or 0.0

    # 5. Zone Health Overview
    optimal_zones = sum(1 for z in zones if z.status == "OPTIMAL")
    warning_zones = sum(1 for z in zones if z.status == "WARNING")
    critical_zones = sum(1 for z in zones if z.status == "CRITICAL")

    return {
        "total_zones": len(zones),
        "total_produce_stored_kg": round(total_produce_kg, 1),
        "active_alerts": active_alerts_count,
        "critical_alerts": critical_alerts_count,
        "zone_breakdown": {
            "optimal": optimal_zones,
            "warning": warning_zones,
            "critical": critical_zones
        },
        "system_status": "CRITICAL" if critical_zones > 0 else ("WARNING" if warning_zones > 0 else "OPTIMAL"),
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None)
    }

@router.get("/zones/{zone_id}/live", response_model=ZoneLiveStatus)
async def get_zone_live_status(zone_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get live sensor telemetry, ML spoilage risk score, and safety metrics for a specific zone.
    Checked against Redis in-memory cache first for sub-millisecond response time.
    """
    # 1. Check Redis Cache First
    cached_metrics = await cache_service.get_live_zone_metrics(zone_id)
    if cached_metrics:
        alerts_query = select(func.count(Alert.alert_id)).where(
            Alert.zone_id == zone_id, Alert.status == "ACTIVE"
        )
        active_alerts = (await db.execute(alerts_query)).scalar() or 0
        return ZoneLiveStatus(
            zone_id=cached_metrics["zone_id"],
            zone_name=cached_metrics["zone_name"],
            crop_type=cached_metrics["crop_type"],
            overall_status=cached_metrics.get("status", "OPTIMAL"),
            spoilage_risk=cached_metrics.get("spoilage_risk", "Good"),
            risk_score=cached_metrics.get("risk_score", 0.0),
            temperature=cached_metrics.get("temperature"),
            humidity=cached_metrics.get("humidity"),
            co2=cached_metrics.get("co2"),
            light=cached_metrics.get("light"),
            active_alerts_count=active_alerts,
            last_updated=datetime.fromisoformat(cached_metrics["timestamp"]) if "timestamp" in cached_metrics else datetime.now(timezone.utc).replace(tzinfo=None)
        )

    # 2. Database Fallback if cache miss
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Fetch active sensors
    sensors_query = select(Sensor).where(Sensor.zone_id == zone_id)
    sensors = (await db.execute(sensors_query)).scalars().all()
    sensor_map = {s.sensor_type.upper(): s.current_reading for s in sensors}

    temp = sensor_map.get("TEMPERATURE", 22.0)
    humid = sensor_map.get("HUMIDITY", 90.0)
    co2 = sensor_map.get("CO2", 320.0)
    light = sensor_map.get("LIGHT", 10.0)

    # ML Spoilage Prediction
    pred = ml_service.predict_spoilage(SpoilagePredictionRequest(
        crop_type=zone.current_crop_type,
        temperature=temp,
        humidity=humid,
        co2=co2,
        light=light
    ))

    # Active alerts in this zone
    alerts_query = select(func.count(Alert.alert_id)).where(
        Alert.zone_id == zone_id, Alert.status == "ACTIVE"
    )
    active_alerts = (await db.execute(alerts_query)).scalar() or 0

    return ZoneLiveStatus(
        zone_id=zone.zone_id,
        zone_name=zone.zone_name,
        crop_type=zone.current_crop_type,
        overall_status=zone.status,
        spoilage_risk=pred.predicted_quality,
        risk_score=pred.spoilage_risk_percentage,
        temperature=temp,
        humidity=humid,
        co2=co2,
        light=light,
        active_alerts_count=active_alerts,
        last_updated=datetime.now(timezone.utc).replace(tzinfo=None)
    )

@router.get("/zones/{zone_id}/history")
async def get_zone_telemetry_history(
    zone_id: str,
    sensor_type: Optional[str] = None,
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """
    Get time-series historical sensor records for interactive chart rendering on frontend.
    """
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    cutoff_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    
    query = (
        select(SensorTelemetryLog)
        .where(
            SensorTelemetryLog.zone_id == zone_id,
            SensorTelemetryLog.recorded_at >= cutoff_time
        )
    )
    if sensor_type:
        query = query.where(SensorTelemetryLog.sensor_type == sensor_type.upper())

    query = query.order_by(SensorTelemetryLog.recorded_at.asc()).limit(500)
    logs = (await db.execute(query)).scalars().all()

    # Format data for charts
    formatted_data = [
        {
            "timestamp": log.recorded_at.isoformat(),
            "sensor_type": log.sensor_type,
            "value": log.reading_value
        }
        for log in logs
    ]

    return {
        "zone_id": zone.zone_id,
        "zone_name": zone.zone_name,
        "crop_type": zone.current_crop_type,
        "hours": hours,
        "total_records": len(formatted_data),
        "data": formatted_data
    }

