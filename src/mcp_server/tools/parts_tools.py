"""汽车零部件管理 MCP 工具。

vehicle_search / part_query / part_search / part_by_supplier / part_page / part_create
"""
import json
from fastmcp import FastMCP
from ..http_base import erp_client


def register_parts_tools(mcp: FastMCP):
    """注册零部件管理工具到 MCP Server"""

    @mcp.tool()
    async def part_query(id: int) -> str:
        """获取单个汽车零部件的详细信息。

        Args:
            id: 零部件ID

        Returns:
            零部件详细信息JSON，包含 OE号、品牌、车型适配、供应商报价和库存。
        """
        result = await erp_client.get(f"/api/parts/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_search(
        name: str = None,
        category: str = None,
        vehicle_model_id: int = None,
        oe_number: str = None,
        origin_type: str = None,
        supplier_id: int = None,
    ) -> str:
        """搜索汽车零部件，可组合名称、车型、OE号和零件来源筛选。

        Args:
            name: 零件名称、编码或品牌关键字，例如"前制动片"、"DENSO"
            category: 分类，例如"制动系统"、"过滤系统"、"悬挂系统"
            vehicle_model_id: 车型ID；应先用 vehicle_search 解析车型
            oe_number: OE号或替代零件号
            origin_type: OEM / OES / 品牌件 / 拆车件
            supplier_id: 可供应该零件的供应商ID

        Returns:
            匹配的汽车零部件列表JSON，包含车型适配和供应商报价
        """
        params = {
            "name": name,
            "category": category,
            "vehicle_model_id": vehicle_model_id,
            "oe_number": oe_number,
            "origin_type": origin_type,
            "supplier_id": supplier_id,
        }
        result = await erp_client.get("/api/parts/search", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def vehicle_search(keyword: str) -> str:
        """按品牌、车系、车型、发动机或排量查找车型ID。

        用户提到具体车型时，应先调用此工具解析车型，再将返回的
        vehicle_model_id 传给 part_search。

        Args:
            keyword: 车型关键字，例如“丰田 凯美瑞”“M20A”“2.0L”

        Returns:
            匹配车型列表JSON，每条包含 vehicle_model_id 和年款范围
        """
        result = await erp_client.get("/api/vehicles/search", params={"keyword": keyword})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_by_supplier(supplier_id: int) -> str:
        """获取指定供应商的所有产品列表。

        Args:
            supplier_id: 供应商ID

        Returns:
            该供应商提供的零部件列表JSON
        """
        result = await erp_client.get(f"/api/parts/supplier/{supplier_id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_page(
        current: int = 1,
        size: int = 10,
        name: str = None,
        category: str = None,
        supplier_id: int = None,
        vehicle_model_id: int = None,
        oe_number: str = None,
        origin_type: str = None,
    ) -> str:
        """分页查询零部件列表。

        Args:
            current: 当前页码，默认1
            size: 每页大小，默认10
            name: 零件名称（可选，模糊匹配）
            category: 分类（可选），例如"制动系统"、"过滤系统"、"悬挂系统"
            supplier_id: 供应商ID（可选）
            vehicle_model_id: 适配车型ID（可选）
            oe_number: OE号（可选）
            origin_type: OEM/OES/品牌件/拆车件（可选）

        Returns:
            分页零部件数据JSON，包含 records, total, current, size, pages
        """
        params = {
            "current": current,
            "size": size,
            "name": name,
            "category": category,
            "supplierId": supplier_id,
            "vehicleModelId": vehicle_model_id,
            "oeNumber": oe_number,
            "originType": origin_type,
        }
        result = await erp_client.get("/api/parts/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_create(
        part_code: str,
        name: str,
        purchase_price: float,
        model: str = None,
        specification: str = None,
        unit: str = None,
        suggested_retail_price: float = None,
        stock_warning_value: int = None,
        supplier_id: int = None,
        category: str = None,
        description: str = None,
        brand: str = None,
        position: str = None,
        origin_type: str = "品牌件",
        warranty_months: int = 0,
    ) -> str:
        """创建新零部件。

        Args:
            part_code: 零件编码（必填）
            name: 零件名称（必填）
            purchase_price: 采购单价（必填，>=0）
            model: 型号
            specification: 规格
            unit: 单位（个/套/件）
            suggested_retail_price: 建议零售价
            stock_warning_value: 库存预警值
            supplier_id: 供应商ID
            category: 分类
            description: 描述
            brand: 零件品牌，例如 BOSCH、DENSO
            position: 安装位置，例如左前、后轴
            origin_type: OEM / OES / 品牌件 / 拆车件
            warranty_months: 质保月数

        Returns:
            创建结果JSON
        """
        data = {
            "partCode": part_code,
            "name": name,
            "purchasePrice": purchase_price,
            "model": model,
            "specification": specification,
            "unit": unit,
            "suggestedRetailPrice": suggested_retail_price,
            "stockWarningValue": stock_warning_value,
            "supplierId": supplier_id,
            "category": category,
            "description": description,
            "brand": brand,
            "position": position,
            "originType": origin_type,
            "warrantyMonths": warranty_months,
        }
        data = {k: v for k, v in data.items() if v is not None}
        result = await erp_client.post("/api/parts/create", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)
