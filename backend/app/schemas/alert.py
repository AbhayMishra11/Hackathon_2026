from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AlertBase(BaseModel):
    zone_id: str
    sensor_id: Optional[str] = None
    alert_type: str
    severity: str = "WARNING"
    title: str
    message: str

class AlertCreate(AlertBase):
    pass

class AlertAcknowledge(BaseModel):
    status: str = "ACKNOWLEDGED" # 'ACKNOWLEDGED', 'RESOLVED'

class AlertNotificationResponse(BaseModel):
    notification_id: str
    alert_id: str
    farmer_id: str
    channel: str
    recipient: str
    content: str
    delivery_status: str
    sent_at: datetime

    class Config:
        from_attributes = True

class AlertResponse(AlertBase):
    alert_id: str
    status: str
    is_farmer_notified: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

