"""Verify the automotive MCP tools against the running mock ERP."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

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
    tools = {tool.name: tool for tool in await load_mcp_tools(force_refresh=True)}
    assert "vehicle_search" in tools
    assert len(tools) >= 24

    vehicles = parse_tool_content(
        await tools["vehicle_search"].ainvoke({"keyword": "凯美瑞"})
    )
    camry = next(item for item in vehicles if item["series"] == "凯美瑞")
    parts = parse_tool_content(
        await tools["part_search"].ainvoke(
            {"name": "前制动片", "vehicle_model_id": camry["id"]}
        )
    )
    part = parts[0]
    warnings = parse_tool_content(await tools["inventory_warning"].ainvoke({}))

    print(
        json.dumps(
            {
                "tool_count": len(tools),
                "vehicle": f"{camry['brand']} {camry['series']} {camry['displacement']}",
                "part": part["name"],
                "oe_numbers": [item["number"] for item in part["oeNumbers"]],
                "supplier_offer_count": len(part["supplierOffers"]),
                "inventory_warning_count": len(warnings),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
