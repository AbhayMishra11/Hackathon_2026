from datetime import datetime
from typing import List, Literal, Optional
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
    device_id: Optional[str] = None
    firmware: Optional[str] = None
    seq: Optional[int] = None
    sampled_at: Optional[datetime] = None
    probe_temps: Optional[List[float]] = None
    probe_status: Optional[List[str]] = None
    surface_temp: Optional[float] = None
    ambient_temp: Optional[float] = None
    co2_true: Optional[float] = None
    eco2: Optional[float] = None
    voc_index: Optional[float] = None
    door_open: Optional[bool] = None
    compressor_on: Optional[bool] = None
    fan_on: Optional[bool] = None
    mass_kg: Optional[float] = None
    power_source: Optional[Literal["SOLAR", "BATTERY", "GRID", "NONE"]] = None
    battery_soc: Optional[float] = None
    battery_v: Optional[float] = None
    pv_power_w: Optional[float] = None
    load_power_w: Optional[float] = None
    dew_point_c: Optional[float] = None
    vpd_kpa: Optional[float] = None
    rssi: Optional[int] = None
    edge_status: Optional[str] = None

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
    remaining_shelf_life_h: Optional[float] = None
    condensation_margin_c: Optional[float] = None
    recommended_setpoint_c: Optional[float] = None
    server_time: Optional[datetime] = None


class BulkItemResult(BaseModel):
    seq: Optional[int] = None
    status: Literal["OK", "DUPLICATE", "ERROR"]
    error: Optional[str] = None
    ingest: Optional[IngestResponse] = None


class BulkIngestResponse(BaseModel):
    accepted: int
    duplicates: int
    failed: int
    results: List[BulkItemResult]

