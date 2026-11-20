# 汽车零部件领域模型

## 设计目标

Agent 不直接依赖某个 ERP 厂商的原始字段。MCP 工具向 Agent 暴露稳定的汽车零部件
数据契约，底层 ERP 负责存储，模拟 ERP 负责在本机复现同一类接口。

```text
Agent
  ↓
MCP Tool：稳定的汽车零部件字段
  ↓
ERP Adapter：分页、字段映射、单位转换、错误归一化
  ↓
汽车 ERP / SQLite 模拟服务
```

## 核心关系

```text
Supplier ──< SupplierOffer >── Part ──< PartFitment >── VehicleModel
                                  │
                                  ├──< PartNumber
                                  ├──< Inventory
                                  └──< PurchaseOrderDetail

PurchaseOrder ──< PurchaseOrderDetail
PurchaseOrder ── Supplier
Inventory ── Warehouse location / bin / batch
```

关键关系：

- 一个零件可以适配多个车型。
- 一个车型可以适配多个零件。
- 一个零件可以由多个供应商供货。
- 同一零件的不同供应商可以有不同报价、MOQ、交期和质量表现。
- 一个零件可以有多个 OE号、OES号、替代号或供应商零件号。
- 库存按仓库、库位、批次、预留量区分。

## 实体

### Supplier

| 字段 | 说明 |
|---|---|
| `supplier_code` | 供应商编码 |
| `name` | 企业名称 |
| `credit_rating` | 信用等级 |
| `on_time_rate` | 准时交付率 |
| `quality_ppm` | 每百万件不良数 |
| `monthly_capacity` | 月供货能力 |
| `status` | 1=合作中，0=停用 |

### VehicleModel

| 字段 | 说明 |
|---|---|
| `brand` | 品牌 |
| `series` | 车系 |
| `model_name` | 车型 |
| `year_start/year_end` | 年款范围 |
| `engine` | 发动机代码 |
| `displacement` | 排量 |
| `market` | 销售区域 |

### Part

| 字段 | 说明 |
|---|---|
| `part_code` | 内部零件编码 |
| `name` | 零件名称 |
| `category` | 制动、过滤、悬挂等分类 |
| `brand` | 零件品牌 |
| `position` | 安装位置 |
| `origin_type` | OEM/OES/品牌件/拆车件 |
| `warranty_months` | 质保月数 |
| `purchase_price` | 主供应商参考采购价 |
| `supplier_id` | 主供应商，仅用于兼容基础接口 |

### PartNumber

用于保存多个编号，不以 OE号充当数据库主键。

| 字段 | 说明 |
|---|---|
| `part_id` | 内部零件ID |
| `number` | OE号、规格号、替代号或供应商编号 |
| `number_type` | 编号类型 |
| `brand` | 编号所属品牌 |

### PartFitment

零件与车型的多对多关系。

| 字段 | 说明 |
|---|---|
| `part_id` | 零件ID |
| `vehicle_model_id` | 车型ID |
| `position` | 前、后、左前等位置 |
| `note` | 适配补充说明 |

### SupplierOffer

供应商与零件的多对多报价关系。

| 字段 | 说明 |
|---|---|
| `supplier_id` | 供应商ID |
| `part_id` | 零件ID |
| `supplier_part_no` | 供应商零件号 |
| `purchase_price` | 报价 |
| `currency` | 币种 |
| `tax_included` | 是否含税 |
| `moq` | 最小起订量 |
| `lead_time_days` | 交货周期 |
| `valid_from/valid_to` | 报价有效期 |

### Inventory

| 字段 | 说明 |
|---|---|
| `part_id` | 零件ID |
| `warehouse_location` | 仓库 |
| `bin_location` | 库位 |
| `batch_number` | 批次 |
| `current_quantity` | 当前数量 |
| `reserved_quantity` | 已预留 |
| `available_quantity` | 当前数量减预留数量 |
| `safety_stock` | 安全库存 |

### PurchaseOrder / PurchaseOrderDetail

订单头负责供应商、币种、含税状态和期望到货日；订单明细负责零件、数量、单价和
要求到货日。

## MCP 数据契约

### 车型解析

```text
vehicle_search(keyword="丰田 凯美瑞 2.0L")
```

返回：

```json
{
  "id": 1,
  "brand": "丰田",
  "series": "凯美瑞",
  "year_start": 2020,
  "year_end": 2024,
  "engine": "M20A",
  "displacement": "2.0L"
}
```

### 零件查询

```text
part_search(
  name="前制动片",
  vehicle_model_id=1,
  oe_number="04465-06120"
)
```

返回的每个零件包含：

- `oeNumbers`
- `fitments`
- `supplierOffers`
- 品牌、来源类型、质保期

### 订单创建

Agent 仍通过 `order_create(order_data)` 提交 JSON。推荐字段：

```json
{
  "orderNumber": "PO20261119001",
  "supplierId": 1,
  "currency": "CNY",
  "taxIncluded": 1,
  "expectedDate": "2026-12-01",
  "remark": "凯美瑞前制动片补货",
  "orderDetail": [
    {
      "partId": 1,
      "quantity": 20,
      "unitPrice": 268.5,
      "requiredDate": "2026-12-01",
      "remark": "OES 前轴套装"
    }
  ]
}
```

## 从其他 ERP 接入

如果已有汽车 ERP：

1. 保留 ERP 作为主数据源。
2. 定义 MCP 返回契约。
3. 在 MCP 工具中把 ERP 字段映射成上述契约。
4. 不要将车型适配解析为自由文本后交给模型猜测。
5. 无法确认适配关系时，应明确返回“未找到适配数据”。

如果现有 ERP 缺少车型适配或 OE号：

1. 在 ERP 中增加车型、适配和零件编号表。
2. 或者建立由 ERP 统一管理的伴随表。
3. 不建议把适配关系塞进 `description` 或 `remark`。
4. 不建议只修改提示词而不修改数据。

## 安全边界

- MongoDB 保存 Agent 会话、checkpoint 和用户偏好，不作为汽车 ERP 主数据源。
- 供应商、零件、报价、车型适配、库存和订单由 ERP 管理。
- 创建、修改订单和调整库存需要人工审批。
- MCP 和模拟 ERP 当前没有登录鉴权，只适合本地和可信内网。
