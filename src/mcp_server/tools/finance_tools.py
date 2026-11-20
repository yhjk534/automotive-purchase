"""Unified MCP finance, report, and notification tools."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP

from ...alerts.config import AlertSettings
from ...alerts.dingtalk import DingTalkNotifier
from ..http_base import erp_client

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOWNLOAD_DIR = PROJECT_ROOT / "src" / "download"


def _money(value: float | int | None) -> str:
    return f"¥{float(value or 0):,.2f}"


def build_finance_report(summary: dict, invoices: list[dict]) -> str:
    category_rows = "\n".join(
        f"| {item['category']} | {_money(item['amount'])} |"
        for item in summary.get("categoryBreakdown", [])
    ) or "| 暂无数据 | ¥0.00 |"
    supplier_rows = "\n".join(
        f"| {item['supplier_name']} | {item['order_count']} | {_money(item['amount'])} |"
        for item in summary.get("supplierBreakdown", [])
    ) or "| 暂无数据 | 0 | ¥0.00 |"
    invoice_rows = "\n".join(
        "| {invoice_no} | {order_number} | {supplier_name} | {amount} | {paid} | {outstanding} | {status} |".format(
            invoice_no=item.get("invoice_no", ""),
            order_number=item.get("order_number", ""),
            supplier_name=item.get("supplier_name", ""),
            amount=_money(item.get("amount")),
            paid=_money(item.get("paid_amount")),
            outstanding=_money(float(item.get("amount") or 0) - float(item.get("paid_amount") or 0)),
            status=item.get("status", ""),
        )
        for item in invoices
    ) or "| 暂无发票 | - | - | ¥0.00 | ¥0.00 | ¥0.00 | - |"

    return f"""# 汽车零部件采购财务分析报告

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 核心指标

| 指标 | 金额/数值 |
|---|---:|
| 订单数量 | {summary.get('order_count', 0)} |
| 采购订单金额 | {_money(summary.get('order_amount'))} |
| 待审批金额 | {_money(summary.get('pending_approval_amount'))} |
| 在途金额 | {_money(summary.get('in_transit_amount'))} |
| 已开票金额 | {_money(summary.get('invoiced_amount'))} |
| 已付款金额 | {_money(summary.get('paid_amount'))} |
| 未付款金额 | {_money(summary.get('outstanding_amount'))} |
| 逾期发票数量 | {summary.get('overdue_invoice_count', 0)} |
| 预算金额 | {_money(summary.get('budget_amount'))} |
| 预算使用金额 | {_money(summary.get('budget_used_amount'))} |
| 预算使用率 | {float(summary.get('budget_utilization') or 0) * 100:.1f}% |

## 分类采购金额

| 分类 | 金额 |
|---|---:|
{category_rows}

## 供应商采购金额

| 供应商 | 订单数 | 金额 |
|---|---:|---:|
{supplier_rows}

## 发票与应付

| 发票号 | 订单号 | 供应商 | 开票金额 | 已付 | 未付 | 状态 |
|---|---|---|---:|---:|---:|---|
{invoice_rows}

## 管理建议

1. 优先处理待审批金额和逾期发票，避免影响供应商交付。
2. 对预算使用率超过 80% 的类别限制非紧急采购。
3. 未付款金额较高的供应商应结合交期和信用评级进行综合评估。
"""


def register_finance_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def finance_query(
        start_date: str = None,
        end_date: str = None,
        supplier_id: int = None,
        category: str = None,
    ) -> str:
        """统一查询采购、发票、应付、预算和供应商财务数据。

        Args:
            start_date: 开始日期，格式 yyyy-MM-dd
            end_date: 结束日期，格式 yyyy-MM-dd
            supplier_id: 供应商ID筛选
            category: 汽车零件分类筛选

        Returns:
            汇总指标、分类金额、供应商金额、预算和财务明细JSON
        """
        summary = await erp_client.get(
            "/api/finance/summary",
            params={
                "startDate": start_date,
                "endDate": end_date,
                "supplierId": supplier_id,
                "category": category,
            },
        )
        invoices = await erp_client.get(
            "/api/finance/invoices",
            params={
                "startDate": start_date,
                "endDate": end_date,
                "supplierId": supplier_id,
            },
        )
        return json.dumps(
            {"summary": summary, "invoices": invoices},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def generate_finance_report(
        start_date: str = None,
        end_date: str = None,
        filename: str = "",
    ) -> str:
        """生成汽车零部件采购财务 Markdown 报表并保存为可下载文件。

        Args:
            start_date: 开始日期，格式 yyyy-MM-dd
            end_date: 结束日期，格式 yyyy-MM-dd
            filename: 可选文件名，不包含路径；为空则自动生成

        Returns:
            报表文件路径、下载URL和核心摘要JSON
        """
        summary = await erp_client.get(
            "/api/finance/summary",
            params={"startDate": start_date, "endDate": end_date},
        )
        invoices = await erp_client.get(
            "/api/finance/invoices",
            params={"startDate": start_date, "endDate": end_date},
        )
        markdown = build_finance_report(summary, invoices)
        safe_name = re.sub(r"[^\w\-.\u4e00-\u9fff]", "_", filename or "").strip("._")
        if not safe_name:
            safe_name = f"汽车零部件财务报告_{datetime.now():%Y%m%d_%H%M%S}.md"
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target = DOWNLOAD_DIR / safe_name
        target.write_text(markdown, encoding="utf-8")
        return json.dumps(
            {
                "success": True,
                "filename": safe_name,
                "path": str(target),
                "downloadUrl": f"http://localhost:8000/api/download/{safe_name}",
                "summary": {
                    "order_amount": summary.get("order_amount", 0),
                    "outstanding_amount": summary.get("outstanding_amount", 0),
                    "pending_approval_amount": summary.get(
                        "pending_approval_amount", 0
                    ),
                    "budget_utilization": summary.get("budget_utilization", 0),
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def notification_publish(
        title: str,
        content: str,
        severity: str = "info",
        dedupe_key: str = "",
    ) -> str:
        """通过统一通知网关向钉钉发布消息。

        Args:
            title: 消息标题
            content: Markdown消息正文
            severity: info / warning / critical
            dedupe_key: 可选去重键；为空时根据标题和正文生成

        Returns:
            发送状态、尝试次数和去重结果JSON
        """
        key = dedupe_key or (
            "mcp_notification:"
            + hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()[:24]
        )
        notifier = DingTalkNotifier(AlertSettings.from_env())
        result = await notifier.publish(
            title=title,
            content=content,
            severity=severity,
            dedupe_key=key,
            alert_type="mcp_notification",
            payload={"title": title, "content": content, "severity": severity},
        )
        return json.dumps(result.__dict__, ensure_ascii=False, indent=2)
