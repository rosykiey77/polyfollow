import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "api_v1" in data
    assert data["mode"] in ("headless_api", "monolith_with_ui")


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "poller_running" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_readiness_check(async_client: AsyncClient):
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "degraded")
    assert "database" in data


@pytest.mark.asyncio
async def test_dashboard_endpoint_headless_behavior(async_client: AsyncClient):
    # In headless mode (default), /dashboard returns 404
    response = await async_client.get("/dashboard")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_docs_disabled_in_headless_mode(async_client: AsyncClient):
    # When ENABLE_DOCS is False (default), /docs returns 404
    response = await async_client.get("/docs")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_summary_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_wallets" in data
    assert "total_signals" in data
    assert "total_positions" in data
    assert "total_trades_tracked" in data
    assert "status" in data
    assert data["database"] == "connected"

