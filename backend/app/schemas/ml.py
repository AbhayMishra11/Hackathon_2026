from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class SpoilagePredictionRequest(BaseModel):
    crop_type: str = Field(..., description="Orange, Banana, Tomato, Pineapple")
    temperature: float = Field(..., description="Temperature in °C")
    humidity: float = Field(..., description="Humidity percentage (0-100%)")
    light: float = Field(..., description="Light level in Lux/Fux")
    co2: float = Field(..., description="CO2 concentration in ppm")

class RiskFactor(BaseModel):
    parameter: str
    current_value: float
    safe_range: str
    status: str # 'NORMAL', 'WARNING', 'CRITICAL'
    message: str

class SpoilagePredictionResponse(BaseModel):
    crop_type: str
    predicted_quality: str # 'Good' or 'Bad'
    spoilage_risk_percentage: float # 0.0 to 100.0%
    confidence: float # 0.0 to 1.0
    risk_level: str # 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    estimated_shelf_life_days: int
    primary_risk_factors: List[RiskFactor]
    recommendations: List[str]

