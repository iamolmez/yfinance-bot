"""Webhook bildirim servisi — Discord, Slack, Email, Pushover, Telegram Bot API, ntfy."""

import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import time

import requests

logger = logging.getLogger(__name__)


@dataclass
class WebhookPayload:
    """Standart webhook payload."""
    title: str
    message: str
    symbol: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    alert_type: Optional[str] = None
    timestamp: Optional[float] = None


class WebhookSender(ABC):
    """Webhook gönderici temel sınıf."""

    name: str = "base"

    @abstractmethod
    def send(self, payload: WebhookPayload) -> bool:
        """Payload gönderir. Başarı durumu döndürür."""
        pass

    def _post(self, url: str, json_data: dict, headers: dict = None, timeout: int = 10) -> bool:
        try:
            resp = requests.post(url, json=json_data, headers=headers, timeout=timeout)
            return 200 <= resp.status_code < 300
        except Exception as e:
            logger.warning("Webhook %s gönderim hatası: %s", self.name, e)
            return False


class DiscordWebhook(WebhookSender):
    """Discord webhook (embed destekli)."""
    name = "discord"

    def send(self, payload: WebhookPayload) -> bool:
        color = 0x00ff00
        if payload.change_pct is not None:
            color = 0x00ff00 if payload.change_pct >= 0 else 0xff0000
        elif payload.alert_type and "sat" in payload.alert_type.lower():
            color = 0xff0000

        embed = {
            "title": payload.title,
            "description": payload.message,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(payload.timestamp or time.time())),
        }
        if payload.symbol:
            embed["fields"] = [
                {"name": "Sembol", "value": payload.symbol, "inline": True},
            ]
            if payload.price is not None:
                embed["fields"].append({"name": "Fiyat", "value": f"{payload.price:,.2f}", "inline": True})
            if payload.change_pct is not None:
                embed["fields"].append({"name": "Değişim", "value": f"{payload.change_pct:+.2f}%", "inline": True})

        return self._post(payload.webhook_url, {"embeds": [embed]})


class SlackWebhook(WebhookSender):
    """Slack webhook (blocks destekli)."""
    name = "slack"

    def send(self, payload: WebhookPayload) -> bool:
        color = "good"
        if payload.change_pct is not None:
            color = "good" if payload.change_pct >= 0 else "danger"
        elif payload.alert_type and "sat" in payload.alert_type.lower():
            color = "danger"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": payload.title}},
            {"type": "section", "text": {"type": "mrkdwn", "text": payload.message}},
        ]
        fields = []
        if payload.symbol:
            fields.append({"type": "mrkdwn", "text": f"*Sembol:*\n{payload.symbol}"})
        if payload.price is not None:
            fields.append({"type": "mrkdwn", "text": f"*Fiyat:*\n{payload.price:,.2f}"})
        if payload.change_pct is not None:
            fields.append({"type": "mrkdwn", "text": f"*Değişim:*\n{payload.change_pct:+.2f}%"})
        if fields:
            blocks.append({"type": "section", "fields": fields})

        return self._post(payload.webhook_url, {"blocks": blocks, "attachments": [{"color": color, "blocks": blocks}]})


class NtfyWebhook(WebhookSender):
    """ntfy.sh webhook (basit, topic-based)."""
    name = "ntfy"

    def send(self, payload: WebhookPayload) -> bool:
        tags = []
        if payload.change_pct is not None:
            tags.append("chart_with_upwards_trend" if payload.change_pct >= 0 else "chart_with_downwards_trend")
        if payload.alert_type:
            tags.append("warning" if "sat" in payload.alert_type.lower() else "information_source")

        headers = {
            "Title": payload.title,
            "Tags": ",".join(tags) if tags else "bell",
        }
        if payload.symbol:
            headers["X-Symbol"] = payload.symbol

        return self._post(payload.webhook_url, payload.message.encode("utf-8"), headers=headers)


class PushoverWebhook(WebhookSender):
    """Pushover.net webhook."""
    name = "pushover"

    def send(self, payload: WebhookPayload) -> bool:
        data = {
            "token": payload.webhook_url.split("token=")[1].split("&")[0] if "token=" in payload.webhook_url else "",
            "user": payload.webhook_url.split("user=")[1].split("&")[0] if "user=" in payload.webhook_url else "",
            "title": payload.title,
            "message": payload.message,
            "priority": 1 if (payload.change_pct and payload.change_pct < -10) else 0,
        }
        return self._post("https://api.pushover.net/1/messages.json", data)


class EmailWebhook(WebhookSender):
    """Email webhook (basit SMTP yerine webhook URL — örn: sendgrid, mailgun, vb.)."""
    name = "email"

    def send(self, payload: WebhookPayload) -> bool:
        # URL formatı: email://to@example.com?api_key=...&from=...
        # Basit implementasyon: JSON POST
        data = {
            "to": payload.webhook_url.replace("email://", "").split("?")[0],
            "subject": payload.title,
            "text": payload.message,
        }
        return self._post(payload.webhook_url, data)


class TelegramWebhook(WebhookSender):
    """Telegram Bot API webhook (chat_id + token)."""
    name = "telegram"

    def send(self, payload: WebhookPayload) -> bool:
        # URL formatı: tg://<bot_token>/<chat_id>
        if not payload.webhook_url.startswith("tg://"):
            return False
        parts = payload.webhook_url[5:].split("/")
        if len(parts) != 2:
            return False
        token, chat_id = parts
        data = {
            "chat_id": chat_id,
            "text": f"<b>{payload.title}</b>\n\n{payload.message}",
            "parse_mode": "HTML",
        }
        return self._post(f"https://api.telegram.org/bot{token}/sendMessage", data)


class GenericJSONWebhook(WebhookSender):
    """Genel JSON POST webhook (herhangi bir endpoint)."""
    name = "json"

    def send(self, payload: WebhookPayload) -> bool:
        data = {
            "title": payload.title,
            "message": payload.message,
            "symbol": payload.symbol,
            "price": payload.price,
            "change_pct": payload.change_pct,
            "alert_type": payload.alert_type,
            "timestamp": payload.timestamp or time.time(),
        }
        return self._post(payload.webhook_url, data)


# Sender registry
_SENDERS: dict[str, WebhookSender] = {
    "discord": DiscordWebhook(),
    "slack": SlackWebhook(),
    "ntfy": NtfyWebhook(),
    "pushover": PushoverWebhook(),
    "email": EmailWebhook(),
    "telegram": TelegramWebhook(),
    "json": GenericJSONWebhook(),
}


def get_sender(webhook_type: str) -> Optional[WebhookSender]:
    """Webhook tipine göre sender döndürür."""
    return _SENDERS.get(webhook_type.lower())


def send_webhook(webhook_url: str, webhook_type: str, payload: WebhookPayload) -> bool:
    """Webhook gönderir (tip + URL ile)."""
    if not webhook_url or not webhook_type:
        return False
    sender = get_sender(webhook_type)
    if not sender:
        logger.warning("Bilinmeyen webhook tipi: %s", webhook_type)
        return False
    # Payload'a URL ve type ekle
    payload.webhook_url = webhook_url
    payload.webhook_type = webhook_type
    return sender.send(payload)


# Thread-safe rate limiting (per webhook URL)
_rate_limits: dict[str, float] = {}
_rate_lock = threading.Lock()


def send_webhook_rate_limited(webhook_url: str, webhook_type: str, payload: WebhookPayload, min_interval: float = 1.0) -> bool:
    """Rate-limited webhook gönderimi (aynı URL için min_interval saniye)."""
    now = time.time()
    with _rate_lock:
        last = _rate_limits.get(webhook_url, 0)
        if now - last < min_interval:
            return False  # Rate limited
        _rate_limits[webhook_url] = now
    return send_webhook(webhook_url, webhook_type, payload)