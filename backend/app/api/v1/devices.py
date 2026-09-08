from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.device import Device

router = APIRouter(prefix="/devices", tags=["IoT Devices & Hardware Nodes"])

class DeviceResponse(BaseModel):
    device_id: str
    zone_id: Optional[str] = None
    label: Optional[str] = None
    location: Optional[str] = None
    firmware: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    last_seq: Optional[int] = 0
    is_online: bool = False
    last_power_source: Optional[str] = None
    last_battery_soc: Optional[float] = None
    last_temp_c: Optional[float] = None
    last_rssi: Optional[int] = None
    last_seen_age_s: Optional[int] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[DeviceResponse])
@router.get("/", response_model=List[DeviceResponse], include_in_schema=False)
async def list_devices(db: AsyncSession = Depends(get_db)):
    """List all registered IoT nodes, power status, battery level, and connectivity."""
    query = select(Device)
    result = await db.execute(query)
    devices = result.scalars().all()
    now = datetime.utcnow()
    
    out = []
    for d in devices:
        age_s = int((now - d.last_seen_at).total_seconds()) if d.last_seen_at else None
        out.append(DeviceResponse(
            device_id=d.device_id,
            zone_id=d.zone_id,
            label=d.label,
            location=d.location,
            firmware=d.firmware,
            last_seen_at=d.last_seen_at,
            last_seq=d.last_seq,
            is_online=d.is_online and (age_s is not None and age_s <= (d.offline_grace_s or 90)),
            last_power_source=d.last_power_source,
            last_battery_soc=d.last_battery_soc,
            last_temp_c=d.last_temp_c,
            last_rssi=d.last_rssi,
            last_seen_age_s=age_s
        ))
    return out

@router.get("/{device_id}/health", response_model=DeviceResponse)
async def get_device_health(device_id: str, db: AsyncSession = Depends(get_db)):
    """Get diagnostic health, power source, and battery state for a specific IoT device."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    now = datetime.utcnow()
    age_s = int((now - device.last_seen_at).total_seconds()) if device.last_seen_at else None
    return DeviceResponse(
        device_id=device.device_id,
        zone_id=device.zone_id,
        label=device.label,
        location=device.location,
        firmware=device.firmware,
        last_seen_at=device.last_seen_at,
        last_seq=device.last_seq,
        is_online=device.is_online and (age_s is not None and age_s <= (device.offline_grace_s or 90)),
        last_power_source=device.last_power_source,
        last_battery_soc=device.last_battery_soc,
        last_temp_c=device.last_temp_c,
        last_rssi=device.last_rssi,
        last_seen_age_s=age_s
    )

