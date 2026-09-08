from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from app.db.database import Base


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(64), primary_key=True)
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="SET NULL"), nullable=True)
    label = Column(String(120), nullable=True)
    location = Column(String(200), nullable=True)
    firmware = Column(String(20), nullable=True)
    last_seen_at = Column(DateTime, index=True, nullable=True)
    last_seq = Column(Integer, default=0)
    expected_interval_s = Column(Integer, default=30)
    offline_grace_s = Column(Integer, default=90)
    is_online = Column(Boolean, default=False)
    last_power_source = Column(String(10), nullable=True)
    last_battery_soc = Column(Float, nullable=True)
    last_temp_c = Column(Float, nullable=True)
    last_rssi = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)