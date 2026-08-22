from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.database import get_db
from app.models.user import User
from app.models.crop_batch import CropBatch
from app.models.alert import AlertNotification
from app.schemas.crop_batch import CropBatchResponse, CropBatchCreate

router = APIRouter(prefix="/farmers", tags=["Farmers & Inventory"])

@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict], include_in_schema=False)
async def list_farmers(db: AsyncSession = Depends(get_db)):
    """
    List all registered farmers.
    """
    query = select(User).where(User.role == "FARMER")
    result = await db.execute(query)
    farmers = result.scalars().all()
    return [
        {
            "user_id": f.user_id,
            "name": f.name,
            "phone_number": f.phone_number,
            "email": f.email,
            "role": f.role,
            "preferred_alert_channel": f.preferred_alert_channel,
            "created_at": f.created_at
        }
        for f in farmers
    ]

@router.get("/{farmer_id}", response_model=dict)
async def get_farmer(farmer_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get farmer profile by user_id.
    """
    farmer = await db.get(User, farmer_id)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return {
        "user_id": farmer.user_id,
        "name": farmer.name,
        "phone_number": farmer.phone_number,
        "email": farmer.email,
        "role": farmer.role,
        "preferred_alert_channel": farmer.preferred_alert_channel,
        "created_at": farmer.created_at
    }

@router.get("/{farmer_id}/batches", response_model=List[CropBatchResponse])
async def get_farmer_batches(farmer_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get all crop batches stored in cold storage by a specific farmer.
    """
    query = select(CropBatch).where(CropBatch.farmer_id == farmer_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/batches", response_model=CropBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_crop_batch(payload: CropBatchCreate, db: AsyncSession = Depends(get_db)):
    """
    Register new produce intake batch for a farmer in a designated cold storage zone.
    """
    new_batch = CropBatch(
        zone_id=payload.zone_id,
        farmer_id=payload.farmer_id,
        fruit_type=payload.fruit_type,
        quantity_kg=payload.quantity_kg,
        expected_shelf_life_days=payload.expected_shelf_life_days,
        current_health_status=payload.current_health_status
    )
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)
    return new_batch

@router.get("/{farmer_id}/notifications")
async def get_farmer_notifications(farmer_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get historical alerts received by this specific farmer.
    """
    query = select(AlertNotification).where(AlertNotification.farmer_id == farmer_id).order_by(desc(AlertNotification.sent_at))
    result = await db.execute(query)
    notifications = result.scalars().all()
    return notifications

