import json
import logging
from typing import List, Dict, Optional
from fastapi import WebSocket

logger = logging.getLogger("coldstorage.websocket")

class ConnectionManager:
    def __init__(self):
        # Global active connections
        self.active_connections: List[WebSocket] = []
        # Connections subscribed to a specific zone_id
        self.zone_subscribers: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, zone_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if zone_id:
            if zone_id not in self.zone_subscribers:
                self.zone_subscribers[zone_id] = []
            self.zone_subscribers[zone_id].append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, zone_id: Optional[str] = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if zone_id and zone_id in self.zone_subscribers:
            if websocket in self.zone_subscribers[zone_id]:
                self.zone_subscribers[zone_id].remove(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict, zone_id: Optional[str] = None):
        """Broadcast message to all connected clients and zone-specific subscribers."""
        payload = json.dumps(message)
        
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error(f"Error sending message to websocket client: {e}")
                self.disconnect(connection, zone_id)

connection_manager = ConnectionManager()

