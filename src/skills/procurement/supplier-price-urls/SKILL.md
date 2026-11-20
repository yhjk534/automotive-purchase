---
name: supplier-price-urls
description: 供应商报价URL映射 - 各供应商在线报价系统地址
scope: procurement
version: 1.0.0
---

# 供应商报价URL映射

## 概述
记录各主要供应商的在线报价系统URL，用于价格比对和市场竞争分析。

## URL映射表

| 供应商 | 报价系统URL | 备注 |
|--------|------------|------|
| 上海安驰 | https://example.com/anchi/quote | 制动系统 |
| 苏州恒擎 | https://example.com/hengqing/price | 动力、点火与传动 |
| 广州德驰 | https://example.com/dechi/catalog | 滤清与保养耗材 |
| 江苏联创 | https://example.com/lianchuang/quote | 底盘与悬挂 |
| 宁波启航 | https://example.com/qihang/price | 汽车电气与车身附件 |

## 使用场景
1. 当用户要求对比某零部件的市场价格时
2. 需要验证供应商报价是否合理时
3. 进行供应商竞争力分析时

## 使用方式
- 配合 `web_search` 工具搜索最新报价
- 配合 `web-scraper` 技能抓取报价页面
- 将抓取结果与 ERP 中的采购价进行对比

## 注意事项
- URL可能随时间变化，需定期验证
- 部分报价系统需要登录，仅抓取公开页面
- 价格数据仅供参考，实际以合同价为准
- 同一零件存在多个供应商报价时，应同时比较含税价、MOQ、交期、准时交付率和质量 PPM
