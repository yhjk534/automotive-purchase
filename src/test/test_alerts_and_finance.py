"""Tests for tiered alerts, deduplication, retry, finance, and reports."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from src.alerts.config import AlertSettings
from src.alerts.dingtalk import DingTalkNotifier
from src.alerts.service import AlertService, approval_severity, low_stock_severity
from src.mcp_server.tools.finance_tools import build_finance_report


def _settings(tmp_path, **overrides) -> AlertSettings:
    settings = AlertSettings(
        enabled=True,
        webhook_url="https://dingtalk.invalid/robot/send",
        secret="test-secret",
        dry_run=False,
        retry_attempts=3,
        retry_base_delay_seconds=0,
        request_timeout_seconds=1,
        dedupe_cooldown_seconds=3600,
        state_db=tmp_path / "alerts.db",
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


@pytest.mark.asyncio
async def test_dingtalk_retries_then_deduplicates(tmp_path):
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, text="temporary")
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    notifier = DingTalkNotifier(
        _settings(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    first = await notifier.publish(
        title="库存告警",
        content="前制动片库存不足",
        severity="critical",
        dedupe_key="stock:1",
    )
    second = await notifier.publish(
        title="库存告警",
        content="前制动片库存不足",
        severity="critical",
        dedupe_key="stock:1",
    )

    assert first.success
    assert first.attempts == 2
    assert second.status == "duplicate_skipped"
    assert attempts == 2


@pytest.mark.asyncio
async def test_dingtalk_retries_network_failure(tmp_path):
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("offline")

    notifier = DingTalkNotifier(
        _settings(tmp_path, retry_attempts=3),
        transport=httpx.MockTransport(handler),
    )
    result = await notifier.publish(
        title="审批超时",
        content="订单等待审批",
        severity="warning",
        dedupe_key="approval:1",
    )

    assert not result.success
    assert result.attempts == 3
    assert attempts == 3


def test_low_stock_and_approval_severity_tiers():
    assert low_stock_severity(
        {"current_quantity": 42, "safety_stock": 100}
    ) == "critical"
    assert low_stock_severity(
        {"current_quantity": 80, "safety_stock": 100}
    ) == "warning"

    warning_order = {
        "order_time": (datetime.now() - timedelta(minutes=90)).isoformat(),
        "total_amount": 1000,
    }
    critical_order = {
        "order_time": (datetime.now() - timedelta(hours=3)).isoformat(),
        "total_amount": 1000,
    }
    assert approval_severity(
        warning_order,
        timeout_minutes=60,
        critical_multiplier=2,
        critical_amount=50000,
    )[0] == "warning"
    assert approval_severity(
        critical_order,
        timeout_minutes=60,
        critical_multiplier=2,
        critical_amount=50000,
    )[0] == "critical"


def test_alert_event_keys_are_stable(tmp_path):
    service = AlertService(_settings(tmp_path))
    inventory = service.evaluate_inventory(
        [
            {
                "part_id": 1,
                "part_name": "前制动片",
                "part_code": "BRK-PAD-CAMRY-F",
                "category": "制动系统",
                "warehouse_location": "华东中心仓",
                "current_quantity": 20,
                "safety_stock": 80,
                "shortage": 60,
                "supplier_name": "上海安驰",
            }
        ]
    )
    assert len(inventory) == 1
    assert inventory[0].severity == "critical"
    assert inventory[0].event_key.startswith("low_stock:")


def test_finance_report_contains_automotive_metrics():
    markdown = build_finance_report(
        {
            "order_count": 2,
            "order_amount": 12000,
            "pending_approval_amount": 3400,
            "in_transit_amount": 5200,
            "invoiced_amount": 10640,
            "paid_amount": 9440,
            "outstanding_amount": 1200,
            "overdue_invoice_count": 1,
            "budget_amount": 15000,
            "budget_used_amount": 12000,
            "budget_utilization": 0.8,
            "categoryBreakdown": [{"category": "制动系统", "amount": 5360}],
            "supplierBreakdown": [
                {"supplier_name": "上海安驰", "order_count": 1, "amount": 5360}
            ],
        },
        [
            {
                "invoice_no": "INV-1",
                "order_number": "PO-1",
                "supplier_name": "上海安驰",
                "amount": 5360,
                "paid_amount": 5360,
                "status": "已付款",
            }
        ],
    )
    assert "汽车零部件采购财务分析报告" in markdown
    assert "预算使用率" in markdown
    assert "上海安驰" in markdown
