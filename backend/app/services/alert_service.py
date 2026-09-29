import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.alert import Alert, AlertNotification
from app.models.cold_storage import Zone
from app.models.sensor import Sensor
from app.models.user import User
from app.models.crop_batch import CropBatch
from app.models.device import Device
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
        Check if an individual sensor reading violates safe operational thresholds
        and trigger a debounced alert.
        """
        alert_triggered = False
        alert_type = None
        severity = "WARNING"
        title = ""
        message = ""

        # 1. Direct threshold breach
        if sensor.max_reading is not None and reading_value > sensor.max_reading:
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
        elif sensor.base_reading is not None and sensor.base_reading > 0 and reading_value < sensor.base_reading:
            alert_triggered = True
            severity = "WARNING"
            alert_type = f"{sensor.sensor_type}_LOW"
            title = f"Low {sensor.sensor_type.capitalize()} Alert in {zone.zone_name}"
            message = (
                f"{sensor.sensor_type.capitalize()} dropped to {reading_value:.2f}{sensor.unit}, "
                f"below safe minimum baseline of {sensor.base_reading:.2f}{sensor.unit} "
                f"for stored {zone.current_crop_type}."
            )
        elif spoilage_risk_pct >= 70.0 and sensor.sensor_type in ("TEMPERATURE", "CO2"):
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

        # 2. Debounce Check
        lock_acquired = await cache_service.acquire_alert_lock(
            zone_id=zone.zone_id,
            alert_type=alert_type,
            ttl_seconds=settings.ALERT_DEBOUNCE_MINUTES * 60
        )
        if not lock_acquired:
            return None

        debounce_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=settings.ALERT_DEBOUNCE_MINUTES)
        existing_alert_query = select(Alert).where(
            and_(
                Alert.zone_id == zone.zone_id,
                Alert.alert_type == alert_type,
                Alert.status == "ACTIVE",
                Alert.created_at >= debounce_cutoff
            )
        )
        result = await db.execute(existing_alert_query)
        if result.scalars().first():
            return None

        # 3. Create Alert Record
        threshold_val = sensor.max_reading if (alert_type and alert_type.endswith("_HIGH")) else sensor.base_reading
        new_alert = Alert(
            zone_id=zone.zone_id,
            sensor_id=sensor.sensor_id,
            device_id=sensor.device_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            status="ACTIVE",
            is_farmer_notified=False,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            metric=sensor.sensor_type,
            observed_value=reading_value,
            threshold_value=threshold_val,
        )
        db.add(new_alert)
        await db.flush()

        # Update Zone overall status
        if severity == "CRITICAL":
            zone.status = "CRITICAL"
        elif zone.status != "CRITICAL":
            zone.status = "WARNING"

        # 4. Dispatch Notifications
        await AlertService.dispatch_notifications(db, zone, new_alert, target_audience="FARMER")
        return new_alert

    @staticmethod
    async def evaluate_storage_safety(
        db: AsyncSession,
        zone: Zone,
        temperature: Optional[float],
        humidity: Optional[float],
        condensation_margin: Optional[float] = None,
        stratification: Optional[float] = None,
        door_open: Optional[bool] = None,
        compressor_on: Optional[bool] = None,
        voc_index: Optional[float] = None,
        remaining_shelf_life_h: Optional[float] = None,
        device_id: Optional[str] = None
    ) -> List[Alert]:
        """
        Evaluate produce-specific storage safety conditions:
        1. Chilling Injury Risk (produce physiological cold damage)
        2. Freezing Hazard (cellular rupture)
        3. Condensation / Sweating (fungal / mold rot on produce skins)
        4. Thermal Stratification (poor air circulation)
        5. Prolonged Door Ajar
        6. Ineffective Cooling (compressor on but chamber warming)
        7. VOC / Respiration Spikes
        8. Remaining Shelf Life Depletion
        """
        triggered_alerts: List[Alert] = []

        if temperature is not None:
            # 1. Freezing Point Hazard (CRITICAL)
            if zone.freezing_point_c is not None and temperature <= zone.freezing_point_c:
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="FREEZING_HAZARD",
                    severity="CRITICAL",
                    title=f"CRITICAL: Freezing Hazard in {zone.zone_name}",
                    message=(
                        f"Chamber temperature ({temperature:.2f}°C) is at or below the crop freezing "
                        f"threshold ({zone.freezing_point_c:.2f}°C) for stored {zone.current_crop_type}. "
                        f"Cellular rupture and irreversible frost loss will occur."
                    ),
                    device_id=device_id,
                    metric="TEMPERATURE",
                    observed_value=temperature,
                    threshold_value=zone.freezing_point_c,
                    target_audience="ALL"
                )
                if alert:
                    triggered_alerts.append(alert)

            # 2. Chilling Injury Risk (Specific to subtropical/temperate crops e.g. Tomato, French Bean, Mandarin)
            elif zone.chilling_injury_c is not None and temperature < zone.chilling_injury_c:
                below_by = zone.chilling_injury_c - temperature
                severity = "CRITICAL" if below_by >= 2.0 else "WARNING"
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="CHILLING_INJURY_RISK",
                    severity=severity,
                    title=f"Chilling Injury Risk for {zone.current_crop_type} in {zone.zone_name}",
                    message=(
                        f"Chamber temperature ({temperature:.2f}°C) has fallen below the physiological "
                        f"chilling floor ({zone.chilling_injury_c:.2f}°C) for stored {zone.current_crop_type}. "
                        f"Continuous exposure causes skin pitting, watery breakdown, and failure to ripen."
                    ),
                    device_id=device_id,
                    metric="TEMPERATURE",
                    observed_value=temperature,
                    threshold_value=zone.chilling_injury_c,
                    target_audience="ALL"
                )
                if alert:
                    triggered_alerts.append(alert)
            else:
                # Temperature is safe: auto-resolve freezing and chilling injury alerts
                await AlertService.auto_resolve_alerts(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_types=["FREEZING_HAZARD", "CHILLING_INJURY_RISK"],
                    device_id=device_id
                )

        # 3. Condensation / Sweating Hazard (Dew point vs Surface Temp)
        if condensation_margin is not None:
            if condensation_margin <= 0.5:
                severity = "CRITICAL" if condensation_margin <= 0.0 else "WARNING"
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="CONDENSATION_MOLD_HAZARD",
                    severity=severity,
                    title=f"Produce Condensation & Mold Hazard in {zone.zone_name}",
                    message=(
                        f"Surface condensation margin is {condensation_margin:.2f}°C (surface is at/below dew point). "
                        f"Free moisture droplets are condensing onto {zone.current_crop_type}, "
                        f"creating ideal conditions for rapid Botrytis and mold sporulation."
                    ),
                    device_id=device_id,
                    metric="CONDENSATION_MARGIN",
                    observed_value=condensation_margin,
                    threshold_value=0.5,
                    target_audience="FARMER"
                )
                if alert:
                    triggered_alerts.append(alert)
            elif condensation_margin > 1.0:
                await AlertService.auto_resolve_alerts(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_types=["CONDENSATION_MOLD_HAZARD"],
                    device_id=device_id
                )

        # 4. Thermal Stratification (> 3.0°C differential across spatial probes)
        if stratification is not None:
            if stratification > 3.0:
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="THERMAL_STRATIFICATION_HIGH",
                    severity="WARNING",
                    title=f"Severe Thermal Stratification in {zone.zone_name}",
                    message=(
                        f"Vertical temperature gradient across multi-probe array is {stratification:.1f}°C "
                        f"(safe limit: 3.0°C). Airflow stagnation detected; check evaporator fans "
                        f"or check whether produce pallets are blocking air circulation vents."
                    ),
                    device_id=device_id,
                    metric="STRATIFICATION",
                    observed_value=stratification,
                    threshold_value=3.0,
                    target_audience="OPERATOR"
                )
                if alert:
                    triggered_alerts.append(alert)
            elif stratification <= 2.0:
                await AlertService.auto_resolve_alerts(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_types=["THERMAL_STRATIFICATION_HIGH"],
                    device_id=device_id
                )

        # 5. Door Ajar Alert
        if door_open is True:
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="DOOR_AJAR_WARNING",
                severity="WARNING",
                title=f"Chamber Door Left Open in {zone.zone_name}",
                message=(
                    f"Cold storage chamber door is reported OPEN. Ingress of warm ambient air "
                    f"will cause refrigeration loss and evaporator coil icing."
                ),
                device_id=device_id,
                target_audience="ALL"
            )
            if alert:
                triggered_alerts.append(alert)
        elif door_open is False:
            await AlertService.auto_resolve_alerts(
                db=db,
                zone_id=zone.zone_id,
                alert_types=["DOOR_AJAR_WARNING"],
                device_id=device_id
            )

        # 6. Ineffective Cooling / Thermal Runaway
        if (
            compressor_on is True
            and temperature is not None
            and zone.temp_max is not None
            and temperature > (zone.temp_max + 1.5)
        ):
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="COOLING_INEFFECTIVE",
                severity="CRITICAL",
                title=f"Refrigeration Ineffective / Chamber Warming in {zone.zone_name}",
                message=(
                    f"Compressor is running, but chamber temperature is {temperature:.1f}°C "
                    f"(safe max is {zone.temp_max:.1f}°C). Possible refrigerant leak, "
                    f"heavily iced evaporator, or compressor motor failure."
                ),
                device_id=device_id,
                metric="TEMPERATURE",
                observed_value=temperature,
                threshold_value=zone.temp_max,
                target_audience="ALL"
            )
            if alert:
                triggered_alerts.append(alert)

        # 7. VOC / Respiration Gas Spike
        if voc_index is not None and voc_index > 250.0:
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="VOC_SPIKE_HIGH",
                severity="WARNING",
                title=f"Elevated VOC / Ethylene Levels in {zone.zone_name}",
                message=(
                    f"VOC index reached {voc_index:.0f}. Accelerated crop respiration or "
                    f"ethylene gas accumulation detected. Sensitive produce will experience rapid decay."
                ),
                device_id=device_id,
                metric="VOC_INDEX",
                observed_value=voc_index,
                threshold_value=250.0,
                target_audience="FARMER"
            )
            if alert:
                triggered_alerts.append(alert)

        # 8. Remaining Shelf Life Depletion
        if remaining_shelf_life_h is not None and 0.0 < remaining_shelf_life_h < 48.0:
            severity = "CRITICAL" if remaining_shelf_life_h < 24.0 else "WARNING"
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="SHELF_LIFE_CRITICAL",
                severity=severity,
                title=f"Produce Shelf Life Expiring in {zone.zone_name}",
                message=(
                    f"Estimated remaining shelf life for stored {zone.current_crop_type} is "
                    f"{remaining_shelf_life_h:.1f} hours ({remaining_shelf_life_h/24.0:.1f} days). "
                    f"Urgent dispatch to local market recommended to avoid postharvest loss."
                ),
                device_id=device_id,
                metric="SHELF_LIFE_HOURS",
                observed_value=remaining_shelf_life_h,
                threshold_value=48.0,
                target_audience="FARMER"
            )
            if alert:
                triggered_alerts.append(alert)

        return triggered_alerts

    @staticmethod
    async def evaluate_power_transition(
        db: AsyncSession,
        zone: Zone,
        device: Device,
        current_source: Optional[str],
        previous_source: Optional[str],
        battery_soc: Optional[float],
        battery_v: Optional[float],
        autonomy_h: Optional[float],
    ) -> List[Alert]:
        """
        Detect and alert on power source transitions and battery health:
        1. GRID / SOLAR -> BATTERY (Power cut / outage alert)
        2. BATTERY -> GRID / SOLAR (Mains power restored)
        3. Low Battery warning (SoC <= 30% or autonomy < 3.0h)
        4. Critical Battery warning (SoC <= 15% or autonomy < 1.0h)
        5. Total blackout (power_source == 'NONE')
        """
        alerts: List[Alert] = []
        if not current_source:
            return alerts

        # 1. Transition: GRID / SOLAR -> BATTERY (Grid failure)
        if previous_source in ("GRID", "SOLAR") and current_source == "BATTERY":
            autonomy_str = f"{autonomy_h:.1f}h" if autonomy_h is not None else "unknown"
            soc_str = f"{battery_soc:.0f}%" if battery_soc is not None else "unknown"
            is_urgent = (autonomy_h is not None and autonomy_h < 2.0) or (battery_soc is not None and battery_soc < 25.0)
            severity = "CRITICAL" if is_urgent else "WARNING"

            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="POWER_GRID_LOST",
                severity=severity,
                title=f"Power Outage: Switched to Battery Backup at {device.device_id}",
                message=(
                    f"Primary {previous_source} power failed. Chamber {zone.zone_name} has transitioned "
                    f"to BATTERY power. Current Battery SoC: {soc_str}, Estimated autonomy: {autonomy_str}."
                ),
                device_id=device.device_id,
                metric="BATTERY_SOC",
                observed_value=battery_soc,
                target_audience="ALL"
            )
            if alert:
                alerts.append(alert)

        # 2. Transition: BATTERY -> GRID / SOLAR (Power restored)
        elif previous_source == "BATTERY" and current_source in ("GRID", "SOLAR"):
            # Auto-resolve existing power failure / battery alerts
            await AlertService.auto_resolve_alerts(
                db=db,
                zone_id=zone.zone_id,
                alert_types=["POWER_GRID_LOST", "POWER_FAILURE", "POWER_BATTERY_LOW", "POWER_BATTERY_CRITICAL", "POWER_BLACKOUT_CRITICAL"],
                device_id=device.device_id
            )
            soc_str = f"{battery_soc:.0f}%" if battery_soc is not None else "unknown"
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="POWER_RESTORED",
                severity="INFO",
                title=f"Power Restored: Operating on {current_source} at {device.device_id}",
                message=(
                    f"Primary power restored to {current_source}. Battery is recharging "
                    f"(level: {soc_str}). Continuous cooling is secured."
                ),
                device_id=device.device_id,
                metric="BATTERY_SOC",
                observed_value=battery_soc,
                target_audience="ALL"
            )
            if alert:
                alerts.append(alert)

        # 3. Battery Low & Critical monitoring while on Battery
        if current_source == "BATTERY" and battery_soc is not None:
            if battery_soc <= 15.0 or (autonomy_h is not None and autonomy_h < 1.0):
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="POWER_BATTERY_CRITICAL",
                    severity="CRITICAL",
                    title=f"CRITICAL: Battery Near Depletion at {device.device_id}",
                    message=(
                        f"Battery SoC is critically low at {battery_soc:.1f}% ({battery_v or 0:.1f}V), "
                        f"cooling autonomy under {autonomy_h or 0:.1f}h. Immediate generator start "
                        f"or grid supply required before cooling system shuts down."
                    ),
                    device_id=device.device_id,
                    metric="BATTERY_SOC",
                    observed_value=battery_soc,
                    threshold_value=15.0,
                    target_audience="ALL"
                )
                if alert:
                    alerts.append(alert)
            elif battery_soc <= 30.0 or (autonomy_h is not None and autonomy_h < 3.0):
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="POWER_BATTERY_LOW",
                    severity="WARNING",
                    title=f"Low Battery Warning at {device.device_id}",
                    message=(
                        f"Battery SoC has dropped to {battery_soc:.1f}%, remaining autonomy: "
                        f"{autonomy_h or 0:.1f} hours. Monitor cold storage power supply."
                    ),
                    device_id=device.device_id,
                    metric="BATTERY_SOC",
                    observed_value=battery_soc,
                    threshold_value=30.0,
                    target_audience="OPERATOR"
                )
                if alert:
                    alerts.append(alert)

        # 4. Total Blackout (power_source == 'NONE')
        if current_source == "NONE":
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="POWER_BLACKOUT_CRITICAL",
                severity="CRITICAL",
                title=f"Total Power Blackout at {device.device_id}",
                message=(
                    f"No active power source (GRID, SOLAR, and BATTERY exhausted). "
                    f"Cold storage chamber {zone.zone_name} has lost all power."
                ),
                device_id=device.device_id,
                target_audience="ALL"
            )
            if alert:
                alerts.append(alert)

        return alerts

    @staticmethod
    async def evaluate_sensor_health(
        db: AsyncSession,
        zone: Zone,
        device: Optional[Device],
        temperature: Optional[float],
        humidity: Optional[float],
        co2: Optional[float],
        air_sensor_ok: Optional[bool] = None,
        probe_temps: Optional[List[float]] = None,
        probe_status: Optional[List[str]] = None,
        edge_status: Optional[str] = None,
        sensor_dict: Optional[Dict[str, Sensor]] = None,
    ) -> List[Alert]:
        """
        Detect sensor damage, probe disconnection, and hardware faults:
        1. 1-Wire DS18B20 digital disconnect code (-127.0°C) or reset error (85.0°C)
        2. Physically impossible readings (temperature < -30°C or > 60°C, RH <= 0% or > 100%, CO2 < 100)
        3. Edge hardware status flags (air_sensor_ok=False, probe_status=['FAULT', ...])
        4. Multi-probe consensus spatial divergence (single broken probe in array)
        """
        alerts: List[Alert] = []
        dev_id = device.device_id if device else None

        # 1. Temperature Sensor Disconnect & Error Codes
        if temperature is not None:
            temp_sensor = sensor_dict.get("TEMPERATURE") if sensor_dict else None

            # -127.0°C is the universal DS18B20 1-Wire bus pull-up / wire severed code
            if temperature <= -100.0:
                if temp_sensor:
                    temp_sensor.status = "FAULT"
                    temp_sensor.last_fault = f"1-Wire disconnected ({temperature:.1f}°C error code)"
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="SENSOR_DISCONNECTED",
                    severity="CRITICAL",
                    title=f"Temperature Sensor Disconnected in {zone.zone_name}",
                    message=(
                        f"Temperature sensor reported {temperature:.1f}°C (DS18B20 1-Wire disconnect error). "
                        f"Probe cable severed, disconnected terminal, or sensor missing on device {dev_id}."
                    ),
                    device_id=dev_id,
                    sensor_id=temp_sensor.sensor_id if temp_sensor else None,
                    metric="TEMPERATURE",
                    observed_value=temperature,
                    target_audience="OPERATOR"
                )
                if alert:
                    alerts.append(alert)

            # 85.0°C is the power-on reset state error of DS18B20
            elif temperature == 85.0:
                if temp_sensor:
                    temp_sensor.status = "FAULT"
                    temp_sensor.last_fault = "DS18B20 power-on reset default (85°C error)"
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="SENSOR_FAULT",
                    severity="WARNING",
                    title=f"Temperature Sensor Reset Error in {zone.zone_name}",
                    message=(
                        f"Sensor reported exactly 85.0°C (DS18B20 power-on default). "
                        f"Read request occurred before conversion completed or power glitch on 1-Wire bus."
                    ),
                    device_id=dev_id,
                    sensor_id=temp_sensor.sensor_id if temp_sensor else None,
                    metric="TEMPERATURE",
                    observed_value=temperature,
                    target_audience="OPERATOR"
                )
                if alert:
                    alerts.append(alert)

            # Physically impossible temperature in operating cold storage
            elif temperature < -30.0 or temperature > 60.0:
                if temp_sensor:
                    temp_sensor.status = "FAULT"
                    temp_sensor.last_fault = f"Physically impossible reading: {temperature:.1f}°C"
                alert = await AlertService.raise_system_alert(
                    db=db,
                    zone_id=zone.zone_id,
                    alert_type="SENSOR_OUT_OF_BOUNDS",
                    severity="CRITICAL",
                    title=f"Impossible Temperature Reading in {zone.zone_name}",
                    message=(
                        f"Sensor reported {temperature:.1f}°C, which is physically impossible for "
                        f"a commercial cold room. Electrical short circuit or broken sensing element."
                    ),
                    device_id=dev_id,
                    sensor_id=temp_sensor.sensor_id if temp_sensor else None,
                    metric="TEMPERATURE",
                    observed_value=temperature,
                    target_audience="OPERATOR"
                )
                if alert:
                    alerts.append(alert)

        # 2. Relative Humidity Physical Bounds (corroded or flooded sensor)
        if humidity is not None and (humidity <= 0.0 or humidity > 100.0):
            rh_sensor = sensor_dict.get("HUMIDITY") if sensor_dict else None
            if rh_sensor:
                rh_sensor.status = "FAULT"
                rh_sensor.last_fault = f"Out of bounds RH reading: {humidity:.1f}%"
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="SENSOR_OUT_OF_BOUNDS",
                severity="WARNING",
                title=f"Humidity Sensor Malfunction in {zone.zone_name}",
                message=(
                    f"Humidity reading {humidity:.1f}% is outside physical 1-100% RH boundaries. "
                    f"Sensing polymer contaminated, flooded with condensed water, or defective."
                ),
                device_id=dev_id,
                sensor_id=rh_sensor.sensor_id if rh_sensor else None,
                metric="HUMIDITY",
                observed_value=humidity,
                target_audience="OPERATOR"
            )
            if alert:
                alerts.append(alert)

        # 3. CO2 Sensor Physical Bounds (NDIR lamp / optical failure)
        if co2 is not None and (co2 < 100.0 or co2 > 30000.0):
            co2_sensor = sensor_dict.get("CO2") if sensor_dict else None
            if co2_sensor:
                co2_sensor.status = "FAULT"
                co2_sensor.last_fault = f"Out of bounds CO2 reading: {co2:.0f}ppm"
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="SENSOR_OUT_OF_BOUNDS",
                severity="WARNING",
                title=f"CO2 Sensor Failure in {zone.zone_name}",
                message=(
                    f"CO2 reading {co2:.0f} ppm is outside atmospheric limits (minimum ~380 ppm). "
                    f"NDIR optical chamber clogged, mirror dirty, or IR lamp failed."
                ),
                device_id=dev_id,
                sensor_id=co2_sensor.sensor_id if co2_sensor else None,
                metric="CO2",
                observed_value=co2,
                target_audience="OPERATOR"
            )
            if alert:
                alerts.append(alert)

        # 4. Edge Hardware Status Flags
        if air_sensor_ok is False:
            alert = await AlertService.raise_system_alert(
                db=db,
                zone_id=zone.zone_id,
                alert_type="SENSOR_HARDWARE_FAULT",
                severity="CRITICAL",
                title=f"Air Sensor I2C Bus Fault in {zone.zone_name}",
                message=(
                    f"IoT edge node {dev_id} reported hardware communication failure (air_sensor_ok=False). "
                    f"I2C bus lockup or sensor hardware power loss."
                ),
                device_id=dev_id,
                target_audience="OPERATOR"
            )
            if alert:
                alerts.append(alert)

        # 5. Multi-Probe Status Array (probe_status: ["OK", "FAULT", ...])
        if probe_status:
            for idx, p_stat in enumerate(probe_status):
                if p_stat and p_stat.upper() not in ("OK", "NORMAL", "HEALTHY"):
                    alert = await AlertService.raise_system_alert(
                        db=db,
                        zone_id=zone.zone_id,
                        alert_type=f"PROBE_{idx+1}_FAULT",
                        severity="WARNING",
                        title=f"Temperature Probe #{idx+1} Fault in {zone.zone_name}",
                        message=(
                            f"Multi-probe array sensor #{idx+1} on node {dev_id} reported hardware status: '{p_stat}'. "
                            f"Check probe wiring and connector terminal."
                        ),
                        device_id=dev_id,
                        target_audience="OPERATOR"
                    )
                    if alert:
                        alerts.append(alert)

        # 6. Multi-Probe Consensus Spatial Divergence (detecting rogue / damaged probe in array)
        if probe_temps and len(probe_temps) >= 3:
            # Clean values: filter out disconnect codes (<= -100 or >= 80)
            valid_probes = [(i, val) for i, val in enumerate(probe_temps) if -30.0 <= val <= 60.0]
            if len(valid_probes) >= 3:
                vals = sorted([v for _, v in valid_probes])
                median_temp = vals[len(vals) // 2]
                for p_idx, p_val in valid_probes:
                    deviation = abs(p_val - median_temp)
                    # If single probe deviates by > 6.0°C from chamber median while others agree
                    if deviation > 6.0:
                        alert = await AlertService.raise_system_alert(
                            db=db,
                            zone_id=zone.zone_id,
                            alert_type=f"PROBE_{p_idx+1}_MALFUNCTION",
                            severity="WARNING",
                            title=f"Probe #{p_idx+1} Anomaly Detected in {zone.zone_name}",
                            message=(
                                f"Probe #{p_idx+1} reading ({p_val:.1f}°C) deviated by {deviation:.1f}°C "
                                f"from chamber median ({median_temp:.1f}°C). Probe damaged, unseated, or loose."
                            ),
                            device_id=dev_id,
                            metric="PROBE_TEMPERATURE",
                            observed_value=p_val,
                            threshold_value=median_temp,
                            target_audience="OPERATOR"
                        )
                        if alert:
                            alerts.append(alert)

        return alerts

    @staticmethod
    async def auto_resolve_alerts(
        db: AsyncSession,
        zone_id: Optional[str],
        alert_types: List[str],
        device_id: Optional[str] = None,
    ) -> int:
        """
        Auto-resolve active alerts when safe operating conditions are restored.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        query = select(Alert).where(
            and_(
                Alert.status == "ACTIVE",
                Alert.alert_type.in_(alert_types)
            )
        )
        if zone_id:
            query = query.where(Alert.zone_id == zone_id)
        if device_id:
            query = query.where(Alert.device_id == device_id)

        result = await db.execute(query)
        active_alerts = result.scalars().all()
        for alert in active_alerts:
            alert.status = "RESOLVED"
            alert.auto_resolved_at = now
            alert.resolved_at = now

        # If zone has no remaining active CRITICAL or WARNING alerts, set status back to OPTIMAL
        if zone_id:
            zone = await db.get(Zone, zone_id)
            if zone:
                remaining_q = select(Alert).where(
                    and_(
                        Alert.zone_id == zone_id,
                        Alert.status == "ACTIVE"
                    )
                )
                rem_alerts = (await db.execute(remaining_q)).scalars().all()
                if not rem_alerts:
                    zone.status = "OPTIMAL"
                elif any(a.severity == "CRITICAL" for a in rem_alerts):
                    zone.status = "CRITICAL"
                else:
                    zone.status = "WARNING"

        return len(active_alerts)

    @staticmethod
    async def raise_system_alert(
        db: AsyncSession,
        zone_id: Optional[str],
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        device_id: Optional[str] = None,
        sensor_id: Optional[str] = None,
        metric: Optional[str] = None,
        observed_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        target_audience: str = "ALL",  # 'FARMER', 'OPERATOR', 'ALL'
    ) -> Optional[Alert]:
        """
        Create a debounced system alert with distributed locking and recipient notification.
        """
        zone = await db.get(Zone, zone_id) if zone_id else None

        # 1. Distributed Redis / memory lock debounce
        lock_key = zone_id or device_id or "system"
        lock_acquired = await cache_service.acquire_alert_lock(
            zone_id=lock_key,
            alert_type=alert_type,
            ttl_seconds=settings.ALERT_DEBOUNCE_MINUTES * 60,
        )
        if not lock_acquired:
            return None

        # 2. Database active duplicate suppression
        debounce_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=settings.ALERT_DEBOUNCE_MINUTES)
        conds = [
            Alert.alert_type == alert_type,
            Alert.status == "ACTIVE",
            Alert.created_at >= debounce_cutoff
        ]
        if zone_id:
            conds.append(Alert.zone_id == zone_id)
        elif device_id:
            conds.append(Alert.device_id == device_id)

        existing = (await db.execute(select(Alert).where(and_(*conds)))).scalars().first()
        if existing:
            return None

        # 3. Create Alert Record
        alert = Alert(
            zone_id=zone_id or (zone.zone_id if zone else None),
            device_id=device_id,
            sensor_id=sensor_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            status="ACTIVE",
            is_farmer_notified=False,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            metric=metric,
            observed_value=observed_value,
            threshold_value=threshold_value,
        )
        db.add(alert)
        await db.flush()

        # Update Zone status
        if zone:
            if severity == "CRITICAL":
                zone.status = "CRITICAL"
            elif zone.status != "CRITICAL" and severity == "WARNING":
                zone.status = "WARNING"

        # 4. Dispatch Notifications
        await AlertService.dispatch_notifications(db, zone, alert, target_audience=target_audience)
        return alert

    @staticmethod
    async def dispatch_notifications(
        db: AsyncSession,
        zone: Optional[Zone],
        alert: Alert,
        target_audience: str = "ALL"
    ):
        """
        Dispatches SMS/WhatsApp alerts with targeted recipient filtering:
        - 'FARMER': Farmers with produce stored in the affected zone.
        - 'OPERATOR': Facility operators and maintenance engineers.
        - 'ALL': Both farmers and operators.
        """
        recipients: List[User] = []

        # Query Farmers who have batches in this zone
        if target_audience in ("FARMER", "ALL") and zone:
            batch_query = (
                select(User)
                .join(CropBatch, CropBatch.farmer_id == User.user_id)
                .where(CropBatch.zone_id == zone.zone_id)
                .distinct()
            )
            farmers = (await db.execute(batch_query)).scalars().all()
            recipients.extend(farmers)

        # Query Facility Operators & Admins
        if target_audience in ("OPERATOR", "ALL"):
            operator_query = select(User).where(User.role.in_(["OPERATOR", "ADMIN"]))
            operators = (await db.execute(operator_query)).scalars().all()
            for op in operators:
                if op.user_id not in [r.user_id for r in recipients]:
                    recipients.append(op)

        chamber_info = f"Chamber: {zone.zone_name} | Produce: {zone.current_crop_type}" if zone else f"Device: {alert.device_id or 'Central Unit'}"

        for recipient in recipients:
            role_label = "Operator" if recipient.role in ("OPERATOR", "ADMIN") else "Farmer"
            notification_content = (
                f"🚨 [Cold Storage Alert - {alert.severity}]\n"
                f"Dear {recipient.name} ({role_label}),\n"
                f"{alert.title}\n"
                f"{alert.message}\n"
                f"{chamber_info}\n"
                f"Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"Action: Verify chamber conditions & system status."
            )

            delivery_status = "SENT"
            if recipient.preferred_alert_channel in ("SMS", "WHATSAPP"):
                sms_res = await smschef_service.send_sms(
                    phone_number=recipient.phone_number,
                    message=notification_content
                )
                if sms_res.get("status") == "FAILED":
                    delivery_status = "FAILED"

            if settings.ENABLE_SMS_SIMULATION:
                logger.warning(
                    f"\n================ [{role_label.upper()} NOTIFICATION DISPATCHED] ================\n"
                    f"To: {recipient.name} ({recipient.phone_number}) via {recipient.preferred_alert_channel}\n"
                    f"{notification_content}\n"
                    f"==================================================================\n"
                )

            notification = AlertNotification(
                alert_id=alert.alert_id,
                farmer_id=recipient.user_id,
                channel=recipient.preferred_alert_channel,
                recipient=recipient.phone_number if recipient.preferred_alert_channel in ("SMS", "WHATSAPP") else (recipient.email or recipient.phone_number),
                content=notification_content,
                delivery_status=delivery_status,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            db.add(notification)

        alert.is_farmer_notified = True


alert_service = AlertService()
