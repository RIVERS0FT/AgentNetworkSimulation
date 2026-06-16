# AP Deployment — 园区WiFi AP部署规划仿真

## 场景概述

1000m×400m 矩形园区，5个固定信号干扰源。10个Agent角色协作规划AP部署方案，目标：覆盖≥95%、成本≤预算¥50,000。

## 角色技能

| 角色 | 技能 | 职责 |
|------|------|------|
| PLANNER | `plan_next_ap`, `confirm_ap`, `reject_ap`, `relocate_ap`, `confirm_relocation`, `evaluate_cost`, `plan_deployment` | 逐点统筹AP规划 |
| RF_ENGINEER | `simulate_coverage`, `analyze_interference`, `generate_heatmap`, `evaluate_single_ap` | 信号覆盖仿真 |
| COST_ANALYST | `evaluate_cost` | 成本预算 |
| SURVEYOR | `check_feasibility`, `report_obstacles` | 物理可行性 |
| ARCHITECT | `validate_topology` | 拓扑验证 |
| AI_ASSISTANT | `optimize_ap_positions`, `simulate_signal`, `suggest_improvements` | AI优化(外部LLM) |
| VERIFIER | `verify_coverage` | 覆盖验证 |
| DEPLOYER | `plan_deployment`, `schedule_tasks` | 部署计划 |
| QA_ENGINEER | `final_inspection`, `acceptance_test` | 验收测试 |
| DOCUMENTER | `record_decision`, `archive_solution` | 文档归档 |

## 执行流程

```
Phase 1: 逐点部署循环 (每个AP重复)
  ┌──────────────────────────────────────────────────┐
  │ PLANNER ──plan_next_ap──→ AI_ASSISTANT           │ 南北向: AI调用
  │         ←── (x,y)候选 ──                          │ 前端: 虚线AP闪烁出现
  │                                                  │
  │ RF_ENGINEER ──evaluate_single_ap──→ 覆盖贡献%    │ 东西向: 评估报告
  │                                     前端: evaluating状态 │
  │                                                  │
  │ PLANNER ──confirm_ap──→ 虚线→实线 ✅             │
  │         ──reject_ap ──→ 虚线消失 ❌ → 重新plan    │
  └──────────────────────────────────────────────────┘

Phase 2-5: 全局评估 (每轮一次)
  RF_ENGINEER ──simulate_coverage──→ 全园区覆盖率
  RF_ENGINEER ──analyze_interference→ AP受干扰情况
  COST_ANALYST──evaluate_cost──────→ 总成本/预算
  SURVEYOR ────check_feasibility───→ 每个AP可行性
  ARCHITECT ───validate_topology───→ AP间距/干扰冲突

Phase 6-7: 迭代优化
  AI_ASSISTANT──suggest_improvements→ 改进建议
  PLANNER ─────relocate_ap ────────→ 旧位闪烁+新位虚线
  PLANNER ─────confirm_relocation──→ 新位虚线→实线
  VERIFIER ────verify_coverage ────→ 是否≥95%?

Phase 8-11: 收尾
  DEPLOYER ────plan_deployment ────→ 分批部署计划
  QA_ENGINEER──acceptance_test ────→ 验收
  DOCUMENTER ──archive_solution ────→ 归档
```

## 面板可视化

| 操作 | 视觉效果 |
|------|----------|
| `plan_next_ap` | 蓝色虚线圆出现 |
| `evaluate_single_ap` | 虚线流动动画 |
| `confirm_ap` | 虚线→实心蓝圆 |
| `reject_ap` | 虚线圆消失 |
| `relocate_ap` | 旧位红色闪烁 + 新位蓝色虚线 |
| `confirm_relocation` | 新位虚线→实线 |

## 通信拓扑

```
sub_core_team (STAR):  PLANNER ←→ 全员
sub_ai_network (MESH): AI_ASSISTANT ←→ PLANNER/RF_ENGINEER/VERIFIER
```

## 流量类型

| 流量 | 触发场景 |
|------|----------|
| 南北向 | PLANNER/AI调用外部LLM推理 |
| 东西向 | Agent间协作报告(覆盖/成本/可行性/拓扑) |
| 内部 | 部署计划/验收/归档 |
