import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_id = Column(String(36), ForeignKey("sensors.sensor_id", ondelete="SET NULL"), nullable=True)
    alert_type = Column(String(50), nullable=False) # 'TEMP_SPIKE', 'CO2_HAZARD', 'SPOILAGE_RISK', 'HUMIDITY_LOW'
    severity = Column(String(20), default="WARNING") # 'INFO', 'WARNING', 'CRITICAL'
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="ACTIVE") # 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'
    is_farmer_notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    zone = relationship("Zone", back_populates="alerts")
    sensor = relationship("Sensor")
    notifications = relationship("AlertNotification", back_populates="alert", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Alert(type='{self.alert_type}', severity='{self.severity}', status='{self.status}')>"

class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    notification_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String(36), ForeignKey("alerts.alert_id", ondelete="CASCADE"), nullable=False)
    farmer_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(20), default="SMS") # 'SMS', 'WHATSAPP', 'EMAIL'
    recipient = Column(String(100), nullable=False) # Phone number or email
    content = Column(Text, nullable=False)
    delivery_status = Column(String(20), default="SENT") # 'PENDING', 'SENT', 'FAILED'
    sent_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    alert = relationship("Alert", back_populates="notifications")
    farmer = relationship("User")

