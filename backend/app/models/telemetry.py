from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class SensorTelemetryLog(Base):
    __tablename__ = "sensor_telemetry_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String(36), ForeignKey("sensors.sensor_id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_type = Column(String(50), nullable=False)
    reading_value = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    sensor = relationship("Sensor", back_populates="telemetry_logs")

    def __repr__(self):
        return f"<TelemetryLog(sensor='{self.sensor_type}', val={self.reading_value}, time='{self.recorded_at}')>"

