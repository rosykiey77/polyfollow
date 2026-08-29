import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_wallet_crud_lifecycle(async_client: AsyncClient):
    valid_address = "0x1234567890123456789012345678901234567890"

    # 1. Create wallet
    create_res = await async_client.post(
        "/api/v1/wallets",
        json={"address": valid_address, "label": "Super Whale", "is_active": True},
    )
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["address"] == valid_address.lower()
    assert created_data["label"] == "Super Whale"
    assert created_data["is_active"] is True

    # 2. Prevent duplicate creation (409)
    dup_res = await async_client.post(
        "/api/v1/wallets",
        json={"address": valid_address},
    )
    assert dup_res.status_code == 409

    # 3. Invalid address validation (422)
    invalid_res = await async_client.post(
        "/api/v1/wallets",
        json={"address": "0x123"},
    )
    assert invalid_res.status_code == 422

    # 4. Get wallet
    get_res = await async_client.get(f"/api/v1/wallets/{valid_address}")
    assert get_res.status_code == 200
    assert get_res.json()["address"] == valid_address.lower()

    # 5. List wallets
    list_res = await async_client.get("/api/v1/wallets?active_only=true")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 6. Update wallet
    update_res = await async_client.patch(
        f"/api/v1/wallets/{valid_address}",
        json={"label": "Renamed Whale", "is_active": False},
    )
    assert update_res.status_code == 200
    assert update_res.json()["label"] == "Renamed Whale"
    assert update_res.json()["is_active"] is False

    # 7. Delete wallet
    del_res = await async_client.delete(f"/api/v1/wallets/{valid_address}")
    assert del_res.status_code == 204

    # 8. Verify deleted
    not_found_res = await async_client.get(f"/api/v1/wallets/{valid_address}")
    assert not_found_res.status_code == 404


@pytest.mark.asyncio
async def test_wallet_seed_and_discover(async_client: AsyncClient):
    # Test seed endpoint
    seed_res = await async_client.post("/api/v1/wallets/seed")
    assert seed_res.status_code == 200
    assert "seeded_count" in seed_res.json()

    # Test discover endpoint
    disc_res = await async_client.post("/api/v1/wallets/discover?top_markets_limit=2&max_new_whales=5")
    assert disc_res.status_code == 200
    assert "discovered_count" in disc_res.json()


@pytest.mark.asyncio
async def test_wallet_profile_endpoint(async_client: AsyncClient):
    addr = "0x9999999999999999999999999999999999999999"
    await async_client.post("/api/v1/wallets", json={"address": addr, "label": "Profile Whale"})

    prof_res = await async_client.get(f"/api/v1/wallets/{addr}/profile")
    assert prof_res.status_code == 200
    pdata = prof_res.json()
    assert pdata["address"] == addr.lower()
    assert "archetype" in pdata
    assert "conviction_tier" in pdata
    assert "win_rate" in pdata
    assert "total_volume_usdc" in pdata
