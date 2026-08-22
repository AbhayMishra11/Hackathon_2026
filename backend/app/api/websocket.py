import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import connection_manager

logger = logging.getLogger("coldstorage.websocket")

router = APIRouter()

@router.websocket("/ws/live-telemetry")
async def websocket_live_telemetry_all(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep alive and handle any incoming client control messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)

@router.websocket("/ws/live-telemetry/{zone_id}")
async def websocket_live_telemetry_zone(websocket: WebSocket, zone_id: str):
    await connection_manager.connect(websocket, zone_id=zone_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, zone_id=zone_id)

