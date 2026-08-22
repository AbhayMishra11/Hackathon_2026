from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class CropBatchBase(BaseModel):
    fruit_type: str
    quantity_kg: float
    expected_shelf_life_days: int = 30
    current_health_status: str = "Good"

class CropBatchCreate(CropBatchBase):
    zone_id: str
    farmer_id: str

class CropBatchResponse(CropBatchBase):
    batch_id: str
    zone_id: str
    farmer_id: str
    intake_date: datetime

    class Config:
        from_attributes = True

