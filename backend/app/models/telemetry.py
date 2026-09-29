from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base

class SensorTelemetryLog(Base):
    __tablename__ = "sensor_telemetry_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String(36), ForeignKey("sensors.sensor_id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_type = Column(String(50), nullable=False)
    reading_value = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    # Relationships
    sensor = relationship("Sensor", back_populates="telemetry_logs")

    def __repr__(self):
        return f"<TelemetryLog(sensor='{self.sensor_type}', val={self.reading_value}, time='{self.recorded_at}')>"


class TelemetryFrame(Base):
    __tablename__ = "telemetry_frames"

    frame_id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), index=True, nullable=False)
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"), index=True, nullable=False)
    seq = Column(Integer, nullable=False)
    sampled_at = Column(DateTime, index=True, nullable=False)
    received_at = Column(DateTime, nullable=False)
    is_replay = Column(Boolean, default=False)

    air_temp_c = Column(Float)
    air_rh = Column(Float)
    surface_temp_c = Column(Float)
    ambient_temp_c = Column(Float)
    probe_temps = Column(JSON)
    probe_status = Column(JSON)
    co2_ppm = Column(Float)
    eco2_ppm = Column(Float)
    voc_index = Column(Float)
    lux = Column(Float)
    mass_kg = Column(Float)
    door_open = Column(Boolean, default=False)
    compressor_on = Column(Boolean, default=False)
    fan_on = Column(Boolean, default=False)
    mode = Column(String(20))
    power_source = Column(String(10))
    pv_power_w = Column(Float)
    battery_soc = Column(Float)
    battery_v = Column(Float)
    load_power_w = Column(Float)
    autonomy_hours = Column(Float)
    dew_point_c = Column(Float)
    vpd_kpa = Column(Float)
    abs_humidity_gm3 = Column(Float)
    condensation_margin_c = Column(Float)
    stratification_c = Column(Float)
    rssi = Column(Integer)
    firmware = Column(String(20))
    edge_status = Column(String(24))

    __table_args__ = (
        UniqueConstraint("device_id", "seq", name="uq_frame_device_seq"),
        Index("ix_frames_zone_time", "zone_id", "sampled_at"),
    )

