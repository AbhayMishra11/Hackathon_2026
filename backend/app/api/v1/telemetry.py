from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.telemetry import TelemetryIngestRequest, BulkTelemetryIngestRequest, IngestResponse
from app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/telemetry", tags=["IoT Telemetry"])

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest_sensor_telemetry(
    payload: TelemetryIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest live telemetry from IoT controller/hardware sensor node.
    - Updates current sensor reading & timestamps in PostgreSQL.
    - Logs time-series record for historical graphs.
    - Evaluates thresholds and triggers instant Farmer Alerts if safety limits are breached.
    - Broadcasts live data to frontend dashboard via WebSockets.
    """
    try:
        response = await telemetry_service.process_telemetry(db, payload)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process telemetry: {str(e)}")

@router.post("/bulk", response_model=List[IngestResponse], status_code=status.HTTP_200_OK)
async def bulk_ingest_telemetry(
    payload: BulkTelemetryIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest bulk sensor telemetry packets from simulators or buffered IoT gateways.
    """
    results = []
    for item in payload.items:
        try:
            res = await telemetry_service.process_telemetry(db, item)
            results.append(res)
        except Exception as e:
            continue
    return results

