import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.mark.asyncio
async def test_api_docs_endpoints_accessible(async_client: AsyncClient):
    """Verify that Swagger UI, ReDoc, and OpenAPI schema are accessible and return 200."""
    original_enable_docs = settings.ENABLE_DOCS
    settings.ENABLE_DOCS = True

    try:
        # 1. Test /docs
        res_docs = await async_client.get("/docs")
        assert res_docs.status_code == 200
        assert "html" in res_docs.headers.get("content-type", "").lower()

        # 2. Test /redoc
        res_redoc = await async_client.get("/redoc")
        assert res_redoc.status_code == 200
        assert "html" in res_redoc.headers.get("content-type", "").lower()

        # 3. Test /openapi.json
        res_openapi = await async_client.get("/openapi.json")
        assert res_openapi.status_code == 200
        openapi_data = res_openapi.json()
        assert "openapi" in openapi_data
        assert openapi_data["info"]["title"] == settings.APP_NAME
        assert "/api/v1/signals/consensus" in openapi_data["paths"]
        assert "/api/v1/signals/exits" in openapi_data["paths"]

        # 4. Test Root / endpoint returns docs links
        res_root = await async_client.get("/")
        assert res_root.status_code == 200
        root_json = res_root.json()
        assert root_json["docs"] == "/docs"
        assert root_json["redoc"] == "/redoc"
        assert root_json["openapi"] == "/openapi.json"
    finally:
        settings.ENABLE_DOCS = original_enable_docs


@pytest.mark.asyncio
async def test_api_docs_endpoints_disabled_when_false(async_client: AsyncClient):
    """Verify that Swagger UI, ReDoc, and OpenAPI schema return 404 when ENABLE_DOCS is False."""
    original_enable_docs = settings.ENABLE_DOCS
    settings.ENABLE_DOCS = False

    try:
        # 1. /docs should return 404
        res_docs = await async_client.get("/docs")
        assert res_docs.status_code == 404

        # 2. /redoc should return 404
        res_redoc = await async_client.get("/redoc")
        assert res_redoc.status_code == 404

        # 3. /openapi.json should return 404
        res_openapi = await async_client.get("/openapi.json")
        assert res_openapi.status_code == 404

        # 4. Root / endpoint should NOT contain docs links
        res_root = await async_client.get("/")
        assert res_root.status_code == 200
        root_json = res_root.json()
        assert "docs" not in root_json
        assert "redoc" not in root_json
        assert "openapi" not in root_json
    finally:
        settings.ENABLE_DOCS = original_enable_docs
