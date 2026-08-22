from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .sensor import SensorResponse

class ZoneBase(BaseModel):
    zone_name: str
    current_crop_type: str = Field(..., description="Orange, Banana, Tomato, Pineapple")
    capacity_kg: float = 5000.0
    temp_min: float = 21.0
    temp_max: float = 24.0
    humidity_min: float = 80.0
    humidity_max: float = 95.0
    co2_max: float = 380.0
    light_max: float = 20.0

class ZoneCreate(ZoneBase):
    storage_id: str

class ZoneResponse(ZoneBase):
    zone_id: str
    storage_id: str
    status: str
    created_at: datetime
    sensors: Optional[List[SensorResponse]] = []

    class Config:
        from_attributes = True

class ZoneLiveStatus(BaseModel):
    zone_id: str
    zone_name: str
    crop_type: str
    overall_status: str # 'OPTIMAL', 'WARNING', 'CRITICAL'
    spoilage_risk: str # 'Good', 'Degrading', 'Bad'
    risk_score: float # 0.0 to 100.0%
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[float] = None
    light: Optional[float] = None
    active_alerts_count: int = 0
    last_updated: datetime

