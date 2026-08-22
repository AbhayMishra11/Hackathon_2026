import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class ColdStorage(Base):
    __tablename__ = "cold_storages"

    storage_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(120), nullable=False)
    location = Column(String(255), nullable=False)
    total_capacity_tons = Column(Float, default=100.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    zones = relationship("Zone", back_populates="storage", cascade="all, delete-orphan")

class Zone(Base):
    __tablename__ = "zones"

    zone_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_id = Column(String(36), ForeignKey("cold_storages.storage_id", ondelete="CASCADE"), nullable=False)
    zone_name = Column(String(60), nullable=False) # e.g. "Zone A - Citrus Chamber"
    current_crop_type = Column(String(50), nullable=False) # 'Orange', 'Banana', 'Tomato', 'Pineapple'
    capacity_kg = Column(Float, default=5000.0)

    # Safe operating thresholds for the stored produce
    temp_min = Column(Float, default=21.0)
    temp_max = Column(Float, default=24.0)
    humidity_min = Column(Float, default=80.0)
    humidity_max = Column(Float, default=95.0)
    co2_max = Column(Float, default=380.0)
    light_max = Column(Float, default=20.0)

    status = Column(String(20), default="OPTIMAL") # 'OPTIMAL', 'WARNING', 'CRITICAL'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    storage = relationship("ColdStorage", back_populates="zones")
    sensors = relationship("Sensor", back_populates="zone", cascade="all, delete-orphan")
    batches = relationship("CropBatch", back_populates="zone", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="zone", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Zone(name='{self.zone_name}', crop='{self.current_crop_type}', status='{self.status}')>"

