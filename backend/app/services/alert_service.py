import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.alert import Alert, AlertNotification
from app.models.cold_storage import Zone
from app.models.sensor import Sensor
from app.models.user import User
from app.models.crop_batch import CropBatch
from app.core.config import settings
from app.services.smschef_service import smschef_service
from app.services.cache_service import cache_service

logger = logging.getLogger("coldstorage.alerts")
CRITICAL_MARGIN = {
    "TEMPERATURE": 2.0,
    "HUMIDITY": 10.0,
    "CO2": 3000.0,
    "VOC_INDEX": 100.0,
    "LIGHT": 50.0,
}

class AlertService:
    @staticmethod
    async def evaluate_sensor_and_alert(
        db: AsyncSession,
        zone: Zone,
        sensor: Sensor,
        reading_value: float,
        spoilage_risk_pct: float
    ) -> Optional[Alert]:
        """
        Check if the sensor reading violates thresholds and trigger an alert with debouncing.
        """
        alert_triggered = False
        alert_type = None
        severity = "WARNING"
        title = ""
        message = ""

        # 1. Check direct threshold breach
        if reading_value > sensor.max_reading:
            alert_triggered = True
            margin = CRITICAL_MARGIN.get(sensor.sensor_type, 3.0)
            severity = "CRITICAL" if (reading_value - sensor.max_reading) >= margin else "WARNING"
            alert_type = f"{sensor.sensor_type}_HIGH"
            title = f"High {sensor.sensor_type.capitalize()} Alert in {zone.zone_name}"
            message = (
                f"{sensor.sensor_type.capitalize()} reached {reading_value:.2f}{sensor.unit}, "
                f"exceeding safe maximum threshold of {sensor.max_reading:.2f}{sensor.unit} "
                f"for stored {zone.current_crop_type}."
            )
        if not alert_triggered and reading_value < sensor.base_reading and sensor.base_reading > 0:
            alert_triggered = True
            severity = "WARNING"
            alert_type = f"{sensor.sensor_type}_LOW"
            title = f"Low {sensor.sensor_type.capitalize()} Alert in {zone.zone_name}"
            message = (
                f"{sensor.sensor_type.capitalize()} dropped to {reading_value:.2f}{sensor.unit}, "
                f"below safe minimum baseline of {sensor.base_reading:.2f}{sensor.unit} "
                f"for stored {zone.current_crop_type}."
            )
        if not alert_triggered and spoilage_risk_pct >= 70.0 and sensor.sensor_type in ("TEMPERATURE", "CO2"):
            alert_triggered = True
            severity = "CRITICAL"
            alert_type = "SPOILAGE_RISK_HIGH"
            title = f"Critical Spoilage Danger in {zone.zone_name}"
            message = (
                f"Composite decay prediction detected a {spoilage_risk_pct:.1f}% risk of "
                f"{zone.current_crop_type} spoiling rapidly due to current chamber conditions."
            )

        if not alert_triggered:
            return None

        # 2. Debounce Check: Check distributed Redis lock & recent DB alerts
        lock_acquired = await cache_service.acquire_alert_lock(
            zone_id=zone.zone_id,
            alert_type=alert_type,
            ttl_seconds=settings.ALERT_DEBOUNCE_MINUTES * 60
        )
        if not lock_acquired:
            # Active debounce lock in Redis, suppress duplicate SMS & alert creation
            return None

        debounce_cutoff = datetime.utcnow() - timedelta(minutes=settings.ALERT_DEBOUNCE_MINUTES)
        existing_alert_query = select(Alert).where(
            and_(
                Alert.zone_id == zone.zone_id,
                Alert.alert_type == alert_type,
                Alert.status == "ACTIVE",
                Alert.created_at >= debounce_cutoff
            )
        )
        result = await db.execute(existing_alert_query)
        recent_alert = result.scalars().first()

        if recent_alert:
            # Already alerted recently, suppress spam
            return None

        # 3. Create Alert Record
        new_alert = Alert(
            zone_id=zone.zone_id,
            sensor_id=sensor.sensor_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            status="ACTIVE",
            is_farmer_notified=False,
            created_at=datetime.utcnow()
        )
        new_alert.metric = sensor.sensor_type
        new_alert.observed_value = reading_value
        new_alert.threshold_value = sensor.max_reading if alert_type.endswith("_HIGH") else sensor.base_reading
        db.add(new_alert)
        await db.flush() # Populate alert_id

        # Update Zone overall status
        if severity == "CRITICAL":
            zone.status = "CRITICAL"
        elif zone.status != "CRITICAL":
            zone.status = "WARNING"

        # 4. Dispatch Farmer Notification
        await AlertService.dispatch_farmer_notification(db, zone, new_alert)

        return new_alert

    @staticmethod
    async def raise_system_alert(
        db: AsyncSession,
        zone_id: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        device_id: Optional[str] = None,
    ) -> Optional[Alert]:
        """Create a debounced alert when no sensor reading is available."""
        zone = await db.get(Zone, zone_id) if zone_id else None
        if not zone:
            return None
        lock_acquired = await cache_service.acquire_alert_lock(
            zone_id=zone.zone_id,
            alert_type=alert_type,
            ttl_seconds=settings.ALERT_DEBOUNCE_MINUTES * 60,
        )
        if not lock_acquired:
            return None
        alert = Alert(
            zone_id=zone.zone_id,
            device_id=device_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            status="ACTIVE",
            is_farmer_notified=False,
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        await db.flush()
        zone.status = "CRITICAL" if severity == "CRITICAL" else "WARNING"
        await AlertService.dispatch_farmer_notification(db, zone, alert)
        return alert

    @staticmethod
    async def dispatch_farmer_notification(
        db: AsyncSession,
        zone: Zone,
        alert: Alert
    ):
        """
        Finds all farmers who have crop batches in this zone and sends notification.
        """
        # Query farmers with batches in this zone
        batch_query = (
            select(User)
            .join(CropBatch, CropBatch.farmer_id == User.user_id)
            .where(CropBatch.zone_id == zone.zone_id)
            .distinct()
        )
        farmers = (await db.execute(batch_query)).scalars().all()

        for farmer in farmers:
            notification_content = (
                f"🚨 [Cold Storage Alert - {alert.severity}]\n"
                f"Dear {farmer.name},\n"
                f"{alert.title}\n"
                f"{alert.message}\n"
                f"Chamber: {zone.zone_name} | Produce: {zone.current_crop_type}\n"
                f"Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Action: Check chamber cooling & ventilation."
            )

            # Dispatch via SMS Chef Gateway (or simulator)
            delivery_status = "SENT"
            if farmer.preferred_alert_channel in ("SMS", "WHATSAPP"):
                sms_res = await smschef_service.send_sms(
                    phone_number=farmer.phone_number,
                    message=notification_content
                )
                if sms_res.get("status") == "FAILED":
                    delivery_status = "FAILED"

            if settings.ENABLE_SMS_SIMULATION:
                logger.warning(
                    f"\n================ [FARMER NOTIFICATION DISPATCHED] ================\n"
                    f"To: {farmer.name} ({farmer.phone_number}) via {farmer.preferred_alert_channel}\n"
                    f"{notification_content}\n"
                    f"==================================================================\n"
                )

            # Record notification log in database
            notification = AlertNotification(
                alert_id=alert.alert_id,
                farmer_id=farmer.user_id,
                channel=farmer.preferred_alert_channel,
                recipient=farmer.phone_number if farmer.preferred_alert_channel in ("SMS", "WHATSAPP") else (farmer.email or farmer.phone_number),
                content=notification_content,
                delivery_status=delivery_status,
                sent_at=datetime.utcnow()
            )
            db.add(notification)

        alert.is_farmer_notified = True

alert_service = AlertService()
