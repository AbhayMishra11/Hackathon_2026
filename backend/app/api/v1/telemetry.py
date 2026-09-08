from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.telemetry import BulkIngestResponse, BulkItemResult, BulkTelemetryIngestRequest, IngestResponse, TelemetryIngestRequest
from app.services.telemetry_service import telemetry_service
from app.core.security import verify_device

router = APIRouter(prefix="/telemetry", tags=["IoT Telemetry"])

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
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

@router.post("/bulk", response_model=BulkIngestResponse, status_code=status.HTTP_200_OK, dependencies=[Depends(verify_device)])
async def bulk_ingest_telemetry(
    payload: BulkTelemetryIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest bulk sensor telemetry packets from simulators or buffered IoT gateways.
    """
    results = []
    accepted = duplicates = failed = 0
    for item in payload.items:
        try:
            if await telemetry_service.frame_exists(db, item):
                duplicates += 1
                results.append(BulkItemResult(seq=item.seq, status="DUPLICATE"))
                continue
            res = await telemetry_service.process_telemetry(db, item, commit=False)
            accepted += 1
            results.append(BulkItemResult(seq=item.seq, status="OK", ingest=res))
        except Exception as e:
            failed += 1
            await db.rollback()
            results.append(BulkItemResult(seq=item.seq, status="ERROR", error=str(e)))
    if accepted:
        await db.commit()
    return BulkIngestResponse(accepted=accepted, duplicates=duplicates, failed=failed, results=results)

