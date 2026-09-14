from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from .sensor import SensorResponse

class ZoneBase(BaseModel):
    zone_name: str
    current_crop_type: str = Field(..., description="Cabbage, French bean, Leafy greens, Tomato, Ginger, Pineapple, Khasi mandarin, Green chilli")
    capacity_kg: float = 5000.0
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    humidity_min: Optional[float] = None
    humidity_max: Optional[float] = None
    co2_max: Optional[float] = None
    light_max: Optional[float] = None

class ZoneCreate(ZoneBase):
    storage_id: str

class ZoneResponse(ZoneBase):
    zone_id: str
    storage_id: str
    status: str
    created_at: datetime
    sensors: Optional[List[SensorResponse]] = []

    # NER Solar & Environmental Control Fields
    setpoint_c: Optional[float] = None
    setpoint_rh: Optional[float] = None
    hysteresis_c: Optional[float] = None
    mode: Optional[str] = None
    chilling_injury_c: Optional[float] = None
    freezing_point_c: Optional[float] = None
    co2_ppm_max: Optional[float] = None
    co2_ppm_critical: Optional[float] = None
    free_volume_m3: Optional[float] = None

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

class ZoneSetpointUpdate(BaseModel):
    temp_c: float = Field(..., description="Target chamber temperature in °C")
    rh_pct: Optional[float] = Field(default=92.0, description="Target relative humidity %")

class ZoneModeUpdate(BaseModel):
    mode: Literal["AUTO", "PRECOOL", "DEFROST", "ECO", "OFF"] = Field(..., description="AUTO, PRECOOL, DEFROST, ECO, OFF")

class ZoneCropUpdate(BaseModel):
    crop_type: Literal[
        "Cabbage", "French bean", "Leafy greens", "Tomato",
        "Ginger", "Pineapple", "Khasi mandarin", "Green chilli"
    ] = Field(..., description="Cabbage, French bean, Leafy greens, Tomato, Ginger, Pineapple, Khasi mandarin, Green chilli")


