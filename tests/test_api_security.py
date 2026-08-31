import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.mark.asyncio
async def test_api_key_disabled_when_none(async_client: AsyncClient):
    # When API_KEY is None or empty, access is allowed without headers
    settings.API_KEY = None
    res = await async_client.get("/api/v1/wallets")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_api_key_required_when_configured(async_client: AsyncClient):
    settings.API_KEY = "test-secret-key-123"

    try:
        # 1. Request without API key -> 401 Unauthorized
        res_no_auth = await async_client.get("/api/v1/wallets")
        assert res_no_auth.status_code == 401
        assert "Unauthorized" in res_no_auth.json()["detail"]

        # 2. Request with invalid API key -> 401 Unauthorized
        res_invalid = await async_client.get(
            "/api/v1/wallets",
            headers={"X-API-Key": "wrong-key"}
        )
        assert res_invalid.status_code == 401

        # 3. Request with valid X-API-Key header -> 200 OK
        res_valid_header = await async_client.get(
            "/api/v1/wallets",
            headers={"X-API-Key": "test-secret-key-123"}
        )
        assert res_valid_header.status_code == 200

        # 4. Request with valid Bearer token -> 200 OK
        res_valid_bearer = await async_client.get(
            "/api/v1/wallets",
            headers={"Authorization": "Bearer test-secret-key-123"}
        )
        assert res_valid_bearer.status_code == 200

        # 5. Request with valid query parameter ?api_key= -> 200 OK
        res_valid_query = await async_client.get(
            "/api/v1/wallets?api_key=test-secret-key-123"
        )
        assert res_valid_query.status_code == 200

        # 6. Root health endpoint remains accessible without key
        res_health = await async_client.get("/health")
        assert res_health.status_code == 200
    finally:
        # Reset settings
        settings.API_KEY = None
