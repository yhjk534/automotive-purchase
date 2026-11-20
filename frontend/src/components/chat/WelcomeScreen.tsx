"use client";

import { CapabilityCard } from "@/lib/types";
import CapabilityCardComponent from "@/components/common/CapabilityCard";

const CARDS: CapabilityCard[] = [
  {
    icon: "🚘",
    title: "车型适配查询",
    description: "按品牌、车系、年款、发动机或 OE 号查找适配汽车零部件",
    prompt: "查询2021款丰田凯美瑞2.0L适用的前制动片，并列出OE号和供应商报价",
  },
  {
    icon: "📊",
    title: "供应商比价",
    description: "比较含税价、MOQ、交货周期、准时交付率和质量 PPM",
    prompt: "对比前制动片的不同供应商报价，并综合交期和质量给出采购建议",
  },
  {
    icon: "📦",
    title: "库存预警",
    description: "监控多仓库存、预留库存和车型专用件安全库存",
    prompt: "查看当前汽车零部件库存预警，并按缺货严重程度排序",
  },
  {
    icon: "🛒",
    title: "采购下单",
    description: "创建汽车零部件采购订单，支持适配校验和人工审批",
    prompt: "为2021款丰田凯美瑞2.0L创建前制动片采购订单，数量20套",
  },
  {
    icon: "💰",
    title: "财务与报表",
    description: "统一查询采购金额、发票、应付、付款进度和预算使用率",
    prompt: "查询本月汽车零部件采购财务情况，并生成可下载的财务分析报表",
  },
  {
    icon: "🔔",
    title: "告警与通知",
    description: "低库存和审批超时分级告警，自动去重、失败重试并发布钉钉消息",
    prompt: "检查当前低库存和审批超时风险，并按严重级别汇总",
  },
];

interface Props {
  onPromptClick: (prompt: string) => void;
}

export default function WelcomeScreen({ onPromptClick }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-8">
      <div className="max-w-2xl w-full text-center">
        {/* 标题 */}
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          汽车零部件智能采购助手
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          车型适配 · OE 号检索 · 供应商比价 · 订单审批 · 多仓库存
        </p>

        {/* 功能卡片 2x2 */}
        <div className="grid grid-cols-2 gap-4">
          {CARDS.map((card) => (
            <CapabilityCardComponent
              key={card.title}
              card={card}
              onClick={onPromptClick}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
