# AP Deployment Scale — Data Dictionary

> 覆盖 `ap_deployment_scale/`：`scale_config.json` + `skills.py`
> 大规模采用统计建模，不实例化个体 Agent。

## scale_config.json

| 路径 | 说明 |
|------|------|
| `_description` / `version` / `target_scale` | 元信息，目标 `"1,000,000 agents"` |
| `agent_categories[10]` | 分类定义：`{category_id, name, identity, spawn_count{base,scale_factor}, model_backbone{enabled,llm_ratio}, primary_interaction_paradigm, skills[], persona_templates[{role,ratio,expertise/focus/...}], behavior_profile, topology_constraints}` |
| `agent_categories[].behavior_profile` | `{actions_per_10_rounds{skill:[min,max], idle:[min,max]}, traffic_mix{EW/NS/INT}, avg_payload_kb{EW/NS/INT}}` |
| `agent_categories[].topology_constraints` | `{max_peers_per_agent, preferred_connection_categories[], connection_affinity{cat_id:ratio, other:ratio}}` |
| `network_generation_rules[4]` | `{sub_id, topology_type, description, generation_rule, paradigm, edge_density, max_total_edges, channel_prefix}` — `STAR_HUB` 含 `hub_categories`/`spoke_categories`; `MESH` 含 `source_categories`/`target_categories` |
| `network_global_constraints` | `{max_total_edges:20M, max_edges_per_agent:250, bandwidth_limits_gbps{EW/NS/INT:{per_agent_avg_mbps, total_aggregate_gbps}}}` |
| `traffic_generation_rules` | `{EAST_WEST, NORTH_SOUTH, INTERNAL}` 各含 `{description, generated_by[], avg_requests_per_agent_per_round, size_distribution{min/p50/p95/max_kb}}` — NS 额外含 `rate_limit_per_round_global:100000` |
| `mapping_rules` | `{rules[{category_id, subnets[], roles[]}]}` — `roles`: `"hub"`/`"spoke"`/`"peer"`，与 subnets 按索引对齐 |
| `scaling_parameters` | `{total_agents_target:1M, llm_enabled_ratio:0.01, llm_estimate:10K, scale_factors{agent_count{min:100K/default:500K/max:5M}, edges_per_subnet{formula}, traffic_throughput{formula}}}` |

### 10 分类速查

| category_id | spawn | LLM | 技能 | NS |
|-------------|-------|-----|------|----|
| `ap_planner` | 50K | 2% | `call_ai_optimizer` `plan_deployment` | 25% |
| `rf_engineer` | 120K | 1% | `simulate_coverage` `analyze_interference` `generate_heatmap` | 20% |
| `cost_analyst` | 60K | 1% | `evaluate_cost` | 20% |
| `surveyor` | 80K | 0% | `check_feasibility` `report_obstacles` | 10% |
| `architect` | 40K | 1% | `validate_topology` | 10% |
| `ai_assistant` | 3K | **100%** | `optimize_ap_positions` `simulate_signal` `suggest_improvements` | **70%** |
| `verifier` | 50K | 1% | `verify_coverage` | 35% |
| `deployer` | 40K | 0% | `plan_deployment` `schedule_tasks` | 5% |
| `qa_engineer` | 30K | 1% | `final_inspection` `acceptance_test` | 15% |
| `documenter` | 25K | 0% | `record_decision` `archive_solution` | 5% |

### 4 子网速查

| sub_id | 拓扑 | Hub | Spokes | 最大边 | 范式 |
|--------|------|-----|--------|-------|------|
| `sub_planning_plane` | STAR | ap_planner | 其他 8 类 | 10M | COLLABORATION |
| `sub_ai_gateway` | STAR | ai_assistant | ap_planner/rf_engineer/verifier | 3M | NEGOTIATION |
| `sub_tech_collab` | MESH | — | rf/cost/surveyor/architect/verifier | 5M | COLLABORATION |
| `sub_deploy_flow` | MESH | — | deployer/qa/documenter | 2M | COLLABORATION |

### 三类流量参数

| 类型 | 每 agent 每轮请求 | p50 | p95 | 全局限流 |
|------|------------------|-----|-----|---------|
| EAST_WEST | 0.25 | 16 KB | 64 KB | — |
| NORTH_SOUTH | 0.10 | 128 KB | 512 KB | 100K/轮 |
| INTERNAL | 0.12 | 64 KB | 512 KB | — |

---

## skills.py

### 与小规模差异

| 维度 | ap_deployment | ap_deployment_scale |
|------|-------------|-------------------|
| Agent | 10 实例 | 统计分类，无个体 |
| 部署 | `plan_next_ap` 逐点 | `call_ai_optimizer` 批量 |
| 阵营博弈 | 3 阵营 14 技能 | 无 |
| AP 状态 | 5 个变量(含 proposed/relocating) | 仅 `ap_placements` |
| 技能数 | 38 (get_panel_state 未注册) | 17 (含 get_panel_state) |

### 常量 (同小规模)

| 变量 | 值 | 说明 |
|------|-----|------|
| `CAMPUS_W/H` | 1000/400 | 园区 (m) |
| `BUDGET` / `AP_UNIT_COST` | 50000 / 3500 | 预算 / AP 单价 |
| `AP_COVERAGE_RADIUS` / `TARGET_COVERAGE` | 60 / 95 | 覆盖半径 (m) / 目标 (%) |
| `INTERFERENCE[]` | 5 个 | `{id, x, y, radius, desc}` |

### 运行时状态

| 变量 | 元素结构 |
|------|----------|
| `ap_placements[]` | `{id, x, y, radius, cost, status}` |
| `coverage_reports[]` | `{round, coverage_pct, blind_spots, ap_count, total_cost}` |
| `cost_estimates[]` | `{round, ap_count, unit_cost, total_cost, budget_remaining}` |
| `ai_call_log[]` | `{round, caller, request_type, latency_ms, tokens}` |
| `feasibility_checks[]` | `{round, ap_id, feasible, issue}` |
| `event_log[]` | `{event_type, round, source, target, action, detail}` |
| `traffic_log[]` | `{round, type, source, target, action, bytes}` |

> 无 `proposed_aps`/`relocating_aps`/`pending_action`/`decision_log` 及阵营博弈状态。

### 技能签名 (17 个)

| 技能 | 分类 | 入参 | → data |
|------|------|------|--------|
| `call_ai_optimizer` | ap_planner | `round, num_aps` | `{positions[{x,y,safe_dist}], num_aps, latency_ms, tokens}` |
| `optimize_ap_positions` | ai_assistant | `round, num_aps` | `{positions[{x,y,score}], latency_ms, tokens}` |
| `simulate_signal` | ai_assistant | `round, ap_placements?` | `{coverage_pct, heatmap_sample[{x,y,signal_dbm}]}` |
| `suggest_improvements` | ai_assistant | `round, current_coverage` | `{suggestions[{type, desc}]}` |
| `simulate_coverage` | rf_engineer | `round, ap_placements?` | `{coverage_pct, blind_spot_count, blind_spots_sample}` |
| `analyze_interference` | rf_engineer | `round` | `{sources[{source_id, affected_ap_count, affected_aps[]}]}` |
| `generate_heatmap` | rf_engineer | `round, ap_placements?` | `{grid[{x, y, signal_dbm}]}` |
| `evaluate_cost` | cost_analyst | `round, ap_count?, unit_cost?` | `{ap_count, total_cost, budget_remaining, within_budget}` |
| `check_feasibility` | surveyor | `round, ap_placements?` | `{checks[{ap_id, feasible, issue}], feasible_count}` |
| `report_obstacles` | surveyor | `round` | `{obstacles[{ap_id, issue, x, y}]}` |
| `validate_topology` | architect | `round, ap_placements?` | `{valid, issues[]}` |
| `verify_coverage` | verifier | `round, ap_placements?` | `{coverage_pct, target, passed}` |
| `plan_deployment` | deployer | `round, ap_placements?` | `{phases[{phase, ap_ids[], duration_h}]}` |
| `schedule_tasks` | deployer | `round, ap_placements?` | `{schedule[{ap_id, start_h, duration_h, crew}]}` |
| `final_inspection` | qa_engineer | `round` | `{checks{cov,cost,interference,feasibility}, all_pass}` |
| `acceptance_test` | qa_engineer | `round` | `{tests{signal,coverage,interference,throughput}, all_pass}` |
| `record_decision` | documenter | `round, detail` | `{detail}` |
| `archive_solution` | documenter | `round` | `{archive{ap_count,total_cost,coverage_pct,rounds_taken}}` |

### get_panel_state() → /api/scenes/state.custom

```typescript
{
  campus, interference, budget,                                    // 常量
  ap_placements, coverage_reports, cost_estimates,                 // 全量
  ai_call_log, feasibility_checks,                                 // 全量
  latest_coverage: object|null, latest_cost: object|null,          // 最新一条
  event_log, traffic_log,                                          // 最近 20 条
}
```

### event_log 类型 (18 种)

| event_type | 技能 | source → target |
|-----------|------|-----------------|
| `AI_CALL` / `AI_OPTIMIZE` / `AI_SIGNAL_SIM` / `AI_SUGGEST` | 对应 ai 技能 | PLANNER/AI_ASSISTANT/VERIFIER/EXTERNAL:LLM |
| `COVERAGE_SIM` / `INTERFERENCE_ANALYSIS` / `HEATMAP` | rf_engineer 技能 | RF_ENGINEER → PLANNER |
| `COST_EVAL` | evaluate_cost | COST_ANALYST → PLANNER |
| `FEASIBILITY_CHECK` / `OBSTACLE_REPORT` | surveyor 技能 | SURVEYOR → PLANNER |
| `TOPOLOGY_CHECK` | validate_topology | ARCHITECT → PLANNER |
| `VERIFY_COVERAGE` | verify_coverage | VERIFIER → PLANNER |
| `FINAL_INSPECTION` / `ACCEPTANCE` | qa 技能 | QA_ENGINEER → PLANNER |
| `DEPLOY_PLAN` / `SCHEDULE` | deployer 技能 | DEPLOYER → PLANNER |
| `DECISION_RECORDED` / `ARCHIVE` | documenter 技能 | DOCUMENTER → PLANNER |

---

## 字段对照: 小规模 → 大规模

| 小规模 | 大规模 | 差异 |
|--------|--------|------|
| `meta_and_roles.roles.{id}` | `agent_categories[]` | 角色实例 → 分类统计 |
| `roles.{id}.faction_id` | (无) | 无阵营博弈 |
| `instances_and_skills.container_instances` | `agent_categories[].skills[]` | 同源 |
| `network_topology.sub_networks[].edges[]` | (动态生成) | 静态边 → 密度公式 |
| `business_topology` | (无) | 无业务合约层 |
| `ap_placements + proposed + relocating` | `ap_placements` | 状态追踪简化为单数组 |
| `decision_log` / `pending_action` | (无) | 无单点决策追踪 |

## 文件引用链

```
scale_config.agent_categories[].skills[] → skills.py SkillRegistry
scale_config.mapping_rules → network_generation_rules[].sub_id
skills.py get_panel_state() → /api/scenes/state.custom
```
