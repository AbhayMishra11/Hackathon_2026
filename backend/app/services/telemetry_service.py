from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import connection_manager
from app.models.cold_storage import Zone
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.telemetry import SensorTelemetryLog, TelemetryFrame
from app.schemas.ml import SpoilagePredictionRequest
from app.schemas.telemetry import IngestResponse, TelemetryIngestRequest
from app.services.alert_service import alert_service
from app.services.cache_service import cache_service
from app.services.ml_service import ml_service
from app.services.power_service import autonomy_hours
from app.services.psychrometrics import abs_humidity_gm3, condensation_margin_c, dew_point_c, vpd_kpa
from app.services.shelf_life_service import shelf_life_service


def _naive_utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


class TelemetryService:
    @staticmethod
    async def frame_exists(db: AsyncSession, data: TelemetryIngestRequest) -> bool:
        if not data.device_id or data.seq is None:
            return False
        result = await db.execute(select(TelemetryFrame.frame_id).where(
            TelemetryFrame.device_id == data.device_id, TelemetryFrame.seq == data.seq
        ))
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def process_telemetry(db: AsyncSession, data: TelemetryIngestRequest, commit: bool = True) -> IngestResponse:
        zone = await TelemetryService._resolve_zone(db, data)
        sampled_at = _naive_utc(data.sampled_at or data.timestamp)
        received_at = datetime.now(timezone.utc).replace(tzinfo=None)
        co2_value = data.co2_true if data.co2_true is not None else data.co2

        # 1. Device Resolution & Power Transition Tracking
        device: Optional[Device] = None
        old_power_source: Optional[str] = None
        if data.device_id:
            device = await db.get(Device, data.device_id)
            if not device:
                device = Device(device_id=data.device_id, zone_id=zone.zone_id)
                db.add(device)
            else:
                old_power_source = device.last_power_source

        # 2. Existing Sensor Map for this Zone
        existing_sensors = (await db.execute(select(Sensor).where(Sensor.zone_id == zone.zone_id))).scalars().all()
        sensor_dict: Dict[Any, Sensor] = {}
        type_to_sensor: Dict[str, Sensor] = {}
        for s in existing_sensors:
            stype = s.sensor_type.upper()
            sensor_dict[(stype, s.channel or "")] = s
            type_to_sensor[stype] = s
            if stype not in sensor_dict:
                sensor_dict[stype] = s

        # 3. Sensor Health & Malfunction Diagnostic Check
        sensor_health_alerts = await alert_service.evaluate_sensor_health(
            db=db,
            zone=zone,
            device=device,
            temperature=data.temperature,
            humidity=data.humidity,
            co2=co2_value,
            air_sensor_ok=data.air_sensor_ok,
            probe_temps=data.probe_temps,
            probe_status=data.probe_status,
            edge_status=data.edge_status,
            sensor_dict=type_to_sensor,
        )

        # 4. Temperature & Humidity Validation / Fallback
        # Prevent damaged/disconnected probe readings (e.g., -127°C or 85°C) from poisoning physics and ML models
        is_temp_valid = (
            data.temperature is not None
            and -30.0 <= data.temperature <= 60.0
            and data.temperature != 85.0
        )

        if is_temp_valid:
            temperature = data.temperature
        else:
            # Fallback to median of valid probe array if available, or zone setpoint
            valid_probes = [p for p in (data.probe_temps or []) if -30.0 <= p <= 60.0 and p != 85.0]
            if valid_probes:
                temperature = sorted(valid_probes)[len(valid_probes) // 2]
            else:
                temperature = zone.setpoint_c if zone.setpoint_c is not None else (zone.temp_min or 2.0)

        is_humidity_valid = (data.humidity is not None and 0.0 < data.humidity <= 100.0)
        humidity = data.humidity if is_humidity_valid else (zone.setpoint_rh or zone.humidity_min or 90.0)
        co2 = co2_value if (co2_value is not None and 100.0 <= co2_value <= 30000.0) else 450.0
        light = data.light if data.light is not None else 0.0

        # 5. ML Spoilage Guardian
        prediction = ml_service.predict_spoilage(SpoilagePredictionRequest(
            crop_type=zone.current_crop_type, temperature=temperature, humidity=humidity,
            co2=co2, light=light
        ))

        # 6. Power Transition & Battery Autonomy Evaluation
        power_alerts = []
        autonomy_calc = None
        if data.battery_soc is not None or data.power_source:
            autonomy_calc = autonomy_hours(data.battery_soc, 10.0, data.load_power_w)

        if device and data.power_source:
            power_alerts = await alert_service.evaluate_power_transition(
                db=db,
                zone=zone,
                device=device,
                current_source=data.power_source,
                previous_source=old_power_source,
                battery_soc=data.battery_soc,
                battery_v=data.battery_v,
                autonomy_h=autonomy_calc,
            )

        # 7. Update Device State & Auto-resolve Node Offline
        if device:
            device.zone_id = zone.zone_id
            device.last_seen_at = received_at
            device.last_seq = data.seq if data.seq is not None else device.last_seq
            device.last_power_source = data.power_source
            device.last_battery_soc = data.battery_soc
            device.last_temp_c = temperature
            device.last_rssi = data.rssi
            device.firmware = data.firmware
            device.is_online = True
            await alert_service.auto_resolve_alerts(
                db=db,
                zone_id=zone.zone_id,
                alert_types=["NODE_OFFLINE"],
                device_id=device.device_id
            )

        # 8. Sensor Log Ingestion & Direct Threshold Alerts
        readings: Dict[str, float] = {}
        if is_temp_valid:
            readings["TEMPERATURE"] = data.temperature
        if is_humidity_valid:
            readings["HUMIDITY"] = data.humidity
        if co2_value is not None and 100.0 <= co2_value <= 30000.0:
            readings["CO2"] = co2_value
        if data.light is not None:
            readings["LIGHT"] = data.light

        for item in data.readings or []:
            st = item.sensor_type.upper()
            if st == "TEMPERATURE" and not (-30.0 <= item.value <= 60.0 and item.value != 85.0):
                continue
            readings[st] = item.value

        bounds = {
            "TEMPERATURE": (zone.temp_min, zone.temp_max, "°C"),
            "HUMIDITY": (zone.humidity_min, zone.humidity_max, "%"),
            "CO2": (0.0, zone.co2_ppm_max or zone.co2_max or 5000.0, "ppm"),
            "LIGHT": (0.0, zone.light_max, "Lux"),
        }

        channel_alerts_count = 0
        for sensor_type, value in readings.items():
            channel = "CHAMBER" if sensor_type == "CO2" else "AIR"
            sensor = sensor_dict.get((sensor_type, channel)) or sensor_dict.get(sensor_type)
            minimum, maximum, unit = bounds.get(sensor_type, (0.0, 100.0, "units"))
            if not sensor:
                sensor = Sensor(
                    zone_id=zone.zone_id, sensor_type=sensor_type, channel=channel, device_id=data.device_id,
                    unit=unit, current_reading=value, base_reading=minimum, max_reading=maximum,
                    status="ACTIVE", timestamp=sampled_at
                )
                db.add(sensor)
                await db.flush()
                sensor_dict[(sensor_type, channel)] = sensor
                sensor_dict[sensor_type] = sensor
                type_to_sensor[sensor_type] = sensor
            else:
                sensor.channel = channel
                sensor.current_reading, sensor.timestamp, sensor.device_id = value, sampled_at, data.device_id
                sensor.base_reading, sensor.max_reading = minimum, maximum
                if sensor.status != "FAULT":
                    sensor.status = "ACTIVE"
            db.add(SensorTelemetryLog(
                sensor_id=sensor.sensor_id, zone_id=zone.zone_id, sensor_type=sensor_type,
                reading_value=value, recorded_at=sampled_at
            ))
            if await alert_service.evaluate_sensor_and_alert(db, zone, sensor, value, prediction.spoilage_risk_percentage):
                channel_alerts_count += 1

        # 9. Psychrometrics & Stratification
        margin = None
        dew_point = None
        if data.surface_temp is not None:
            dew_point = dew_point_c(temperature, humidity)
            margin = condensation_margin_c(data.surface_temp, temperature, humidity)
        stratification = None
        if data.probe_temps:
            valid_p = [p for p in data.probe_temps if -30.0 <= p <= 60.0 and p != 85.0]
            if len(valid_p) >= 2:
                stratification = max(valid_p) - min(valid_p)

        # 10. Persist TelemetryFrame
        frame = None
        if data.device_id and data.seq is not None:
            existing_frame = (await db.execute(
                select(TelemetryFrame).where(
                    TelemetryFrame.device_id == data.device_id,
                    TelemetryFrame.seq == data.seq
                )
            )).scalars().first()

            if existing_frame:
                frame = existing_frame
                frame.is_replay = True
                frame.received_at = received_at
                frame.air_temp_c = temperature
                frame.air_rh = humidity
                frame.surface_temp_c = data.surface_temp
                frame.dew_point_c = dew_point
                frame.vpd_kpa = vpd_kpa(temperature, humidity)
                frame.condensation_margin_c = margin
                frame.stratification_c = stratification
            else:
                frame = TelemetryFrame(
                    device_id=data.device_id, zone_id=zone.zone_id, seq=data.seq, sampled_at=sampled_at,
                    received_at=received_at, is_replay=data.sampled_at is not None,
                    air_temp_c=temperature, air_rh=humidity, surface_temp_c=data.surface_temp,
                    ambient_temp_c=data.ambient_temp, probe_temps=data.probe_temps, probe_status=data.probe_status,
                    co2_ppm=co2_value, eco2_ppm=data.eco2, voc_index=data.voc_index, lux=light, mass_kg=data.mass_kg,
                    door_open=data.door_open or False, compressor_on=data.compressor_on or False,
                    fan_on=data.fan_on or False, mode=zone.mode, power_source=data.power_source,
                    pv_power_w=data.pv_power_w, battery_soc=data.battery_soc, battery_v=data.battery_v,
                    load_power_w=data.load_power_w, autonomy_hours=autonomy_calc,
                    dew_point_c=dew_point, vpd_kpa=vpd_kpa(temperature, humidity),
                    abs_humidity_gm3=abs_humidity_gm3(temperature, humidity), condensation_margin_c=margin,
                    stratification_c=stratification, rssi=data.rssi, firmware=data.firmware, edge_status=data.edge_status,
                )
                db.add(frame)

        # 11. Postharvest Shelf Life Integral (Physics Model)
        shelf_life = await shelf_life_service.update(
            db,
            zone_id=zone.zone_id,
            crop_type=zone.current_crop_type,
            temperature=temperature,
            humidity=humidity,
            sampled_at=sampled_at,
            condensation_margin_c=margin,
            mass_kg=data.mass_kg,
        )

        # 12. Evaluate Crop-Specific Storage Safety & Machine Alerts
        storage_alerts = await alert_service.evaluate_storage_safety(
            db=db,
            zone=zone,
            temperature=temperature,
            humidity=humidity,
            condensation_margin=margin,
            stratification=stratification,
            door_open=data.door_open,
            compressor_on=data.compressor_on,
            voc_index=data.voc_index,
            remaining_shelf_life_h=shelf_life.remaining_h if shelf_life else None,
            device_id=data.device_id,
        )

        total_alerts_count = (
            channel_alerts_count
            + len(sensor_health_alerts)
            + len(power_alerts)
            + len(storage_alerts)
        )

        if commit:
            await db.commit()

        # 13. Real-Time WebSocket & Cache Broadcast
        payload = {
            "type": "TELEMETRY_UPDATE", "zone_id": zone.zone_id, "zone_name": zone.zone_name,
            "device_id": data.device_id, "crop_type": zone.current_crop_type, "temperature": temperature,
            "humidity": humidity, "co2": co2, "light": light, "spoilage_risk": prediction.predicted_quality,
            "risk_score": prediction.spoilage_risk_percentage, "status": zone.status, "timestamp": sampled_at.isoformat(),
            "probe_temps": data.probe_temps, "probe_status": data.probe_status, "surface_temp": data.surface_temp,
            "stratification_c": stratification, "dew_point_c": dew_point, "vpd_kpa": vpd_kpa(temperature, humidity),
            "condensation_margin_c": margin, "voc_index": data.voc_index, "eco2_ppm": data.eco2,
            "door_open": data.door_open, "compressor_on": data.compressor_on, "mode": zone.mode,
            "setpoint_c": zone.setpoint_c, "power_source": data.power_source, "pv_power_w": data.pv_power_w,
            "battery_soc": data.battery_soc, "load_power_w": data.load_power_w,
            "autonomy_hours": frame.autonomy_hours if frame else autonomy_calc, "rssi": data.rssi, "edge_status": data.edge_status,
            "remaining_shelf_life_h": shelf_life.remaining_h if shelf_life else None,
            "total_damage": shelf_life.total_damage if shelf_life else None,
            "value_at_risk": shelf_life.value_at_risk if shelf_life else None,
        }
        await cache_service.set_live_zone_metrics(zone.zone_id, payload)
        await cache_service.publish_telemetry_event("coldstorage:telemetry", payload)
        await connection_manager.broadcast(payload, zone_id=zone.zone_id)
        remaining_h = shelf_life.remaining_h if shelf_life else None

        return IngestResponse(
            status="SUCCESS",
            message=f"Processed telemetry for {len(readings)} sensors in {zone.zone_name}",
            zone_id=zone.zone_id,
            alerts_triggered=total_alerts_count,
            spoilage_status=prediction.predicted_quality,
            timestamp=sampled_at,
            condensation_margin_c=margin,
            recommended_setpoint_c=zone.setpoint_c,
            server_time=received_at,
            remaining_shelf_life_h=remaining_h
        )

    @staticmethod
    async def _resolve_zone(db: AsyncSession, data: TelemetryIngestRequest) -> Zone:
        zone = await db.get(Zone, data.zone_id) if data.zone_id else None
        if not zone and data.zone_name:
            zone = (await db.execute(select(Zone).where(Zone.zone_name == data.zone_name))).scalars().first()
        if not zone and data.crop_type:
            zone = (await db.execute(select(Zone).where(Zone.current_crop_type.ilike(data.crop_type)))).scalars().first()
        if not zone:
            raise ValueError(f"Unknown zone: zone_id={data.zone_id!r} zone_name={data.zone_name!r}")
        return zone


telemetry_service = TelemetryService()