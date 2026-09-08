from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.cold_storage import Zone, ColdStorage
from app.models.sensor import Sensor
from app.schemas.zone import ZoneResponse, ZoneCreate, ZoneSetpointUpdate, ZoneModeUpdate, ZoneCropUpdate

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

@router.post("/{zone_id}/setpoint", response_model=ZoneResponse)
async def update_zone_setpoint(
    zone_id: str,
    payload: ZoneSetpointUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update target temperature and humidity setpoints for a chamber."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    zone.setpoint_c = payload.temp_c
    if payload.rh_pct is not None:
        zone.setpoint_rh = payload.rh_pct
    await db.commit()
    await db.refresh(zone)
    return zone

@router.post("/{zone_id}/mode", response_model=ZoneResponse)
async def update_zone_mode(
    zone_id: str,
    payload: ZoneModeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update operating mode (AUTO, PRECOOL, DEFROST, ECO, OFF) for a chamber."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    zone.mode = payload.mode.upper()
    await db.commit()
    await db.refresh(zone)
    return zone

@router.post("/{zone_id}/crop", response_model=ZoneResponse)
async def update_zone_crop(
    zone_id: str,
    payload: ZoneCropUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update stored crop type for a zone.
    Automatically re-derives all zone thresholds and child sensor bounds from crop rules.
    """
    from app.services.ml_service import CROP_THRESHOLDS
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    crop = payload.crop_type
    rules = CROP_THRESHOLDS.get(crop, CROP_THRESHOLDS.get("Tomato"))
    zone.current_crop_type = crop
    zone.temp_min = rules["temp_min"]
    zone.temp_max = rules["temp_max"]
    zone.humidity_min = rules["humid_min"]
    zone.humidity_max = rules["humid_max"]
    zone.co2_max = rules["co2_max"]
    zone.co2_ppm_max = rules["co2_max"]
    zone.setpoint_c = (rules["temp_min"] + rules["temp_max"]) / 2.0
    zone.setpoint_rh = (rules["humid_min"] + rules["humid_max"]) / 2.0

    # Re-derive child sensor min/max bounds
    sensors_query = select(Sensor).where(Sensor.zone_id == zone_id)
    sensors = (await db.execute(sensors_query)).scalars().all()
    for s in sensors:
        if s.sensor_type == "TEMPERATURE":
            s.base_reading, s.max_reading = zone.temp_min, zone.temp_max
        elif s.sensor_type == "HUMIDITY":
            s.base_reading, s.max_reading = zone.humidity_min, zone.humidity_max
        elif s.sensor_type == "CO2":
            s.base_reading, s.max_reading = 0.0, zone.co2_ppm_max

    await db.commit()
    await db.refresh(zone)
    return zone


