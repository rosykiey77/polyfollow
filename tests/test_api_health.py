import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert data["docs"] == "/docs"


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
async def test_dashboard_endpoint(async_client: AsyncClient):
    response = await async_client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "POLYFOLLOW" in response.text


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

