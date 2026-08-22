import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    role = Column(String(20), default="FARMER") # 'FARMER', 'OPERATOR', 'ADMIN'
    preferred_alert_channel = Column(String(20), default="SMS") # 'SMS', 'WHATSAPP', 'EMAIL', 'PUSH'
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User(name='{self.name}', role='{self.role}', phone='{self.phone_number}')>"

