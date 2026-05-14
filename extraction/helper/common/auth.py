from __future__ import annotations

import os

from fastapi import HTTPException, Request


async def validate_endpoint_api_key(request: Request, api_key: str | None) -> None:
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key:
        raise HTTPException(status_code=500, detail="Endpoint API key not configured on server")

    provided_api_key = api_key
    if not provided_api_key:
        headers = request.headers
        provided_api_key = (
            headers.get("x-api-key")
            or headers.get("api-key")
            or headers.get("api_key")
            or headers.get("x_api_key")
            or headers.get("api_key")
        )
        if not provided_api_key:
            auth_header = headers.get("authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                provided_api_key = auth_header[7:].strip()

    if provided_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")