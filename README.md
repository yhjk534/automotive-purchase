# 汽车零部件智能采购助手

这是一个可本地完整运行的汽车零部件采购 Agent 示例。项目保留了原 ERP Agent 的
Harness、LangGraph、MCP、SSE、MongoDB、Docker 沙箱和人工审批框架，同时把业务层
改造为乘用车售后零部件采购场景。

> 本项目用于学习、课程展示和内部原型验证，不应直接部署到公网。登录鉴权、用户数据
> 隔离、生产级 ERP 权限控制、HTTPS、限流和审计仍需要在上线前完成。

## 相比原项目新增了什么

- 自带可重复初始化的汽车零部件模拟 ERP，不依赖原远程测试库。
- 新增车型主数据和车型/零件多对多适配关系。
- 支持按品牌、车系、年款、发动机、排量、OE 号和零件来源类型查询。
- 一个零件可以对应多个供应商报价，并记录含税状态、MOQ、交期、准时交付率和质量 PPM。
- 库存包含多仓、预留量、可用量、库位和批次。
- 订单支持订单头/明细、供应商、币种、含税状态和期望到货日期。
- Agent 在查询具体车辆时会先解析 `vehicle_model_id`，再查询适配零件。
- 前端、系统提示词、采购技能、评审标准和演示问题均改为汽车零部件场景。
- 低库存和审批超时自动扫描，按 warning/critical 分级推送钉钉。
- 告警使用持久化去重键，网络异常、限流和服务端错误支持指数退避重试。
- MCP 统一提供财务查询、财务 Markdown 报表生成和钉钉通知发布工具。
- `notification_publish` 作为写操作纳入人工审批。

## 技术栈

| 层次 | 技术 |
|---|---|
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS |
| Web API | FastAPI、SSE |
| Agent | deepagents 0.6.x、LangGraph、LangChain |
| 模型 | 通义千问 `qwen-plus`，OpenAI 兼容接口 |
| ERP 工具 | FastMCP |
| 会话持久化 | MongoDB |
| 本地 ERP | FastAPI + SQLite |
| 代码执行 | Docker 安全沙箱 |

项目固定使用 `deepagents>=0.6.0,<0.7.0`。不要直接升级到 `0.7.x`，因为当前代码使用
旧版 backend factory 接口。

## 项目结构

```text
automotive-purchase/
├── erp_mock/                    汽车零部件模拟 ERP
│   ├── database.py              SQLite 建表与汽车测试数据
│   └── main.py                  ERP REST API
├── frontend/                    Next.js 前端
├── src/
│   ├── agent/                   Agent、子 Agent、工具和中间件
│   ├── api_view/                FastAPI 后端
│   ├── alerts/                  分级告警、去重、重试和钉钉客户端
│   ├── mcp_server/              ERP MCP 工具服务
│   ├── skills/procurement/      汽车零部件采购技能
│   ├── test/                    自动化测试
│   └── security.py              路径、URL、压缩包安全校验
├── docs/
│   ├── AUTOMOTIVE_DOMAIN.md    汽车零部件领域模型说明
│   └── ALERTS_AND_FINANCE.md   告警、财务和通知运维说明
├── scripts/check.ps1            一键测试和前端构建
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## 汽车测试数据

模拟 ERP 首次启动时会自动创建 `data/automotive_erp.db`，并写入：

- 6 家汽车零部件供应商
- 12 个汽车零部件 SKU
- 6 个车型配置
- 30 多条车型适配关系
- 13 个 OE号、规格号或供应商零件号
- 17 条供应商报价
- 12 条多仓库存记录
- 5 张汽车零部件采购订单
- 4 张采购发票及付款进度
- 6 个分类采购预算

代表性测试数据：

| 场景 | 数据 |
|---|---|
| 车型 | 2020—2024 丰田凯美瑞 2.0L M20A |
| 零件 | 前制动片，品牌 ADVICS，来源 OES |
| OE号 | `04465-06120` |
| 供应商报价 | 上海安驰、苏州恒擎、广州德驰 |
| 库存预警 | 前制动片、雅阁前制动片、活性炭空调滤芯等 |

详细关系和字段见 `docs/AUTOMOTIVE_DOMAIN.md`。

## 环境要求

1. Windows PowerShell
2. Python 3.11
3. Node.js 20 或更高版本
4. Docker Desktop
5. MongoDB
6. 可用的通义千问 DashScope API Key

## 第一次配置

进入新项目：

```powershell
cd "C:\Users\32253\Desktop\工作\purchase\automotive-purchase"
```

创建环境变量文件：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少配置：

```dotenv
DASHSCOPE_API_KEY=sk-your-own-key
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=automotive_erp_agent
ERP_BASE_URL=http://127.0.0.1:8081
MCP_SERVER_URL=http://localhost:9000
SANDBOX_IMAGE=python:3.11-slim
CORS_ORIGINS=http://localhost:3000
API_HOST=127.0.0.1
API_PORT=8000
DINGTALK_WEBHOOK_URL=
DINGTALK_SECRET=
DINGTALK_DRY_RUN=true
ALERT_SCHEDULER_ENABLED=true
ALERT_SCAN_INTERVAL_SECONDS=60
APPROVAL_TIMEOUT_MINUTES=60
```

不要提交 `.env`，也不要将真实 API Key 写入 README、截图或 Git。

创建 Python 虚拟环境并安装依赖：

```powershell
C:\conda\envs\purchase\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

如果本机 Python 3.11 路径不同，将第一行替换为实际路径。

安装前端依赖：

```powershell
cd frontend
Copy-Item .env.example .env.local
npm.cmd ci
cd ..
```

## 初始化汽车 ERP 数据

首次启动会自动初始化。如果需要把测试数据恢复到初始状态：

```powershell
.\.venv\Scripts\python.exe -m erp_mock.database
```

注意：该命令会删除并重建 `data/automotive_erp.db`，只应在本项目的测试数据库上使用。

## 启动全部服务

建议为每个服务单独打开一个 PowerShell 窗口。

### 1. 启动 MongoDB

首次运行：

```powershell
docker run -d --name automotive-mongodb -p 27017:27017 mongo:6.0
```

以后只需：

```powershell
docker start automotive-mongodb
```

如果已经存在名为 `mongodb` 的容器，也可以直接复用。

### 2. 启动汽车 ERP 模拟服务

```powershell
cd "C:\Users\32253\Desktop\工作\purchase\automotive-purchase"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m uvicorn erp_mock.main:app --host 127.0.0.1 --port 8081
```

验证：

```text
http://127.0.0.1:8081/health
http://127.0.0.1:8081/docs
```

健康检查应包含供应商、零件、车型、适配关系和订单数量。

### 3. 创建安全沙箱

```powershell
cd "C:\Users\32253\Desktop\工作\purchase\automotive-purchase"
.\.venv\Scripts\python.exe -c "from src.agent.backends.sandbox_setup import create_secure_sandbox; create_secure_sandbox()"
```

### 4. 启动 MCP 服务

```powershell
cd "C:\Users\32253\Desktop\工作\purchase\automotive-purchase"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m src.mcp_server.server_main
```

服务地址：

```text
http://localhost:9000
```

### 5. 启动 FastAPI 后端

```powershell
cd "C:\Users\32253\Desktop\工作\purchase\automotive-purchase"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m src.api_view.web_main
```

验证：

```text
http://localhost:8000/health
http://localhost:8000/docs
```

后端启动后会同时启动告警调度器。默认每 60 秒扫描一次低库存和待审批订单。
未配置钉钉时会保留失败状态；首次验收可先使用 `DINGTALK_DRY_RUN=true`。

### 6. 启动前端

```powershell
cd "C:\Users\32253\Desktop\工作\purchase\automotive-purchase\frontend"
npm.cmd run dev
```

打开：

```text
http://localhost:3000
```

## 推荐的验收对话

### 车型适配和 OE号搜索

> 查询 2021 款丰田凯美瑞 2.0L 适用的前制动片，列出 OE 号、零件品牌、供应商报价和当前库存。

期望行为：

1. Agent 调用 `vehicle_search` 解析凯美瑞车型。
2. 使用 `vehicle_model_id` 和“前制动片”调用 `part_search`。
3. 返回 OE号、车型适配和多供应商报价。
4. 不把 OES 或品牌件描述成原厂件。

### 多供应商比价

> 对比前制动片三家供应商的含税价、MOQ、交货周期、准时交付率和质量 PPM，并给出采购建议。

期望行为：

1. 使用真实供应商报价数据。
2. 至少比较含税价、MOQ、交期、准时交付率和质量 PPM。
3. 生成对比表和建议图表。

### 库存预警

> 查看当前汽车零部件库存预警，按缺货数量和车型专用件优先级排序。

期望行为：

1. 调用 `inventory_warning`。
2. 展示 SKU、仓库、当前量、安全库存、缺口和供应商。
3. 给出补货建议。

### 创建采购订单

> 为 2021 款丰田凯美瑞 2.0L 创建 20 套前制动片采购订单，要求 2026-12-01 前到货。

期望行为：

1. 先确认车型适配和零件。
2. 信息不足时通过 `request_order_info` 询问。
3. 展示零件、供应商、数量、单价和到货日期。
4. 调用 `order_create` 前进入人工审批。
5. 用户批准后才写入 ERP。

### 财务查询与报表

> 查询本月汽车零部件采购、开票、付款、应付和预算使用情况，并生成财务分析报表。

期望行为：

1. 调用 `finance_query` 获取统一财务数据。
2. 调用 `generate_finance_report` 生成 Markdown 报表。
3. 返回报表下载路径和关键财务指标。

### 告警通知

> 检查当前低库存和审批超时风险，并按 warning 或 critical 级别汇总。

期望行为：

1. 读取低库存和多仓可用量。
2. 读取超过审批时限的待审批订单。
3. 使用稳定事件键去重。
4. 通过钉钉发送分级 Markdown 消息。
5. 发送失败时最多重试 3 次。

## 自动化检查

运行后端测试、Python 编译检查和前端生产构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

也可以只运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\.pytest_tmp
```

服务启动后，可以分别验证 MCP 工具和完整 SSE 对话：

```powershell
.\.venv\Scripts\python.exe .\scripts\smoke_mcp.py
.\.venv\Scripts\python.exe .\scripts\smoke_chat.py
.\.venv\Scripts\python.exe .\scripts\smoke_automotive_chat.py
.\.venv\Scripts\python.exe .\scripts\smoke_alerts_finance.py
```

`smoke_automotive_chat.py` 会要求 Agent 实际调用 `vehicle_search` 和
`part_search`，并检查回答中是否包含 OE号 `04465-06120`。

当前新增测试覆盖：

- 汽车测试数据的供应商、零件、车型和适配数量
- 凯美瑞车型解析与适配零件查询
- OE号搜索
- 一个零件的多供应商报价
- 汽车订单统计
- 低库存和审批超时的分级规则
- 钉钉重试和消息去重
- 财务发票、预算和汇总查询
- 财务 Markdown 报表生成
- 活跃提示词和前端中不存在原摩托车术语

## 安全说明

- 写操作通过 `INTERRUPT_ON_TOOLS` 在 Agent 层触发人工审批。
- 通过 Agent 调用写工具时，页面必须批准后才会执行。
- 直接访问 MCP 或模拟 ERP 会绕过该审批，因此服务只应监听本机或可信内网。
- 生产部署应给 ERP 和 MCP 增加鉴权、授权、操作审计和网络隔离。
- 技能安装使用正式 `install_skill` 工具，并对 URL 和压缩包路径做安全校验。
- `notification_publish` 通过 Agent 调用时需要人工审批。
- 告警去重和发送状态保存在 `data/alert_state.db`，不会因服务重启重复发送。
- 沙箱创建失败时不应在生产环境自动回退到普通容器。

## 常见问题

### ERP health 正常，但 Agent 查询不到车型

确认 MCP 服务启动时连接的是 `http://127.0.0.1:8081`，并检查 MCP 日志是否加载了
`vehicle_search` 工具。

### 修改测试数据后需要恢复

执行：

```powershell
.\.venv\Scripts\python.exe -m erp_mock.database
```

### MongoDB 会话混入了旧项目历史

确认 `.env` 中的：

```dotenv
MONGODB_DB_NAME=automotive_erp_agent
```

与原项目使用不同的数据库名。

### MCP 没有加载 ERP 工具

先确保汽车 ERP 启动成功，再重启 MCP 和 FastAPI。MCP 工具只在 Agent 初始化时加载。

### SSE 返回 401 Incorrect API key

`.env` 中的 `DASHSCOPE_API_KEY` 无效。请换成你的有效通义千问 DashScope Key，然后
重启 FastAPI。不要把真实 Key 提交到 Git 或发送到公开聊天中。

### 钉钉没有收到消息

1. 检查 FastAPI 日志与 `GET /api/alerts/status`。
2. 确认 `DINGTALK_WEBHOOK_URL` 和加签 `DINGTALK_SECRET` 正确。
3. 将 `DINGTALK_DRY_RUN` 设为 `false`。
4. 手动执行 `POST /api/alerts/scan`。
5. 相同事件在去重窗口内不会重复发送。

## 与原项目的关系

本项目位于独立目录：

```text
C:\Users\32253\Desktop\工作\purchase\automotive-purchase
```

原项目：

```text
C:\Users\32253\Desktop\工作\purchase\改进项目
```

改造不会修改原项目。汽车版使用自己的 SQLite 测试数据库、MongoDB 数据库名、提示词、
技能和前端文案，可以与原项目并行运行和对照。
