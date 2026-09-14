import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.device import Device
from app.services.alert_service import alert_service

logger = logging.getLogger("coldstorage.watchdog")


async def watchdog_loop():
    """Raise one debounced alert when a registered node misses its heartbeat."""
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
                    await alert_service.raise_system_alert(db, device.zone_id, alert_type, "CRITICAL", title, message, device.device_id)
                    device.is_online = False
                await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("watchdog tick failed")
        await asyncio.sleep(30)