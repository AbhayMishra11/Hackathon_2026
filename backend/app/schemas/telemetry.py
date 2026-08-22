from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class SingleSensorReading(BaseModel):
    sensor_type: str = Field(..., description="TEMPERATURE, HUMIDITY, CO2, LIGHT")
    value: float
    unit: Optional[str] = None

class TelemetryIngestRequest(BaseModel):
    """Payload sent by IoT device/controller for a specific zone"""
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    crop_type: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    light: Optional[float] = None
    co2: Optional[float] = None
    readings: Optional[List[SingleSensorReading]] = None
    timestamp: Optional[datetime] = None

class BulkTelemetryIngestRequest(BaseModel):
    items: List[TelemetryIngestRequest]

class TelemetryLogResponse(BaseModel):
    log_id: int
    sensor_id: str
    zone_id: str
    sensor_type: str
    reading_value: float
    recorded_at: datetime

    class Config:
        from_attributes = True

class IngestResponse(BaseModel):
    status: str
    message: str
    zone_id: str
    alerts_triggered: int
    spoilage_status: str
    timestamp: datetime

