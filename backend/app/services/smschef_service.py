import logging
import httpx
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger("coldstorage.smschef")

class SMSChefService:
    def __init__(self):
        self.api_url = settings.SMSCHEF_API_URL
        self.api_key = settings.SMSCHEF_API_KEY
        self.device_id = settings.SMSCHEF_DEVICE_ID
        self.sim_slot = settings.SMSCHEF_SIM_SLOT

    async def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Send an SMS alert via SMS Chef Gateway using your Android phone and SIM card.
        
        API Parameters required by SMS Chef:
        - secret: API Secret Key (Tools -> API Keys)
        - mode: "devices"
        - device: Device ID from SMS Chef app/dashboard
        - sim: 1 or 2
        - priority: 1 (High priority)
        - phone: Recipient phone number (e.g. +919876543210)
        - message: Alert text
        """
        if not self.api_key or not self.device_id:
            logger.info(
                f"[SMS Chef Simulation] Target: {phone_number} | "
                f"Keys not set in .env (SMSCHEF_API_KEY / SMSCHEF_DEVICE_ID). Message: {message[:60]}..."
            )
            return {
                "status": "SIMULATED",
                "message": "SMS simulated (configure SMSCHEF_API_KEY and SMSCHEF_DEVICE_ID in .env for live SIM dispatch)",
                "recipient": phone_number
            }

        payload = {
            "secret": self.api_key,
            "mode": "devices",
            "device": self.device_id,
            "sim": self.sim_slot,
            "priority": 1,
            "phone": phone_number,
            "message": message
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.api_url, data=payload)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ [SMS Chef SUCCESS] Alert sent to {phone_number}. Response: {data}")
                    return {
                        "status": "SENT",
                        "response": data,
                        "recipient": phone_number
                    }
                else:
                    logger.error(f"❌ [SMS Chef ERROR] HTTP {response.status_code}: {response.text}")
                    return {
                        "status": "FAILED",
                        "error": response.text,
                        "recipient": phone_number
                    }
        except Exception as e:
            logger.error(f"❌ [SMS Chef EXCEPTION] Failed to connect to SMS Chef gateway: {str(e)}")
            return {
                "status": "FAILED",
                "error": str(e),
                "recipient": phone_number
            }

smschef_service = SMSChefService()

