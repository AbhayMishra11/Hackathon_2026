import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class ColdStorage(Base):
    __tablename__ = "cold_storages"

    storage_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(120), nullable=False)
    location = Column(String(255), nullable=False)
    total_capacity_tons = Column(Float, default=100.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    zones = relationship("Zone", back_populates="storage", cascade="all, delete-orphan")

class Zone(Base):
    __tablename__ = "zones"

    zone_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_id = Column(String(36), ForeignKey("cold_storages.storage_id", ondelete="CASCADE"), nullable=False)
    zone_name = Column(String(60), nullable=False) # e.g. "Zone A - Citrus Chamber"
    current_crop_type = Column(String(50), nullable=False)
    capacity_kg = Column(Float, default=5000.0)

    # Safe operating thresholds for the stored produce
    temp_min = Column(Float, default=0.0)
    temp_max = Column(Float, default=2.0)
    humidity_min = Column(Float, default=95.0)
    humidity_max = Column(Float, default=100.0)
    co2_max = Column(Float, default=5000.0)
    light_max = Column(Float, default=20.0)

    chilling_injury_c = Column(Float, nullable=True)
    freezing_point_c = Column(Float, nullable=True)
    setpoint_c = Column(Float, default=1.0)
    setpoint_rh = Column(Float, default=97.0)
    hysteresis_c = Column(Float, default=0.75)
    mode = Column(String(20), default="AUTO")
    co2_ppm_max = Column(Float, default=5000.0)
    co2_ppm_critical = Column(Float, default=10000.0)
    free_volume_m3 = Column(Float, default=3.0)

    status = Column(String(20), default="OPTIMAL") # 'OPTIMAL', 'WARNING', 'CRITICAL'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    storage = relationship("ColdStorage", back_populates="zones")
    sensors = relationship("Sensor", back_populates="zone", cascade="all, delete-orphan")
    batches = relationship("CropBatch", back_populates="zone", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="zone", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Zone(name='{self.zone_name}', crop='{self.current_crop_type}', status='{self.status}')>"

