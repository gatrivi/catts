from fastapi import Header, HTTPException

from config import API_KEY


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "Invalid or missing API key")
