import asyncio
from typing import Any
import httpx
from app.core.config import settings
from app.core.logging import logger


class WebhookService:
    """Dispatches asynchronous real-time push alerts to Hermes Agent and Telegram."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=8.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def dispatch_signal_alert(self, signal_dict: dict[str, Any]) -> bool:
        """Send high-conviction consensus signal to configured webhook destinations."""
        score = signal_dict.get("confidence_score", 0.0)
        if score < settings.MIN_ALERT_CONFIDENCE_SCORE:
            return False

        tasks = []
        if settings.HERMES_WEBHOOK_URL:
            tasks.append(self._send_hermes_webhook("CONSENSUS_SIGNAL", signal_dict))
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            tasks.append(self._send_telegram_signal_alert(signal_dict))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return any(r is True for r in results)
        return False

    async def dispatch_whale_trade_alert(self, trade_dict: dict[str, Any]) -> bool:
        """Send large single whale trade to configured webhook destinations."""
        size_usdc = trade_dict.get("usdc_size", 0.0)
        if size_usdc < settings.MIN_WHALE_TRADE_ALERT_USD:
            return False

        tasks = []
        if settings.HERMES_WEBHOOK_URL:
            tasks.append(self._send_hermes_webhook("WHALE_TRADE", trade_dict))
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            tasks.append(self._send_telegram_trade_alert(trade_dict))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return any(r is True for r in results)
        return False

    async def _send_hermes_webhook(self, event_type: str, payload: dict[str, Any]) -> bool:
        """Post structured signal event to Hermes AI Agent."""
        try:
            client = await self._get_client()
            body = {
                "event": event_type,
                "source": "Polyfollow Bandar Intelligence",
                "payload": payload,
            }
            res = await client.post(str(settings.HERMES_WEBHOOK_URL), json=body)
            if res.status_code in (200, 201, 202, 204):
                logger.info("Successfully pushed %s alert to Hermes Agent (%s)", event_type, settings.HERMES_WEBHOOK_URL)
                return True
            else:
                logger.warning("Hermes webhook returned status %d: %s", res.status_code, res.text[:100])
        except Exception as e:
            logger.warning("Failed to dispatch webhook to Hermes Agent: %s", str(e))
        return False

    async def _send_telegram_signal_alert(self, s: dict[str, Any]) -> bool:
        """Send formatted markdown alert to Telegram channel or chat."""
        try:
            client = await self._get_client()
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            
            actionable = s.get("actionable_signal", {})
            action = actionable.get("recommended_action", "BUY")
            risk = actionable.get("risk_tier", "MEDIUM")
            max_entry = actionable.get("suggested_max_entry_price", 0.0)
            potential_roi = actionable.get("potential_roi_percent", 0.0)
            
            text = (
                f"🚨 *POLYFOLLOW SMART CONSENSUS ALPHA*\n\n"
                f"📊 *Market:* `{s.get('market_title', 'Unknown')}`\n"
                f"🎯 *Consensus Outcome:* `{s.get('consensus_outcome', 'YES')}`\n"
                f"🔥 *Confidence Score:* `{s.get('confidence_score')}/100` ({s.get('strength')})\n"
                f"🐋 *Whales Count:* `{s.get('whale_count')}` Bandar\n"
                f"💰 *Total Volume:* `${s.get('total_volume_usdc', 0):,.2f} USDC`\n"
                f"⚡ *Action:* `{action}` (Risk: `{risk}`)\n"
                f"🏷 *Max Entry:* `{max_entry}` | *Upside:* `+{potential_roi:.1f}%`\n\n"
                f"🧠 *AI Rationale:* _{s.get('ai_rationale', '')}_"
            )
            payload = {
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            }
            res = await client.post(url, json=payload)
            return res.status_code == 200
        except Exception as e:
            logger.warning("Failed to send Telegram signal alert: %s", str(e))
            return False

    async def _send_telegram_trade_alert(self, t: dict[str, Any]) -> bool:
        """Send single large whale trade alert to Telegram."""
        try:
            client = await self._get_client()
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            text = (
                f"🐋 *LARGE WHALE TRADE DETECTED*\n\n"
                f"👤 *Wallet:* `{t.get('wallet_address', '')[:8]}...{t.get('wallet_address', '')[-6:]}`\n"
                f"📊 *Market:* `{t.get('market_title', 'Market')}`\n"
                f"🎯 *Side & Outcome:* `{t.get('side', 'BUY')} {t.get('outcome', 'YES')}`\n"
                f"💵 *Amount:* `${t.get('usdc_size', 0):,.2f} USDC` @ `{t.get('price', 0):.4f}`\n"
                f"🔗 *Tx:* `{t.get('transaction_hash', 'N/A')[:12]}...`"
            )
            payload = {
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            }
            res = await client.post(url, json=payload)
            return res.status_code == 200
        except Exception as e:
            logger.warning("Failed to send Telegram trade alert: %s", str(e))
            return False


webhook_service = WebhookService()
