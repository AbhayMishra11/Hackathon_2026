from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.cold_storage import Zone
from app.models.sensor import Sensor
from app.schemas.ml import SpoilagePredictionRequest, SpoilagePredictionResponse
from app.services.ml_service import ml_service

router = APIRouter(prefix="/analytics", tags=["Analytics & AI Spoilage Prediction"])

@router.post("/predict-spoilage", response_model=SpoilagePredictionResponse)
async def predict_crop_spoilage(payload: SpoilagePredictionRequest):
    """
    Predict produce shelf life, quality status ('Good' vs 'Bad'), spoilage probability,
    and root-cause breakdown based on Temperature, Humidity, Light, and CO2 values.
    """
    try:
        prediction = ml_service.predict_spoilage(payload)
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@router.get("/zone-risk-score/{zone_id}", response_model=SpoilagePredictionResponse)
async def get_zone_risk_score(zone_id: str, db: AsyncSession = Depends(get_db)):
    """
    Compute real-time AI spoilage risk score for a specific zone using its current live sensor telemetry.
    """
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    sensors_query = select(Sensor).where(Sensor.zone_id == zone_id)
    sensors = (await db.execute(sensors_query)).scalars().all()
    sensor_map = {s.sensor_type.upper(): s.current_reading for s in sensors}

    req = SpoilagePredictionRequest(
        crop_type=zone.current_crop_type,
        temperature=sensor_map.get("TEMPERATURE", 22.0),
        humidity=sensor_map.get("HUMIDITY", 90.0),
        co2=sensor_map.get("CO2", 320.0),
        light=sensor_map.get("LIGHT", 10.0)
    )

    return ml_service.predict_spoilage(req)

