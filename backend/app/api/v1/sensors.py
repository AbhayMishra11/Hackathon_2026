from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.sensor import Sensor
from app.schemas.sensor import SensorResponse, SensorCreate, SensorUpdate

router = APIRouter(prefix="/sensors", tags=["Sensors"])

@router.get("", response_model=List[SensorResponse])
async def list_sensors(zone_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    List all IoT sensors, optionally filtered by zone_id.
    """
    query = select(Sensor)
    if zone_id:
        query = query.where(Sensor.zone_id == zone_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor(sensor_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed sensor reading and thresholds.
    """
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return sensor

@router.patch("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(sensor_id: str, payload: SensorUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update sensor baseline/maximum safety thresholds or calibration reading.
    """
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    if payload.current_reading is not None:
        sensor.current_reading = payload.current_reading
    if payload.base_reading is not None:
        sensor.base_reading = payload.base_reading
    if payload.max_reading is not None:
        sensor.max_reading = payload.max_reading
    if payload.status is not None:
        sensor.status = payload.status

    await db.commit()
    await db.refresh(sensor)
    return sensor

