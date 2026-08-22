from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.cold_storage import Zone, ColdStorage
from app.models.sensor import Sensor
from app.schemas.zone import ZoneResponse, ZoneCreate

router = APIRouter(prefix="/zones", tags=["Zones / Chambers"])

@router.get("", response_model=List[ZoneResponse])
@router.get("/", response_model=List[ZoneResponse], include_in_schema=False)
async def list_zones(db: AsyncSession = Depends(get_db)):
    """
    Get all storage zones with their active sensors and thresholds.
    """
    query = select(Zone).options(selectinload(Zone.sensors))
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(zone_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed configuration for a specific storage zone.
    """
    query = select(Zone).where(Zone.zone_id == zone_id).options(selectinload(Zone.sensors))
    result = await db.execute(query)
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(payload: ZoneCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new chamber/zone in the cold storage facility.
    """
    storage = await db.get(ColdStorage, payload.storage_id)
    if not storage:
        raise HTTPException(status_code=404, detail="Cold storage facility not found")

    new_zone = Zone(
        storage_id=payload.storage_id,
        zone_name=payload.zone_name,
        current_crop_type=payload.current_crop_type,
        capacity_kg=payload.capacity_kg,
        temp_min=payload.temp_min,
        temp_max=payload.temp_max,
        humidity_min=payload.humidity_min,
        humidity_max=payload.humidity_max,
        co2_max=payload.co2_max,
        light_max=payload.light_max
    )
    db.add(new_zone)
    await db.commit()
    await db.refresh(new_zone)
    return new_zone

