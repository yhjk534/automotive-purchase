"""DingTalk webhook publisher with signing, deduplication, and retries."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import httpx

from .config import AlertSettings
from .state_store import DedupeStore


@dataclass
class NotificationResult:
    success: bool
    status: str
    attempts: int
    message: str
    status_code: int | None = None


def signed_webhook_url(webhook_url: str, secret: str) -> str:
    if not secret:
        return webhook_url
    timestamp = str(int(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    sign = quote_plus(base64.b64encode(digest))
    separator = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{separator}timestamp={timestamp}&sign={sign}"


class DingTalkNotifier:
    def __init__(
        self,
        settings: AlertSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or AlertSettings.from_env()
        self.store = DedupeStore(self.settings.state_db)
        self._transport = transport

    async def publish(
        self,
        *,
        title: str,
        content: str,
        severity: str,
        dedupe_key: str,
        alert_type: str = "manual_notification",
        payload: dict[str, Any] | None = None,
        cooldown_seconds: int | None = None,
    ) -> NotificationResult:
        severity = severity.lower()
        if severity not in {"info", "warning", "critical"}:
            severity = "info"
        cooldown = (
            self.settings.dedupe_cooldown_seconds
            if cooldown_seconds is None
            else cooldown_seconds
        )
        claimed = self.store.claim(
            event_key=dedupe_key,
            alert_type=alert_type,
            severity=severity,
            payload=payload or {"title": title, "content": content},
            cooldown_seconds=cooldown,
        )
        if not claimed:
            return NotificationResult(
                success=True,
                status="duplicate_skipped",
                attempts=0,
                message="相同事件仍在去重窗口内，已跳过发送",
            )

        if self.settings.dry_run:
            self.store.mark_sent(dedupe_key)
            return NotificationResult(
                success=True,
                status="dry_run",
                attempts=0,
                message="DINGTALK_DRY_RUN 已启用，消息未实际发送",
            )

        if not self.settings.webhook_url:
            error = "未配置 DINGTALK_WEBHOOK_URL"
            self.store.mark_failed(dedupe_key, error)
            return NotificationResult(
                success=False,
                status="not_configured",
                attempts=0,
                message=error,
            )

        level_label = {"info": "信息", "warning": "警告", "critical": "严重"}[severity]
        body = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"[{level_label}] {title}",
                "text": (
                    f"### [{level_label}] {title}\n\n"
                    f"{content}\n\n"
                    f"> 事件级别：{severity}\n"
                    f"> 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
            },
        }
        url = signed_webhook_url(self.settings.webhook_url, self.settings.secret)
        last_error = ""
        last_status: int | None = None

        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.request_timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(url, json=body)
                last_status = response.status_code
                try:
                    data = response.json() if response.content else {}
                except ValueError:
                    data = {}
                if response.status_code == 200 and data.get("errcode", 0) == 0:
                    self.store.mark_sent(dedupe_key)
                    return NotificationResult(
                        success=True,
                        status="sent",
                        attempts=attempt,
                        message="钉钉通知发送成功",
                        status_code=response.status_code,
                    )
                last_error = (
                    f"HTTP {response.status_code}: "
                    f"{data.get('errmsg') or response.text[:300]}"
                )
                if response.status_code != 429 and response.status_code < 500:
                    break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            if attempt < self.settings.retry_attempts:
                await asyncio.sleep(
                    self.settings.retry_base_delay_seconds * (2 ** (attempt - 1))
                )

        self.store.mark_failed(dedupe_key, last_error)
        return NotificationResult(
            success=False,
            status="failed",
            attempts=self.settings.retry_attempts,
            message=f"钉钉通知发送失败: {last_error}",
            status_code=last_status,
        )
