import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import Base, engine, AsyncSessionLocal
from app.models.user import User
from app.models.cold_storage import ColdStorage, Zone
from app.models.sensor import Sensor
from app.models.crop_batch import CropBatch
from app.models.alert import Alert

logger = logging.getLogger("coldstorage.init_db")

async def init_database():
    """Create all database tables and seed initial cold storage facilities, zones, and sensors."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        facility_check = await session.execute(select(ColdStorage))
        if facility_check.scalars().first():
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
                "name": "Zone A - Citrus Chamber",
                "crop": "Orange",
                "capacity": 10000.0,
                "temp_min": 21.0, "temp_max": 23.5,
                "humid_min": 85.0, "humid_max": 95.0,
                "co2_max": 380.0, "light_max": 12.0,
                "farmer": farmer1,
                "batch_qty": 3500.0
            },
            {
                "name": "Zone B - Banana Chamber",
                "crop": "Banana",
                "capacity": 8000.0,
                "temp_min": 24.0, "temp_max": 26.5,
                "humid_min": 85.0, "humid_max": 95.0,
                "co2_max": 360.0, "light_max": 22.0,
                "farmer": farmer2,
                "batch_qty": 4200.0
            },
            {
                "name": "Zone C - Tomato Chamber",
                "crop": "Tomato",
                "capacity": 12000.0,
                "temp_min": 22.0, "temp_max": 24.5,
                "humid_min": 75.0, "humid_max": 93.0,
                "co2_max": 360.0, "light_max": 18.0,
                "farmer": farmer1,
                "batch_qty": 5000.0
            },
            {
                "name": "Zone D - Pineapple Chamber",
                "crop": "Pineapple",
                "capacity": 9000.0,
                "temp_min": 22.0, "temp_max": 24.5,
                "humid_min": 80.0, "humid_max": 95.0,
                "co2_max": 380.0, "light_max": 14.5,
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

