from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.cold_storage import Zone
from app.models.sensor import Sensor
from app.models.telemetry import SensorTelemetryLog
from app.schemas.telemetry import TelemetryIngestRequest, IngestResponse
from app.schemas.ml import SpoilagePredictionRequest
from app.services.ml_service import ml_service
from app.services.alert_service import alert_service
from app.services.cache_service import cache_service
from app.core.websocket_manager import connection_manager

class TelemetryService:
    @staticmethod
    async def process_telemetry(db: AsyncSession, data: TelemetryIngestRequest) -> IngestResponse:
        """
        Process single/multi-sensor telemetry packet from IoT device.
        """
        # 1. Resolve Zone
        zone = None
        if data.zone_id:
            zone = await db.get(Zone, data.zone_id)
        elif data.zone_name:
            query = select(Zone).where(Zone.zone_name == data.zone_name)
            zone = (await db.execute(query)).scalars().first()

        if not zone:
            # Fallback to first zone
            query = select(Zone)
            zone = (await db.execute(query)).scalars().first()
            if not zone:
                raise ValueError("No valid zone found in storage to associate sensor reading.")

        timestamp = data.timestamp or datetime.utcnow()
        alerts_triggered_count = 0

        # Extract readings map
        readings_map: Dict[str, float] = {}
        if data.temperature is not None:
            readings_map["TEMPERATURE"] = data.temperature
        if data.humidity is not None:
            readings_map["HUMIDITY"] = data.humidity
        if data.co2 is not None:
            readings_map["CO2"] = data.co2
        if data.light is not None:
            readings_map["LIGHT"] = data.light

        if data.readings:
            for item in data.readings:
                sensor_type_upper = item.sensor_type.upper()
                readings_map[sensor_type_upper] = item.value

        # 2. Run Spoilage Prediction with latest zone readings
        crop = zone.current_crop_type
        # Fetch current sensor readings if not present in payload
        current_temp = readings_map.get("TEMPERATURE", zone.temp_min + 1.0)
        current_humid = readings_map.get("HUMIDITY", 90.0)
        current_co2 = readings_map.get("CO2", 330.0)
        current_light = readings_map.get("LIGHT", 10.0)

        ml_request = SpoilagePredictionRequest(
            crop_type=crop,
            temperature=current_temp,
            humidity=current_humid,
            co2=current_co2,
            light=current_light
        )
        prediction = ml_service.predict_spoilage(ml_request)

        # 3. Update or Create Sensor Records and Log Telemetry
        sensors_query = select(Sensor).where(Sensor.zone_id == zone.zone_id)
        existing_sensors = (await db.execute(sensors_query)).scalars().all()
        sensor_dict = {s.sensor_type.upper(): s for s in existing_sensors}

        unit_defaults = {
            "TEMPERATURE": "°C",
            "HUMIDITY": "%",
            "CO2": "ppm",
            "LIGHT": "Lux"
        }
        bounds_defaults = {
            "TEMPERATURE": (zone.temp_min, zone.temp_max),
            "HUMIDITY": (zone.humidity_min, zone.humidity_max),
            "CO2": (0.0, zone.co2_max),
            "LIGHT": (0.0, zone.light_max)
        }

        for sensor_type, value in readings_map.items():
            sensor = sensor_dict.get(sensor_type)
            if not sensor:
                base_val, max_val = bounds_defaults.get(sensor_type, (0.0, 100.0))
                sensor = Sensor(
                    zone_id=zone.zone_id,
                    sensor_type=sensor_type,
                    unit=unit_defaults.get(sensor_type, "units"),
                    current_reading=value,
                    base_reading=base_val,
                    max_reading=max_val,
                    status="ACTIVE",
                    timestamp=timestamp
                )
                db.add(sensor)
                await db.flush()
                sensor_dict[sensor_type] = sensor
            else:
                sensor.current_reading = value
                sensor.timestamp = timestamp

            # Create historical time-series log
            log = SensorTelemetryLog(
                sensor_id=sensor.sensor_id,
                zone_id=zone.zone_id,
                sensor_type=sensor_type,
                reading_value=value,
                recorded_at=timestamp
            )
            db.add(log)

            # Evaluate alerts for this reading
            alert = await alert_service.evaluate_sensor_and_alert(
                db=db,
                zone=zone,
                sensor=sensor,
                reading_value=value,
                spoilage_risk_pct=prediction.spoilage_risk_percentage
            )
            if alert:
                alerts_triggered_count += 1

        # Commit DB transaction
        await db.commit()

        # 4. Construct live telemetry payload
        ws_payload = {
            "type": "TELEMETRY_UPDATE",
            "zone_id": zone.zone_id,
            "zone_name": zone.zone_name,
            "crop_type": zone.current_crop_type,
            "temperature": current_temp,
            "humidity": current_humid,
            "co2": current_co2,
            "light": current_light,
            "spoilage_risk": prediction.predicted_quality,
            "risk_score": prediction.spoilage_risk_percentage,
            "status": zone.status,
            "timestamp": timestamp.isoformat()
        }

        # 5. Cache live metrics in Redis for sub-millisecond dashboard reads & publish event
        await cache_service.set_live_zone_metrics(zone.zone_id, ws_payload)
        await cache_service.publish_telemetry_event("coldstorage:telemetry", ws_payload)

        # 6. Broadcast live telemetry packet to WebSocket clients
        await connection_manager.broadcast(ws_payload, zone_id=zone.zone_id)

        return IngestResponse(
            status="SUCCESS",
            message=f"Processed telemetry for {len(readings_map)} sensors in {zone.zone_name}",
            zone_id=zone.zone_id,
            alerts_triggered=alerts_triggered_count,
            spoilage_status=prediction.predicted_quality,
            timestamp=timestamp
        )

telemetry_service = TelemetryService()
