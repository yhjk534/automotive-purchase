# 分级告警、财务与通知

## 1. 告警架构

```text
FastAPI 告警调度器（默认每 60 秒）
    ├── ERP /api/inventory/warning
    └── ERP /api/orders/page?status=0
              ↓
        分级评估
              ↓
   SQLite 去重与发送状态
              ↓
      钉钉 Webhook 客户端
              ↓
     网络/429/5xx 指数退避重试
```

## 2. 告警分级

### 低库存

- `critical`：当前库存为 0，或缺货比例达到安全库存的 50%。
- `warning`：当前库存低于安全库存，但缺货比例不足 50%。

去重键：

```text
low_stock:{日期}:{仓库}:{零件ID}:{级别}
```

同一零件、同一仓库、同一级别每天最多发送一次。

### 审批超时

- `warning`：待审批时间超过 `APPROVAL_TIMEOUT_MINUTES`。
- `critical`：等待时间达到严重阈值，或订单金额达到
  `APPROVAL_CRITICAL_AMOUNT`。

默认严重阈值是普通超时阈值的 2 倍。

去重键：

```text
approval_timeout:{订单ID}:{级别}
```

同一订单在 warning 和 critical 阶段各发送一次。

## 3. 钉钉配置

在钉钉群中添加自定义机器人，安全设置选择“加签”，然后配置：

```dotenv
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=...
DINGTALK_SECRET=SEC...
DINGTALK_DRY_RUN=false
```

本地演示可保持：

```dotenv
DINGTALK_DRY_RUN=true
```

Dry-run 仍会执行去重和状态记录，但不会真正请求钉钉。

## 4. 重试策略

钉钉客户端默认：

- 最大尝试次数：3
- 初始等待：1 秒
- 退避因子：2
- 重试条件：网络错误、超时、HTTP 429、HTTP 5xx
- 不重试条件：其他 4xx 或钉钉业务错误

可通过环境变量调整：

```dotenv
DINGTALK_RETRY_ATTEMPTS=3
DINGTALK_RETRY_BASE_DELAY=1
DINGTALK_TIMEOUT_SECONDS=10
```

## 5. 去重状态

状态保存在：

```text
data/alert_state.db
```

表 `notification_events` 记录：

- 事件键
- 告警类型和级别
- 载荷
- 当前状态
- 尝试次数
- 最近尝试时间
- 最近成功时间
- 最近错误

去重键使用 SQLite 事务原子认领，避免同一进程的并发扫描重复发送。

## 6. 告警 API

```text
GET  /api/alerts/status
POST /api/alerts/scan
```

`status` 返回调度器、去重存储和最近扫描结果。`scan` 用于手动执行一次扫描，
适合联调和运维排查。

## 7. 财务数据模型

### finance_invoice

记录订单发票、应付、已付款和状态。

### budget

记录采购期间、零件分类和预算金额。

### 财务指标

- 采购订单金额
- 待审批金额
- 在途金额
- 开票金额
- 已付款金额
- 未付款金额
- 逾期发票数
- 预算金额、已用金额和使用率
- 分类采购金额
- 供应商采购金额

## 8. MCP 统一工具

### finance_query

统一查询采购、发票、应付、预算、供应商和分类数据。

### generate_finance_report

生成 Markdown 财务报告并保存到 `src/download/`。返回：

- 文件名
- 本地路径
- 下载 URL
- 核心财务摘要

### notification_publish

通过同一套钉钉客户端发布消息，并复用消息去重和失败重试。

Agent 调用该工具时，`notification_publish` 已加入
`INTERRUPT_ON_TOOLS`，必须经过人工审批。

## 9. 生产部署建议

- MCP、FastAPI 和 ERP 增加服务鉴权。
- 钉钉 Webhook 和 Secret 使用密钥管理系统。
- 多实例部署时使用集中式数据库去重，避免 SQLite 单机限制。
- 对通知失败建立人工重发和死信队列。
- 财务数据查询必须叠加 ERP 侧的数据权限。
