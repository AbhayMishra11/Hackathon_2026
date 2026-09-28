import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.device import Device
from app.models.sensor import Sensor
from app.services.alert_service import alert_service

logger = logging.getLogger("coldstorage.watchdog")


async def watchdog_loop():
    """
    Background asyncio worker monitoring IoT edge nodes and sensor heartbeats:
    1. Detects dropped node connections (NODE_OFFLINE)
    2. Detects battery exhaustion outages (POWER_FAILURE)
    3. Detects silent / stale sensors (> 15 min without data)
    """
    while True:
        try:
            async with AsyncSessionLocal() as db:
                devices = (await db.execute(select(Device))).scalars().all()
                now = datetime.now(timezone.utc).replace(tzinfo=None)

                for device in devices:
                    if not device.last_seen_at or not device.is_online:
                        continue
                    gap = (now - device.last_seen_at).total_seconds()
                    if gap <= (device.offline_grace_s or 90):
                        continue

                    battery_failure = device.last_power_source == "BATTERY" and (device.last_battery_soc or 0) < 25
                    alert_type = "POWER_FAILURE" if battery_failure else "NODE_OFFLINE"
                    title = f"Power failure at {device.device_id}" if battery_failure else f"Node {device.device_id} unreachable"
                    message = f"No telemetry for {int(gap)}s. Last temperature {device.last_temp_c}C, battery {device.last_battery_soc}%"

                    await alert_service.raise_system_alert(
                        db=db,
                        zone_id=device.zone_id,
                        alert_type=alert_type,
                        severity="CRITICAL",
                        title=title,
                        message=message,
                        device_id=device.device_id,
                        target_audience="OPERATOR"
                    )
                    device.is_online = False

                # Check stale sensors (> 15 minutes silence on an active sensor)
                active_sensors = (await db.execute(select(Sensor).where(Sensor.status == "ACTIVE"))).scalars().all()
                for sensor in active_sensors:
                    if sensor.timestamp:
                        sensor_gap = (now - sensor.timestamp).total_seconds()
                        if sensor_gap > 900:  # 15 minutes
                            sensor.status = "OFFLINE"
                            sensor.last_fault = f"No reading received for {int(sensor_gap//60)} minutes"
                            await alert_service.raise_system_alert(
                                db=db,
                                zone_id=sensor.zone_id,
                                alert_type="SENSOR_STALE",
                                severity="WARNING",
                                title=f"Sensor Offline in Zone",
                                message=f"Sensor '{sensor.sensor_type}' has not reported telemetry for {int(sensor_gap//60)} minutes.",
                                sensor_id=sensor.sensor_id,
                                device_id=sensor.device_id,
                                target_audience="OPERATOR"
                            )

                await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("watchdog tick failed")
        await asyncio.sleep(30)