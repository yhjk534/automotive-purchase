"""Verify alert scanning, finance MCP tools, reports, and notification publishing."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent.tools.mcp_client import load_mcp_tools


def parse_tool_content(content):
    if isinstance(content, str):
        return json.loads(content)
    if isinstance(content, list) and content and isinstance(content[0], dict):
        text = content[0].get("text")
        if text:
            return json.loads(text)
    return content


async def main() -> None:
    with httpx.Client(timeout=30) as client:
        finance = client.get("http://127.0.0.1:8081/api/finance/summary").json()
        first_scan = client.post("http://127.0.0.1:8000/api/alerts/scan").json()
        second_scan = client.post("http://127.0.0.1:8000/api/alerts/scan").json()
        alert_status = client.get("http://127.0.0.1:8000/api/alerts/status").json()

    assert finance["invoiced_amount"] > 0
    assert finance["budget_amount"] > 0
    assert second_scan["duplicates"] >= first_scan["duplicates"]

    tools = {tool.name: tool for tool in await load_mcp_tools(force_refresh=True)}
    required = {"finance_query", "generate_finance_report", "notification_publish"}
    assert required <= set(tools)

    finance_result = parse_tool_content(
        await tools["finance_query"].ainvoke({})
    )
    report_result = parse_tool_content(
        await tools["generate_finance_report"].ainvoke({})
    )
    notification_result = parse_tool_content(
        await tools["notification_publish"].ainvoke(
            {
                "title": "汽车采购系统验收",
                "content": "低库存与审批超时告警链路验收成功。",
                "severity": "info",
                "dedupe_key": f"smoke:notification:{int(time.time())}",
            }
        )
    )

    assert finance_result["summary"]["order_amount"] > 0
    assert Path(report_result["path"]).exists()
    assert notification_result["success"]

    print(
        json.dumps(
            {
                "mcp_tool_count": len(tools),
                "finance_order_amount": finance_result["summary"]["order_amount"],
                "outstanding_amount": finance_result["summary"]["outstanding_amount"],
                "report_path": report_result["path"],
                "alert_first_scan": first_scan,
                "alert_second_scan": second_scan,
                "alert_delivery_state": alert_status["delivery_state"],
                "notification_status": notification_result["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
