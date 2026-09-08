from datetime import datetime, timezone
from typing import Dict
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
        received_at = datetime.utcnow()
        co2_value = data.co2_true if data.co2_true is not None else data.co2

        readings: Dict[str, float] = {}
        for sensor_type, value in {
            "TEMPERATURE": data.temperature,
            "HUMIDITY": data.humidity,
            "CO2": co2_value,
            "LIGHT": data.light,
        }.items():
            if value is not None:
                readings[sensor_type] = value
        for item in data.readings or []:
            readings[item.sensor_type.upper()] = item.value

        temperature = data.temperature if data.temperature is not None else zone.setpoint_c or zone.temp_min
        humidity = data.humidity if data.humidity is not None else zone.setpoint_rh or zone.humidity_min
        co2 = co2_value if co2_value is not None else 0.0
        light = data.light if data.light is not None else 0.0
        prediction = ml_service.predict_spoilage(SpoilagePredictionRequest(
            crop_type=zone.current_crop_type, temperature=temperature, humidity=humidity,
            co2=co2, light=light
        ))

        device = None
        if data.device_id:
            device = await db.get(Device, data.device_id)
            if not device:
                device = Device(device_id=data.device_id, zone_id=zone.zone_id)
                db.add(device)
            device.zone_id = zone.zone_id
            device.last_seen_at = received_at
            device.last_seq = data.seq if data.seq is not None else device.last_seq
            device.last_power_source = data.power_source
            device.last_battery_soc = data.battery_soc
            device.last_temp_c = temperature
            device.last_rssi = data.rssi
            device.firmware = data.firmware
            device.is_online = True

        existing = (await db.execute(select(Sensor).where(Sensor.zone_id == zone.zone_id))).scalars().all()
        sensor_dict = {(s.sensor_type.upper(), s.channel or ""): s for s in existing}
        bounds = {
            "TEMPERATURE": (zone.temp_min, zone.temp_max, "°C"),
            "HUMIDITY": (zone.humidity_min, zone.humidity_max, "%"),
            "CO2": (0.0, zone.co2_ppm_max or zone.co2_max or 5000.0, "ppm"),
            "LIGHT": (0.0, zone.light_max, "Lux"),
        }
        alerts = 0
        for sensor_type, value in readings.items():
            channel = "CHAMBER" if sensor_type == "CO2" else "AIR"
            sensor = sensor_dict.get((sensor_type, channel))
            minimum, maximum, unit = bounds.get(sensor_type, (0.0, 100.0, "units"))
            if not sensor:
                sensor = Sensor(zone_id=zone.zone_id, sensor_type=sensor_type, channel=channel, device_id=data.device_id,
                                unit=unit, current_reading=value, base_reading=minimum, max_reading=maximum,
                                status="ACTIVE", timestamp=sampled_at)
                db.add(sensor)
                await db.flush()
                sensor_dict[(sensor_type, channel)] = sensor
            else:
                sensor.current_reading, sensor.timestamp, sensor.device_id = value, sampled_at, data.device_id
                sensor.base_reading, sensor.max_reading = minimum, maximum
            db.add(SensorTelemetryLog(sensor_id=sensor.sensor_id, zone_id=zone.zone_id, sensor_type=sensor_type,
                                      reading_value=value, recorded_at=sampled_at))
            if await alert_service.evaluate_sensor_and_alert(db, zone, sensor, value, prediction.spoilage_risk_percentage):
                alerts += 1

        margin = None
        dew_point = None
        if data.surface_temp is not None:
            dew_point = dew_point_c(temperature, humidity)
            margin = condensation_margin_c(data.surface_temp, temperature, humidity)
        stratification = None
        if data.probe_temps:
            stratification = max(data.probe_temps) - min(data.probe_temps)

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
                    load_power_w=data.load_power_w, autonomy_hours=autonomy_hours(data.battery_soc, 10.0, data.load_power_w),
                    dew_point_c=dew_point, vpd_kpa=vpd_kpa(temperature, humidity),
                    abs_humidity_gm3=abs_humidity_gm3(temperature, humidity), condensation_margin_c=margin,
                    stratification_c=stratification, rssi=data.rssi, firmware=data.firmware, edge_status=data.edge_status,
                )
                db.add(frame)
        if commit:
            await db.commit()

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
            "autonomy_hours": frame.autonomy_hours if frame else None, "rssi": data.rssi, "edge_status": data.edge_status,
        }
        await cache_service.set_live_zone_metrics(zone.zone_id, payload)
        await cache_service.publish_telemetry_event("coldstorage:telemetry", payload)
        await connection_manager.broadcast(payload, zone_id=zone.zone_id)
        return IngestResponse(status="SUCCESS", message=f"Processed telemetry for {len(readings)} sensors in {zone.zone_name}",
                              zone_id=zone.zone_id, alerts_triggered=alerts, spoilage_status=prediction.predicted_quality,
                              timestamp=sampled_at, condensation_margin_c=margin,
                              recommended_setpoint_c=zone.setpoint_c, server_time=received_at)

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