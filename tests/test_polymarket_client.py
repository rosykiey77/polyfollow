import datetime
import pytest
from unittest.mock import AsyncMock, patch
from app.services.polymarket import PolymarketClient


@pytest.mark.asyncio
async def test_polymarket_client_parse_timestamp():
    client = PolymarketClient()

    # Numeric seconds
    dt1 = client.parse_timestamp(1700000000)
    assert isinstance(dt1, datetime.datetime)

    # Numeric milliseconds
    dt2 = client.parse_timestamp(1700000000000)
    assert isinstance(dt2, datetime.datetime)

    # ISO format
    dt3 = client.parse_timestamp("2026-08-26T12:00:00Z")
    assert isinstance(dt3, datetime.datetime)
    assert dt3.year == 2026


@pytest.mark.asyncio
async def test_polymarket_client_get_positions_mocked():
    mock_data = [
        {
            "conditionId": "cond_test_1",
            "title": "Will Bitcoin break ATH in 2026?",
            "outcome": "YES",
            "size": 1500.0,
            "avgPrice": 0.50,
            "curPrice": 0.70,
            "cashPnl": 300.0,
            "currentValue": 1050.0,
        }
    ]

    client = PolymarketClient()
    with patch.object(client, "_request_with_retry", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_data
        positions = await client.get_user_positions("0x1234567890123456789012345678901234567890")
        assert len(positions) == 1
        assert positions[0]["conditionId"] == "cond_test_1"
        assert positions[0]["cashPnl"] == 300.0
