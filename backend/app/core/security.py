from fastapi import Header, HTTPException, status
from app.core.config import settings


async def verify_device(x_device_key: str | None = Header(default=None)):
    if settings.DEVICE_API_KEYS and x_device_key not in settings.DEVICE_API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Device-Key")
    return x_device_key