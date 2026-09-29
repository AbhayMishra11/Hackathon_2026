from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SensorBase(BaseModel):
    sensor_type: str = Field(..., description="TEMPERATURE, HUMIDITY, CO2, LIGHT")
    unit: str = Field(..., description="°C, %, ppm, Lux")
    current_reading: float = 0.0
    base_reading: float = 0.0
    max_reading: float = 100.0
    status: str = "ACTIVE"

class SensorCreate(SensorBase):
    zone_id: str

class SensorUpdate(BaseModel):
    current_reading: Optional[float] = None
    base_reading: Optional[float] = None
    max_reading: Optional[float] = None
    status: Optional[str] = None

class SensorResponse(SensorBase):
    sensor_id: str
    zone_id: str
    timestamp: datetime

    class Config:
        from_attributes = True

