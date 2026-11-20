"""Low-stock and overdue-approval alert scanning."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from ..agent.env_utils import get_env
from ..agent.log_utils import web_logger
from .config import AlertSettings
from .dingtalk import DingTalkNotifier


@dataclass
class AlertEvent:
    event_key: str
    alert_type: str
    severity: str
    title: str
    content: str
    payload: dict[str, Any]


def low_stock_severity(item: dict[str, Any]) -> str:
    current = float(item.get("current_quantity") or item.get("quantity") or 0)
    safety = max(float(item.get("safety_stock") or 0), 1.0)
    shortage_ratio = (safety - current) / safety
    return "critical" if current <= 0 or shortage_ratio >= 0.5 else "warning"


def approval_severity(
    order: dict[str, Any],
    *,
    timeout_minutes: int,
    critical_multiplier: float,
    critical_amount: float,
) -> tuple[str, float] | None:
    try:
        order_time = datetime.fromisoformat(str(order["order_time"]))
    except (KeyError, TypeError, ValueError):
        return None
    hours_waiting = max(0.0, (datetime.now() - order_time).total_seconds() / 3600)
    if hours_waiting < timeout_minutes / 60:
        return None
    critical = (
        hours_waiting >= (timeout_minutes / 60) * critical_multiplier
        or float(order.get("total_amount") or 0) >= critical_amount
    )
    return ("critical" if critical else "warning", hours_waiting)


class AlertService:
    def __init__(self, settings: AlertSettings | None = None):
        self.settings = settings or AlertSettings.from_env()
        self.erp_base_url = get_env("ERP_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
        self.notifier = DingTalkNotifier(self.settings)
        self.last_scan_at: str | None = None
        self.last_scan_result: dict[str, Any] = {}

    def evaluate_inventory(self, items: list[dict[str, Any]]) -> list[AlertEvent]:
        events: list[AlertEvent] = []
        today = datetime.now().strftime("%Y-%m-%d")
        for item in items:
            severity = low_stock_severity(item)
            part_id = item.get("part_id")
            warehouse = item.get("warehouse_location") or "未知仓库"
            event_key = f"low_stock:{today}:{warehouse}:{part_id}:{severity}"
            current = item.get("current_quantity") or item.get("quantity") or 0
            content = (
                f"- 零件：**{item.get('part_name', '未知')}** "
                f"({item.get('part_code', '')})\n"
                f"- 分类：{item.get('category', '未分类')}\n"
                f"- 仓库：{warehouse}\n"
                f"- 当前库存：{current}，安全库存：{item.get('safety_stock')}，"
                f"缺口：{item.get('shortage', '未知')}\n"
                f"- 主供应商：{item.get('supplier_name', '未指定')}"
            )
            events.append(
                AlertEvent(
                    event_key=event_key,
                    alert_type="low_stock",
                    severity=severity,
                    title=f"低库存预警：{item.get('part_name', '未知零件')}",
                    content=content,
                    payload={
                        **item,
                        "severity": severity,
                        "dedupe_key": event_key,
                    },
                )
            )
        return events

    def evaluate_approval_timeouts(
        self, orders: list[dict[str, Any]]
    ) -> list[AlertEvent]:
        events: list[AlertEvent] = []
        for order in orders:
            result = approval_severity(
                order,
                timeout_minutes=self.settings.approval_timeout_minutes,
                critical_multiplier=self.settings.critical_timeout_multiplier,
                critical_amount=self.settings.critical_order_amount,
            )
            if result is None:
                continue
            severity, hours_waiting = result
            order_id = order.get("id")
            event_key = f"approval_timeout:{order_id}:{severity}"
            content = (
                f"- 订单：**{order.get('order_number', order_id)}**\n"
                f"- 供应商：{order.get('supplier_name', '未指定')}\n"
                f"- 金额：¥{float(order.get('total_amount') or 0):,.2f}\n"
                f"- 已等待：{hours_waiting:.1f} 小时\n"
                f"- 审批阈值：{self.settings.approval_timeout_minutes} 分钟"
            )
            events.append(
                AlertEvent(
                    event_key=event_key,
                    alert_type="approval_timeout",
                    severity=severity,
                    title=f"采购审批超时：{order.get('order_number', order_id)}",
                    content=content,
                    payload={
                        **order,
                        "hours_waiting": round(hours_waiting, 2),
                        "severity": severity,
                        "dedupe_key": event_key,
                    },
                )
            )
        return events

    async def scan_once(self) -> dict[str, Any]:
        result = {
            "inventory_found": 0,
            "approval_found": 0,
            "sent": 0,
            "duplicates": 0,
            "failed": 0,
            "errors": [],
        }
        async with httpx.AsyncClient(
            base_url=self.erp_base_url,
            timeout=15.0,
        ) as client:
            try:
                inventory_response = await client.get("/api/inventory/warning")
                inventory_response.raise_for_status()
                inventory_items = inventory_response.json()
            except Exception as exc:
                result["errors"].append(f"库存扫描失败: {exc}")
                inventory_items = []

            try:
                orders_response = await client.get(
                    "/api/orders/page",
                    params={"current": 1, "size": 100, "status": 0},
                )
                orders_response.raise_for_status()
                orders = orders_response.json().get("records", [])
            except Exception as exc:
                result["errors"].append(f"订单审批扫描失败: {exc}")
                orders = []

        inventory_events = self.evaluate_inventory(inventory_items)
        approval_events = self.evaluate_approval_timeouts(orders)
        result["inventory_found"] = len(inventory_events)
        result["approval_found"] = len(approval_events)

        for event in [*inventory_events, *approval_events]:
            notification = await self.notifier.publish(
                title=event.title,
                content=event.content,
                severity=event.severity,
                dedupe_key=event.event_key,
                alert_type=event.alert_type,
                payload=event.payload,
            )
            if notification.status == "duplicate_skipped":
                result["duplicates"] += 1
            elif notification.success:
                result["sent"] += 1
            else:
                result["failed"] += 1
                result["errors"].append(notification.message)

        self.last_scan_at = datetime.now().isoformat()
        self.last_scan_result = result
        web_logger.info(f"Alert scan completed: {result}")
        return result

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.enabled,
            "webhook_configured": bool(self.settings.webhook_url),
            "dry_run": self.settings.dry_run,
            "approval_timeout_minutes": self.settings.approval_timeout_minutes,
            "scan_interval_seconds": self.settings.scan_interval_seconds,
            "last_scan_at": self.last_scan_at,
            "last_scan_result": self.last_scan_result,
            "delivery_state": self.notifier.store.status(),
        }


class AlertScheduler:
    def __init__(self, service: AlertService):
        self.service = service
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        while True:
            try:
                await self.service.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                web_logger.error(f"Scheduled alert scan failed: {exc}", exc_info=True)
            await asyncio.sleep(self.service.settings.scan_interval_seconds)

    def start(self) -> None:
        if not self.service.settings.enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="alert-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


alert_service = AlertService()
alert_scheduler = AlertScheduler(alert_service)
