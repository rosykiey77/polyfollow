import secrets
from typing import Optional
from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    query_key: Optional[str] = Query(None, alias="api_key", description="Alternative API Key in query parameter"),
) -> Optional[str]:
    """
    Verify incoming request against the configured API_KEY.
    If settings.API_KEY is None or empty, authentication is disabled.
    Supports:
      1. Header: X-API-Key: <key>
      2. Header: Authorization: Bearer <key>
      3. Query parameter: ?api_key=<key>
    """
    expected_key = settings.API_KEY
    if not expected_key or not expected_key.strip():
        # Authentication is disabled
        return None

    provided_key: Optional[str] = None
    if header_key:
        provided_key = header_key
    elif bearer_creds and bearer_creds.credentials:
        provided_key = bearer_creds.credentials
    elif query_key:
        provided_key = query_key

    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing API Key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return provided_key
