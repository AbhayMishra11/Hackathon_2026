import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class Sensor(Base):
    __tablename__ = "sensors"

    sensor_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_type = Column(String(50), nullable=False) # 'TEMPERATURE', 'HUMIDITY', 'CO2', 'LIGHT'
    unit = Column(String(20), nullable=False) # '°C', '%', 'ppm', 'Lux'
    current_reading = Column(Float, default=0.0)
    base_reading = Column(Float, default=0.0) # Lower safe threshold or baseline
    max_reading = Column(Float, default=100.0) # Upper safe threshold
    status = Column(String(20), default="ACTIVE") # 'ACTIVE', 'FAULT', 'OFFLINE'
    timestamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    zone = relationship("Zone", back_populates="sensors")
    telemetry_logs = relationship("SensorTelemetryLog", back_populates="sensor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Sensor(type='{self.sensor_type}', reading={self.current_reading}{self.unit}, status='{self.status}')>"

