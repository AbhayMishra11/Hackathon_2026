import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import inspect, select, text

from app.db.database import Base, engine, AsyncSessionLocal
from app.models.user import User
from app.models.cold_storage import ColdStorage, Zone
from app.models.sensor import Sensor
from app.models.crop_batch import CropBatch
from app.models.alert import Alert
from app.models.device import Device
from app.models.telemetry import TelemetryFrame
from app.services.shelf_life_service import ShelfLifeState

logger = logging.getLogger("coldstorage.init_db")


async def _additive_schema_migration(conn):
    """Add NER columns to an existing development database without dropping data."""
    additions = {
        "zones": {
            "chilling_injury_c": "FLOAT", "freezing_point_c": "FLOAT",
            "setpoint_c": "FLOAT DEFAULT 1.0", "setpoint_rh": "FLOAT DEFAULT 92.0",
            "hysteresis_c": "FLOAT DEFAULT 0.75", "mode": "VARCHAR(20) DEFAULT 'AUTO'",
            "co2_ppm_max": "FLOAT DEFAULT 5000.0", "co2_ppm_critical": "FLOAT DEFAULT 10000.0",
            "free_volume_m3": "FLOAT DEFAULT 3.0",
        },
        "sensors": {"channel": "VARCHAR(20)", "hw_model": "VARCHAR(40)", "hw_address": "VARCHAR(40)", "device_id": "VARCHAR(64)", "last_fault": "VARCHAR(80)"},
        "alerts": {"metric": "VARCHAR(40)", "observed_value": "FLOAT", "threshold_value": "FLOAT", "device_id": "VARCHAR(64)", "auto_resolved_at": "TIMESTAMP"},
    }

    def migrate(sync_conn):
        inspector = inspect(sync_conn)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))

    await conn.run_sync(migrate)

async def init_database():
    """Create all database tables and seed initial cold storage facilities, zones, and sensors."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _additive_schema_migration(conn)
    logger.info("Database tables initialized successfully.")

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        facility_check = await session.execute(select(ColdStorage))
        if facility_check.scalars().first():
            # Bring the original demo rows onto the NER storage bands.
            bands = {
                "Cabbage": (0.0, 2.0, 95.0, 100.0, 5000.0, -0.9, 0.0, 1.0),
                "French bean": (5.0, 7.5, 92.0, 97.0, 4000.0, 5.0, 0.0, 6.0),
                "Leafy greens": (0.0, 2.0, 95.0, 100.0, 3000.0, -0.4, -0.4, 1.0),
                "Tomato": (12.5, 15.0, 90.0, 95.0, 5000.0, 10.0, 0.0, 13.5),
            }
            zone_crops = {
                "Zone A - Citrus Chamber": "Cabbage",
                "Zone B - Banana Chamber": "French bean",
                "Zone C - Tomato Chamber": "Leafy greens",
                "Zone D - Pineapple Chamber": "Tomato",
                "Zone A - Cabbage Chamber": "Cabbage",
                "Zone B - French Bean Chamber": "French bean",
                "Zone C - Leafy Greens Chamber": "Leafy greens",
                "Zone D - Tomato Chamber": "Tomato",
            }
            renamed_zones = {
                "Zone A - Citrus Chamber": "Zone A - Cabbage Chamber",
                "Zone B - Banana Chamber": "Zone B - French Bean Chamber",
                "Zone C - Tomato Chamber": "Zone C - Leafy Greens Chamber",
                "Zone D - Pineapple Chamber": "Zone D - Tomato Chamber",
            }
            for zone in (await session.execute(select(Zone))).scalars().all():
                zone.zone_name = renamed_zones.get(zone.zone_name, zone.zone_name)
                zone.current_crop_type = zone_crops.get(zone.zone_name, zone.current_crop_type)
                band = bands.get(zone.current_crop_type)
                if band:
                    zone.temp_min, zone.temp_max, zone.humidity_min, zone.humidity_max, zone.co2_max = band[:5]
                    zone.chilling_injury_c, zone.freezing_point_c, zone.setpoint_c = band[5:]
                    zone.setpoint_rh = (zone.humidity_min + zone.humidity_max) / 2
                    zone.co2_ppm_max, zone.co2_ppm_critical = zone.co2_max, 10000.0
                # Synchronize matching crop_batch fruit_type
                batches = (await session.execute(select(CropBatch).where(CropBatch.zone_id == zone.zone_id))).scalars().all()
                for batch in batches:
                    batch.fruit_type = zone.current_crop_type
            await session.commit()
            logger.info("Database already seeded with initial cold storage configuration.")
            return

        # 1. Create Default Cold Storage Facility
        storage = ColdStorage(
            name="Krishi Cold Chain Central Hub",
            location="Warehouse #4, Agricultural Logistics Park",
            total_capacity_tons=500.0
        )
        session.add(storage)
        await session.flush()

        # 2. Create Default Farmers
        farmer1 = User(
            name="Ramesh Patel",
            phone_number="+919876543210",
            email="ramesh.patel@agri.com",
            role="FARMER",
            preferred_alert_channel="SMS"
        )
        farmer2 = User(
            name="Suresh Kumar",
            phone_number="+919812345678",
            email="suresh.kumar@agri.com",
            role="FARMER",
            preferred_alert_channel="WHATSAPP"
        )
        session.add_all([farmer1, farmer2])
        await session.flush()

        # 3. Create Default Chambers / Zones with custom thresholds
        zone_configs = [
            {
                "name": "Zone A - Cabbage Chamber",
                "crop": "Cabbage",
                "capacity": 10000.0,
                "temp_min": 0.0, "temp_max": 2.0,
                "humid_min": 95.0, "humid_max": 100.0,
                "co2_max": 5000.0, "light_max": 12.0,
                "farmer": farmer1,
                "batch_qty": 3500.0
            },
            {
                "name": "Zone B - French Bean Chamber",
                "crop": "French bean",
                "capacity": 8000.0,
                "temp_min": 5.0, "temp_max": 7.5,
                "humid_min": 92.0, "humid_max": 97.0,
                "co2_max": 4000.0, "light_max": 22.0,
                "farmer": farmer2,
                "batch_qty": 4200.0
            },
            {
                "name": "Zone C - Leafy Greens Chamber",
                "crop": "Leafy greens",
                "capacity": 12000.0,
                "temp_min": 0.0, "temp_max": 2.0,
                "humid_min": 95.0, "humid_max": 100.0,
                "co2_max": 3000.0, "light_max": 18.0,
                "farmer": farmer1,
                "batch_qty": 5000.0
            },
            {
                "name": "Zone D - Tomato Chamber",
                "crop": "Tomato",
                "capacity": 9000.0,
                "temp_min": 12.5, "temp_max": 15.0,
                "humid_min": 90.0, "humid_max": 95.0,
                "co2_max": 5000.0, "light_max": 14.5,
                "farmer": farmer2,
                "batch_qty": 2800.0
            }
        ]

        for z_cfg in zone_configs:
            zone = Zone(
                storage_id=storage.storage_id,
                zone_name=z_cfg["name"],
                current_crop_type=z_cfg["crop"],
                capacity_kg=z_cfg["capacity"],
                temp_min=z_cfg["temp_min"],
                temp_max=z_cfg["temp_max"],
                humidity_min=z_cfg["humid_min"],
                humidity_max=z_cfg["humid_max"],
                co2_max=z_cfg["co2_max"],
                light_max=z_cfg["light_max"],
                status="OPTIMAL"
            )
            session.add(zone)
            await session.flush()

            # Create 4 Standard IoT Sensors per Zone (Temperature, Humidity, CO2, Light)
            sensors = [
                Sensor(
                    zone_id=zone.zone_id,
                    sensor_type="TEMPERATURE",
                    unit="°C",
                    current_reading=z_cfg["temp_min"] + 0.8,
                    base_reading=z_cfg["temp_min"],
                    max_reading=z_cfg["temp_max"],
                    status="ACTIVE"
                ),
                Sensor(
                    zone_id=zone.zone_id,
                    sensor_type="HUMIDITY",
                    unit="%",
                    current_reading=91.0,
                    base_reading=z_cfg["humid_min"],
                    max_reading=z_cfg["humid_max"],
                    status="ACTIVE"
                ),
                Sensor(
                    zone_id=zone.zone_id,
                    sensor_type="CO2",
                    unit="ppm",
                    current_reading=315.0,
                    base_reading=0.0,
                    max_reading=z_cfg["co2_max"],
                    status="ACTIVE"
                ),
                Sensor(
                    zone_id=zone.zone_id,
                    sensor_type="LIGHT",
                    unit="Lux",
                    current_reading=8.5,
                    base_reading=0.0,
                    max_reading=z_cfg["light_max"],
                    status="ACTIVE"
                )
            ]
            session.add_all(sensors)

            # Create farmer produce batch
            batch = CropBatch(
                zone_id=zone.zone_id,
                farmer_id=z_cfg["farmer"].user_id,
                fruit_type=z_cfg["crop"],
                quantity_kg=z_cfg["batch_qty"],
                expected_shelf_life_days=30,
                current_health_status="Good"
            )
            session.add(batch)

        await session.commit()
        logger.info("Cold Storage seed data populated successfully.")

