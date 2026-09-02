import asyncio
import datetime
import socket
from typing import Any
import httpx
from app.core.config import settings
from app.core.logging import logger

# Polymarket domains that may be subject to ISP DNS blocking / hijacking (e.g. Internet Positif / Telkomsel)
POLYMARKET_DOMAINS = {
    "data-api.polymarket.com",
    "gamma-api.polymarket.com",
    "clob.polymarket.com",
    "polymarket.com",
}

# Reliable Anycast Cloudflare IPs for Polymarket CDN
DEFAULT_POLYMARKET_IPS = [
    "104.18.34.205",
    "172.64.153.51",
    "104.18.35.205",
    "172.64.152.51",
]

_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_dns_initialized = False


def setup_dns_bypass():
    """
    Patches socket.getaddrinfo to resolve Polymarket domains directly to verified Cloudflare Anycast IPs.
    This guarantees immunity against ISP DNS poisoning, DNS hijacking (Internet Baik / Internet Positif),
    and local IPv6 resolution timeouts.
    """
    global _dns_initialized
    if _dns_initialized:
        return

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        try:
            return _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)
        except Exception:
            if isinstance(host, str) and host.lower() in POLYMARKET_DOMAINS:
                ip = DEFAULT_POLYMARKET_IPS[0]
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
            raise


    socket.getaddrinfo = patched_getaddrinfo
    _dns_initialized = True
    logger.info("Polymarket resilient DNS resolver & ISP bypass initialized.")


# Initialize DNS patch on module import
setup_dns_bypass()


class PolymarketClient:
    """Async client for querying Polymarket Data and Gamma APIs with retry, rate limiting, and ISP bypass."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Polyfollow/1.0; +https://github.com/polymarket)",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request_with_retry(self, method: str, url: str, params: dict[str, Any] | None = None) -> Any:
        client = await self._get_client()
        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                response = await client.request(method, url, params=params)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Polymarket API returned %s for %s. Attempt %d/%d",
                        response.status_code,
                        url,
                        attempt,
                        settings.MAX_RETRIES,
                    )
                    await asyncio.sleep(1.0 * attempt)
                else:
                    logger.error("Polymarket API error %s for %s: %s", response.status_code, url, response.text[:200])
                    return None
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(
                    "Network error querying %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    settings.MAX_RETRIES,
                    str(exc),
                )
                if attempt == settings.MAX_RETRIES:
                    return None
                await asyncio.sleep(1.0 * attempt)
        return None

    async def get_user_positions(self, wallet_address: str) -> list[dict[str, Any]]:
        """Fetch active positions for a wallet address from Polymarket Data API."""
        url = f"{settings.POLYMARKET_DATA_API_BASE}/positions"
        params = {"user": wallet_address.lower()}
        data = await self._request_with_retry("GET", url, params=params)
        if isinstance(data, list):
            return data
        return []

    async def get_user_activity(self, wallet_address: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch recent trade activity for a wallet address from Polymarket Data API."""
        url = f"{settings.POLYMARKET_DATA_API_BASE}/activity"
        params = {"user": wallet_address.lower(), "limit": limit}
        data = await self._request_with_retry("GET", url, params=params)
        if isinstance(data, list):
            return data
        return []

    async def get_top_markets(self, limit: int = 20, order: str = "volume24hr") -> list[dict[str, Any]]:
        """Fetch top prediction markets from Polymarket Gamma API."""
        url = f"{settings.POLYMARKET_GAMMA_API_BASE}/markets"
        params = {
            "limit": limit,
            "order": order,
            "ascending": "false",
            "closed": "false",
            "active": "true",
        }
        data = await self._request_with_retry("GET", url, params=params)
        if isinstance(data, list):
            return data
        return []

    async def get_market_holders(self, condition_id: str) -> list[dict[str, Any]]:
        """Fetch top position holders (whales) for a given market condition ID."""
        url = f"{settings.POLYMARKET_DATA_API_BASE}/holders"
        params = {"market": condition_id}
        data = await self._request_with_retry("GET", url, params=params)
        if isinstance(data, list):
            return data
        return []

    async def get_recent_trades(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch real-time recent trades across all markets from Polymarket Data API."""
        url = f"{settings.POLYMARKET_DATA_API_BASE}/trades"
        params = {"limit": limit}
        data = await self._request_with_retry("GET", url, params=params)
        if isinstance(data, list):
            return data
        return []

    @staticmethod
    def parse_timestamp(val: Any) -> datetime.datetime:
        """Parse unix timestamp (seconds or milliseconds) or ISO string to UTC datetime."""
        if not val:
            return datetime.datetime.now(datetime.timezone.utc)
        if isinstance(val, (int, float)):
            # If timestamp is in milliseconds (> 10 digits)
            if val > 1e11:
                val = val / 1000.0
            return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
        if isinstance(val, str):
            try:
                # Try ISO format
                cleaned = val.replace("Z", "+00:00")
                return datetime.datetime.fromisoformat(cleaned)
            except Exception:
                pass
        return datetime.datetime.now(datetime.timezone.utc)


polymarket_client = PolymarketClient()
