from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.database import get_db
from app.models.alert import Alert, AlertNotification
from app.schemas.alert import AlertResponse, AlertAcknowledge, AlertNotificationResponse

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])

@router.get("", response_model=List[AlertResponse])
@router.get("/", response_model=List[AlertResponse], include_in_schema=False)
@router.get("/active", response_model=List[AlertResponse])
async def list_active_alerts(zone_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    Get all active unresolved cold storage anomalies and farmer alerts.
    """
    query = select(Alert).where(Alert.status == "ACTIVE")
    if zone_id:
        query = query.where(Alert.zone_id == zone_id)
    query = query.order_by(desc(Alert.created_at))
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/history", response_model=List[AlertResponse])
async def list_alert_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """
    Get recent alert history (both active and resolved).
    """
    query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledge,
    db: AsyncSession = Depends(get_db)
):
    """
    Acknowledge or resolve an active alert.
    """
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = payload.status
    if payload.status == "RESOLVED":
        alert.resolved_at = datetime.utcnow()

    await db.commit()
    await db.refresh(alert)
    return alert

@router.get("/notifications", response_model=List[AlertNotificationResponse])
async def list_sent_notifications(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """
    Get log of all SMS / WhatsApp alert notifications dispatched to farmers.
    """
    query = select(AlertNotification).order_by(desc(AlertNotification.sent_at)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

