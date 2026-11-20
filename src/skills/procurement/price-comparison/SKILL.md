---
name: price-comparison
description: 价格对比 - 供应商报价比价分析
scope: procurement
version: 1.0.0
---

# 价格对比技能

## 概述
对比不同供应商对同一汽车零部件的报价，结合车型适配、零件来源和交付条件
分析价格差异原因，给出采购建议。

## 使用方式
1. 通过 vehicle_search 确认目标车型，或通过 OE 号定位零件
2. 调用 part_search / part_query 获取供应商报价与质量交付指标
3. 通过 web_fetch 获取供应商公开报价作为补充
4. 比较含税价、MOQ、交货周期、准时交付率和质量 PPM
5. 对比分析生成价格差异报告
6. 使用 generate_chart 生成对比图表

## 依赖
- web_fetch 工具
- generate_chart 工具
- part_search MCP 工具
