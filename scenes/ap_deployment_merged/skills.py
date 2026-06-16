import math
import json
import hashlib

# ============================================================
# 园区地图 & 干扰源（固定物理环境）
# ============================================================
CAMPUS_W = 1000
CAMPUS_H = 400

INTERFERENCE = [
    {"id": "INT_01", "x": 150, "y": 80,  "radius": 80,  "desc": "变电站电磁干扰"},
    {"id": "INT_02", "x": 420, "y": 280, "radius": 120, "desc": "大型电机设备"},
    {"id": "INT_03", "x": 680, "y": 120, "radius": 60,  "desc": "微波通信塔"},
    {"id": "INT_04", "x": 850, "y": 320, "radius": 100, "desc": "高压输电线"},
    {"id": "INT_05", "x": 300, "y": 350, "radius": 150, "desc": "工业焊接车间"},
]

# ============================================================
# 物理参数
# ============================================================
BUDGET = 50000
AP_UNIT_COST = 3500
AP_INSTALL_COST = 800       # 单AP安装固定成本（支架/电源/线缆基础）
AP_CABLE_COST_PER_M = 5     # 线缆成本/米（长距离布线）
AP_COVERAGE_RADIUS = 60     # AP覆盖半径 (m)
TARGET_COVERAGE = 95        # 目标覆盖率(%)
MIN_AP_SPACING = 25         # AP最小间距 (m)
PATH_LOSS_EXPONENT = 2.5    # 信号衰减指数

# ============================================================
# 模块级状态
# ============================================================
ap_placements = []
coverage_reports = []
cost_estimates = []
ai_call_log = []
feasibility_checks = []
event_log = []
traffic_log = []


def _emit_event(etype, round_num, source, target, action, detail=""):
    event_log.append({"event_type": etype, "round": round_num, "source": source, "target": target, "action": action, "detail": detail})

def _emit_traffic(round_num, ttype, source, target, action, kbytes):
    traffic_log.append({"round": round_num, "type": ttype, "source": source, "target": target, "action": action, "bytes": kbytes * 1024})

def _pseudo_random(seed_str, low, high):
    """确定性伪随机：对相同输入始终返回相同值，使仿真可复现"""
    h = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    return low + (h % 10000) / 10000.0 * (high - low)


# ============================================================
# SkillRegistry
# ============================================================
class SkillRegistry:
    _skills = {}
    @classmethod
    def register(cls, name, fn): cls._skills[name] = fn
    @classmethod
    def execute(cls, name, **kwargs):
        if name not in cls._skills: return {"status": "error", "result": None, "data": {"error": f"Skill '{name}' not found"}}
        return cls._skills[name](**kwargs)
    @classmethod
    def list_skills(cls): return list(cls._skills.keys())


# ============================================================
# 物理计算工具函数
# ============================================================
def _signal_strength_dbm(dist_m):
    """自由空间路径损耗模型：距离→信号强度(dBm)"""
    if dist_m <= 0: return -20
    if dist_m > AP_COVERAGE_RADIUS: return -90
    loss = 20 + PATH_LOSS_EXPONENT * 10 * math.log10(max(1, dist_m))
    return round(-20 - loss)

def _is_in_interference(px, py):
    """检查点是否在任何干扰源的干扰半径内"""
    for src in INTERFERENCE:
        if math.sqrt((px - src["x"])**2 + (py - src["y"])**2) < src["radius"]:
            return True, src
    return False, None

def _min_interference_dist(px, py):
    """返回到最近干扰源边缘的距离（正=安全，负=在干扰内）"""
    min_d = 9999
    for src in INTERFERENCE:
        d = math.sqrt((px - src["x"])**2 + (py - src["y"])**2) - src["radius"]
        if d < min_d: min_d = d
    return min_d

def _ap_pair_dist(ap1, ap2):
    return math.sqrt((ap1["x"] - ap2["x"])**2 + (ap1["y"] - ap2["y"])**2)


# ============================================================
# PLANNER: call_ai_optimizer — 确定性优化算法
# ============================================================
def call_ai_optimizer(**kwargs):
    """
    AP规划师调用AI获取最优位置。使用确定性优化算法（网格+干扰规避），
    相同输入产生相同输出，仅latency/tokens为仿真参数。
    """
    round_num = kwargs.get("round", 0)
    num_aps = kwargs.get("num_aps", 8)

    # 仿真参数：基于AP数量和园区面积
    latency = 200 + num_aps * 60       # 越多的AP，AI计算越久
    tokens = 500 + num_aps * 150

    # 确定性网格+干扰规避
    cols = max(2, int(math.sqrt(num_aps * CAMPUS_W / CAMPUS_H)))
    rows = max(2, int(math.ceil(num_aps / cols)))
    step_x = CAMPUS_W / (cols + 1)
    step_y = CAMPUS_H / (rows + 1)
    positions = []
    idx = 0
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            if idx >= num_aps: break
            bx, by = step_x * c, step_y * r

            # 确定性微调：在网格点周围找离干扰最远的位置
            best_x, best_y, best_dist = bx, by, _min_interference_dist(bx, by)
            # 在3×3网格中搜索最佳偏移
            for dx in [-step_x*0.2, 0, step_x*0.2]:
                for dy in [-step_y*0.2, 0, step_y*0.2]:
                    tx = max(10, min(CAMPUS_W-10, bx+dx))
                    ty = max(10, min(CAMPUS_H-10, by+dy))
                    d = _min_interference_dist(tx, ty)
                    if d > best_dist: best_x, best_y, best_dist = tx, ty, d
            positions.append({"x": round(best_x, 1), "y": round(best_y, 1), "safe_dist": round(best_dist, 1)})
            idx += 1

    ai_call_log.append({"round": round_num, "caller": "PLANNER", "request_type": "optimize_ap_positions", "latency_ms": latency, "tokens": tokens})
    _emit_traffic(round_num, "NORTH_SOUTH", "PLANNER", "AI_ASSISTANT", "optimize_ap", tokens * 4)
    _emit_event("AI_CALL", round_num, "PLANNER", "AI_ASSISTANT", "optimize_ap_positions",
                f"{num_aps} APs, {latency}ms, {tokens} tokens")

    return {"status": "success", "result": "ai_optimized",
            "data": {"positions": positions, "num_aps": num_aps, "latency_ms": latency, "tokens": tokens, "round": round_num}}
SkillRegistry.register("call_ai_optimizer", call_ai_optimizer)


# ============================================================
# RF_ENGINEER
# ============================================================
def simulate_coverage(**kwargs):
    """
    信号覆盖仿真。均匀网格采样，计算覆盖率。
    """
    round_num = kwargs.get("round", 0)
    aps = kwargs.get("ap_placements", ap_placements)
    if not aps: return {"status": "error", "result": "no_aps", "data": {"error": "无AP数据"}}

    # 均匀网格采样（确定性，不随机）
    grid_step = 10  # 每10m采样
    total, covered = 0, 0
    blind_spots = []
    gx = 0
    while gx <= CAMPUS_W:
        gy = 0
        while gy <= CAMPUS_H:
            total += 1
            in_ap = any(math.sqrt((gx-ap["x"])**2 + (gy-ap["y"])**2) < ap.get("radius", AP_COVERAGE_RADIUS) for ap in aps)
            in_int, _ = _is_in_interference(gx, gy)
            if in_ap and not in_int: covered += 1
            elif not in_ap: blind_spots.append({"x": round(gx,1), "y": round(gy,1)})
            gy += grid_step
        gx += grid_step

    coverage_pct = round(covered / total * 100, 1)
    report = {"round": round_num, "coverage_pct": coverage_pct, "blind_spot_count": len(blind_spots),
              "ap_count": len(aps), "total_samples": total, "blind_spots_sample": blind_spots[:20]}
    coverage_reports.append(report)
    _emit_traffic(round_num, "EAST_WEST", "RF_ENGINEER", "PLANNER", "coverage_report", 16)
    _emit_event("COVERAGE_SIM", round_num, "RF_ENGINEER", "PLANNER", "simulate_coverage",
                f"{coverage_pct}% ({covered}/{total}), {len(blind_spots)} blind spots")
    return {"status": "success", "result": "coverage_simulated", "data": report}
SkillRegistry.register("simulate_coverage", simulate_coverage)


def analyze_interference(**kwargs):
    """分析干扰源影响范围（确定性：检查每个AP与干扰源的距离）"""
    round_num = kwargs.get("round", 0)
    analysis = []
    for src in INTERFERENCE:
        affected = []
        for ap in ap_placements:
            if math.sqrt((ap["x"]-src["x"])**2 + (ap["y"]-src["y"])**2) < src["radius"]:
                affected.append({"ap_id": ap.get("id","?"),
                                 "distance": round(math.sqrt((ap["x"]-src["x"])**2+(ap["y"]-src["y"])**2),1)})
        analysis.append({"source_id": src["id"], "desc": src["desc"], "radius": src["radius"],
                         "affected_aps": affected, "affected_count": len(affected)})
    _emit_event("INTERFERENCE_ANALYSIS", round_num, "RF_ENGINEER", "PLANNER", "analyze_interference",
                f"{len(INTERFERENCE)} sources, {sum(a['affected_count'] for a in analysis)} APs affected")
    return {"status": "success", "result": "analysis_complete", "data": {"sources": analysis, "round": round_num}}
SkillRegistry.register("analyze_interference", analyze_interference)


def generate_heatmap(**kwargs):
    """生成覆盖热力图（确定性网格）"""
    round_num = kwargs.get("round", 0)
    grid = []
    for gx in range(0, CAMPUS_W+1, 25):
        for gy in range(0, CAMPUS_H+1, 25):
            best_sig = -90
            for ap in ap_placements:
                d = math.sqrt((gx-ap["x"])**2+(gy-ap["y"])**2)
                if d < ap.get("radius", AP_COVERAGE_RADIUS):
                    sig = _signal_strength_dbm(d)
                    if sig > best_sig: best_sig = sig
            in_int, _ = _is_in_interference(gx, gy)
            if in_int: best_sig = min(best_sig, -85)
            grid.append({"x": gx, "y": gy, "signal_dbm": best_sig})
    _emit_event("HEATMAP", round_num, "RF_ENGINEER", "PLANNER", "generate_heatmap", f"{len(grid)} points")
    return {"status": "success", "result": "heatmap_generated", "data": {"grid": grid, "round": round_num}}
SkillRegistry.register("generate_heatmap", generate_heatmap)


# ============================================================
# COST_ANALYST — 基于实际距离计算成本
# ============================================================
def evaluate_cost(**kwargs):
    """评估方案成本：AP硬件 + 安装 + 线缆（基于AP位置到园区边缘的距离估算）"""
    round_num = kwargs.get("round", 0)
    ap_count = kwargs.get("ap_count", len(ap_placements))
    aps = kwargs.get("ap_placements", ap_placements)
    unit_cost = kwargs.get("unit_cost", AP_UNIT_COST)

    # 计算实际安装成本
    hardware_cost = ap_count * unit_cost
    install_cost = ap_count * AP_INSTALL_COST
    # 线缆成本：每个AP到最近园区边缘的距离 × 线缆单价
    cable_cost = 0
    for ap in aps:
        nearest_edge = min(ap["y"], CAMPUS_H-ap["y"])  # 到上下边缘
        cable_cost += nearest_edge * AP_CABLE_COST_PER_M

    total = hardware_cost + install_cost + cable_cost
    remaining = BUDGET - total
    estimate = {"round": round_num, "ap_count": ap_count, "unit_cost": unit_cost,
                "hardware_cost": hardware_cost, "install_cost": install_cost, "cable_cost": cable_cost,
                "total_cost": total, "budget_remaining": remaining, "within_budget": remaining >= 0}
    cost_estimates.append(estimate)
    _emit_event("COST_EVAL", round_num, "COST_ANALYST", "PLANNER", "evaluate_cost",
                f"{ap_count} APs: HW{hardware_cost}+Install{install_cost}+Cable{cable_cost}={total} (budget:{BUDGET})")
    _emit_traffic(round_num, "EAST_WEST", "COST_ANALYST", "PLANNER", "cost_report", 8)
    return {"status": "success", "result": "cost_evaluated", "data": estimate}
SkillRegistry.register("evaluate_cost", evaluate_cost)


# ============================================================
# SURVEYOR — 基于位置判断可行性
# ============================================================
def _check_ap_feasibility(ap):
    """基于AP位置判断物理可行性，非随机"""
    issues = []
    x, y = ap["x"], ap["y"]
    # 靠近干扰源中心 → 安装困难
    for src in INTERFERENCE:
        dist = math.sqrt((x-src["x"])**2+(y-src["y"])**2)
        if dist < src["radius"] * 0.5: issues.append(f"过于靠近{src['id']}")
        elif dist < src["radius"]: issues.append("信号遮挡")
    # 靠近园区边缘 → 电源问题
    if y < 20 or y > CAMPUS_H-20: issues.append("承重不足(靠近园区边界)")
    if x < 15 or x > CAMPUS_W-15: issues.append("无安装支架(靠近园区边界)")
    # AP间距过近
    for other in ap_placements:
        if other is ap: continue
        if _ap_pair_dist(ap, other) < MIN_AP_SPACING:
            issues.append(f"与{other.get('id','?')}间距过近")
            break
    return len(issues) == 0, issues[0] if issues else None


def check_feasibility(**kwargs):
    """现场勘测：基于物理位置判断可行性"""
    round_num = kwargs.get("round", 0)
    aps = kwargs.get("ap_placements", ap_placements)
    checks = []
    for ap in aps:
        feasible, issue = _check_ap_feasibility(ap)
        checks.append({"ap_id": ap.get("id","?"), "feasible": feasible, "issue": issue,
                       "x": ap["x"], "y": ap["y"]})
        feasibility_checks.append({"round": round_num, "ap_id": ap.get("id","?"), "feasible": feasible, "issue": issue})
    feasible_count = sum(1 for c in checks if c["feasible"])
    _emit_event("FEASIBILITY_CHECK", round_num, "SURVEYOR", "PLANNER", "check_feasibility",
                f"{feasible_count}/{len(checks)} feasible")
    return {"status": "success", "result": "feasibility_checked",
            "data": {"checks": checks, "feasible_count": feasible_count, "total": len(checks), "round": round_num}}
SkillRegistry.register("check_feasibility", check_feasibility)


def report_obstacles(**kwargs):
    """报告所有物理障碍（来自可行性检查的结果）"""
    round_num = kwargs.get("round", 0)
    obstacles = []
    for ap in ap_placements:
        feasible, issue = _check_ap_feasibility(ap)
        if not feasible:
            obstacles.append({"ap_id": ap.get("id","?"), "issue": issue, "x": ap["x"], "y": ap["y"]})
    _emit_event("OBSTACLE_REPORT", round_num, "SURVEYOR", "PLANNER", "report_obstacles", f"{len(obstacles)} obstacles")
    return {"status": "success", "result": "obstacles_reported", "data": {"obstacles": obstacles, "round": round_num}}
SkillRegistry.register("report_obstacles", report_obstacles)


# ============================================================
# ARCHITECT
# ============================================================
def validate_topology(**kwargs):
    """验证AP网络拓扑：检测间距冲突和干扰区内的AP"""
    round_num = kwargs.get("round", 0)
    aps = kwargs.get("ap_placements", ap_placements)
    issues = []
    for i, ap1 in enumerate(aps):
        for ap2 in aps[i+1:]:
            dist = _ap_pair_dist(ap1, ap2)
            if dist < MIN_AP_SPACING: issues.append(f"{ap1.get('id','?')}与{ap2.get('id','?')}间距{dist:.0f}m<{MIN_AP_SPACING}m")
        in_int, src = _is_in_interference(ap1["x"], ap1["y"])
        if in_int: issues.append(f"{ap1.get('id','?')}位于{src['id']}干扰区内")
    valid = len(issues) == 0
    _emit_event("TOPOLOGY_CHECK", round_num, "ARCHITECT", "PLANNER", "validate_topology",
                "PASS" if valid else f"{len(issues)} issues")
    return {"status": "success", "result": "valid" if valid else "issues_found",
            "data": {"valid": valid, "issues": issues, "round": round_num}}
SkillRegistry.register("validate_topology", validate_topology)


# ============================================================
# AI_ASSISTANT
# ============================================================
def optimize_ap_positions(**kwargs):
    """AI优化AP位置（与call_ai_optimizer相同的确定性算法）"""
    return call_ai_optimizer(**kwargs)
SkillRegistry.register("optimize_ap_positions", optimize_ap_positions)


def simulate_signal(**kwargs):
    """AI仿真信号强度（使用路径损耗模型，确定性）"""
    round_num = kwargs.get("round", 0)
    aps = kwargs.get("ap_placements", ap_placements)
    if not aps: return {"status": "error", "result": "no_aps", "data": {}}
    latency = 100 + len(aps) * 50
    tokens = 300 + len(aps) * 100

    # 均匀网格采样
    total, covered = 0, 0
    heatmap = []
    for gx in range(0, CAMPUS_W+1, 20):
        for gy in range(0, CAMPUS_H+1, 20):
            total += 1
            best_sig = -90
            for ap in aps:
                d = math.sqrt((gx-ap["x"])**2+(gy-ap["y"])**2)
                if d < ap.get("radius", AP_COVERAGE_RADIUS):
                    sig = _signal_strength_dbm(d)
                    if sig > best_sig: best_sig = sig
            in_int, _ = _is_in_interference(gx, gy)
            if in_int: best_sig = min(best_sig, -85)
            if best_sig > -75 and not in_int: covered += 1
            if len(heatmap) < 80: heatmap.append({"x": gx, "y": gy, "signal_dbm": best_sig})
    coverage = round(covered / total * 100, 1)

    ai_call_log.append({"round": round_num, "caller": "AI_ASSISTANT", "request_type": "simulate_signal", "latency_ms": latency, "tokens": tokens})
    _emit_traffic(round_num, "NORTH_SOUTH", "AI_ASSISTANT", "EXTERNAL:LLM", "llm_inference", tokens * 4)
    _emit_event("AI_SIGNAL_SIM", round_num, "AI_ASSISTANT", "VERIFIER", "simulate_signal", f"coverage:{coverage}%")
    return {"status": "success", "result": "signal_simulated",
            "data": {"coverage_pct": coverage, "heatmap_sample": heatmap, "latency_ms": latency, "tokens": tokens, "round": round_num}}
SkillRegistry.register("simulate_signal", simulate_signal)


def suggest_improvements(**kwargs):
    """基于实际覆盖数据和干扰分析给出改进建议"""
    round_num = kwargs.get("round", 0)
    current_cov = kwargs.get("current_coverage", 0)
    suggestions = []
    if current_cov < TARGET_COVERAGE:
        gap = TARGET_COVERAGE - current_cov
        extra_aps = max(1, int(gap / 5))
        suggestions.append({"type": "add_ap", "desc": f"覆盖{current_cov}%距目标{TARGET_COVERAGE}%差{gap}%，建议增加{extra_aps}个AP"})
    for src in INTERFERENCE:
        affected = [ap for ap in ap_placements if math.sqrt((ap["x"]-src["x"])**2+(ap["y"]-src["y"])**2) < src["radius"]]
        if affected:
            suggestions.append({"type": "relocate", "desc": f"{src['desc']}干扰区内有{len(affected)}个AP，建议向外移动{src['radius']*0.3:.0f}m"})
    if not suggestions: suggestions.append({"type": "optimal", "desc": "当前方案已达最优"})
    _emit_event("AI_SUGGEST", round_num, "AI_ASSISTANT", "PLANNER", "suggest_improvements", f"{len(suggestions)} suggestions")
    return {"status": "success", "result": "suggestions_ready", "data": {"suggestions": suggestions, "round": round_num}}
SkillRegistry.register("suggest_improvements", suggest_improvements)


# ============================================================
# VERIFIER — 基于实际覆盖数据验证
# ============================================================
def verify_coverage(**kwargs):
    """验证覆盖是否达标（读取最新覆盖报告）"""
    round_num = kwargs.get("round", 0)
    if not coverage_reports: return {"status": "error", "result": "no_data", "data": {"error": "无覆盖报告"}}
    cov = coverage_reports[-1]["coverage_pct"]
    passed = cov >= TARGET_COVERAGE
    _emit_event("VERIFY_COVERAGE", round_num, "VERIFIER", "PLANNER", "verify_coverage",
                f"{cov}% {'PASS' if passed else 'FAIL'} (target:{TARGET_COVERAGE}%)")
    return {"status": "success", "result": "pass" if passed else "fail",
            "data": {"coverage_pct": cov, "target": TARGET_COVERAGE, "passed": passed, "round": round_num}}
SkillRegistry.register("verify_coverage", verify_coverage)


# ============================================================
# DEPLOYER — 基于AP数量生成部署计划
# ============================================================
def plan_deployment(**kwargs):
    """制定部署计划：按AP数量和位置分组"""
    round_num = kwargs.get("round", 0)
    aps = kwargs.get("ap_placements", ap_placements)
    phase_size = max(1, len(aps) // 3)
    phases = []
    for i in range(0, len(aps), phase_size):
        batch = aps[i:i+phase_size]
        avg_dist = sum(_min_interference_dist(ap["x"], ap["y"]) for ap in batch) / len(batch)
        duration = max(4, min(12, int(4 + len(batch) * 2 + (0 if avg_dist > 50 else 3))))
        phases.append({"phase": len(phases)+1, "ap_ids": [ap.get("id",f"AP_{j+1}") for j,ap in enumerate(batch)],
                        "duration_h": duration, "difficulty": "normal" if avg_dist > 50 else "complex"})
    _emit_event("DEPLOY_PLAN", round_num, "DEPLOYER", "PLANNER", "plan_deployment", f"{len(phases)} phases")
    return {"status": "success", "result": "plan_created", "data": {"phases": phases, "round": round_num}}
SkillRegistry.register("plan_deployment", plan_deployment)


def schedule_tasks(**kwargs):
    """制定部署时间表：基于部署计划中的phase信息"""
    round_num = kwargs.get("round", 0)
    plan_result = plan_deployment(round=round_num)
    phases = plan_result["data"]["phases"]
    crews = ["team_A", "team_B", "team_C"]
    schedule = []
    for ph in phases:
        schedule.append({"phase": ph["phase"], "ap_ids": ph["ap_ids"],
                         "start_h": sum(p["duration_h"] for p in phases[:ph["phase"]-1]),
                         "duration_h": ph["duration_h"],
                         "crew": crews[(ph["phase"]-1) % 3]})
    _emit_event("SCHEDULE", round_num, "DEPLOYER", "PLANNER", "schedule_tasks", f"{len(schedule)} tasks")
    return {"status": "success", "result": "schedule_created", "data": {"schedule": schedule, "round": round_num}}
SkillRegistry.register("schedule_tasks", schedule_tasks)


# ============================================================
# QA_ENGINEER — 基于累积状态做验收
# ============================================================
def final_inspection(**kwargs):
    """最终验收：基于实际的覆盖/成本/可行性状态综合判定"""
    round_num = kwargs.get("round", 0)
    cov_ok = coverage_reports[-1]["coverage_pct"] >= TARGET_COVERAGE if coverage_reports else False
    budget_ok = cost_estimates[-1]["within_budget"] if cost_estimates else False
    feas_checks = [f for f in feasibility_checks if f.get("round") == round_num] or feasibility_checks
    feas_count = sum(1 for f in feas_checks if f["feasible"])
    feas_ok = feas_count / max(len(feas_checks), 1) >= 0.80
    intf_ok = not any(
        math.sqrt((ap["x"]-src["x"])**2+(ap["y"]-src["y"])**2) < src["radius"]
        for ap in ap_placements for src in INTERFERENCE
    )

    checks = {"coverage": cov_ok, "cost_within_budget": budget_ok,
              "feasibility_ok": feas_ok, "interference_avoided": intf_ok}
    all_pass = all(checks.values())
    _emit_event("FINAL_INSPECTION", round_num, "QA_ENGINEER", "PLANNER", "final_inspection",
                "ALL PASS" if all_pass else f"FAIL: {[k for k,v in checks.items() if not v]}")
    return {"status": "success", "result": "pass" if all_pass else "fail",
            "data": {"checks": checks, "all_pass": all_pass, "round": round_num}}
SkillRegistry.register("final_inspection", final_inspection)


def acceptance_test(**kwargs):
    """验收测试：综合覆盖率、信号强度、成本和可行性"""
    return final_inspection(**kwargs)
SkillRegistry.register("acceptance_test", acceptance_test)


# ============================================================
# DOCUMENTER
# ============================================================
def record_decision(**kwargs):
    """记录决策"""
    round_num = kwargs.get("round", 0)
    detail = kwargs.get("detail", "decision recorded")
    _emit_event("DECISION_RECORDED", round_num, "DOCUMENTER", "PLANNER", "record", detail)
    return {"status": "success", "result": "recorded", "data": {"detail": detail, "round": round_num}}
SkillRegistry.register("record_decision", record_decision)


def archive_solution(**kwargs):
    """归档最终方案"""
    round_num = kwargs.get("round", 0)
    archive = {
        "ap_count": len(ap_placements),
        "total_cost": cost_estimates[-1]["total_cost"] if cost_estimates else 0,
        "coverage_pct": coverage_reports[-1]["coverage_pct"] if coverage_reports else 0,
        "interference_sources": len(INTERFERENCE),
        "feasibility_rate": round(sum(1 for f in feasibility_checks if f["feasible"])/max(len(feasibility_checks),1)*100,1),
        "rounds_taken": round_num,
    }
    _emit_event("ARCHIVE", round_num, "DOCUMENTER", "PLANNER", "archive_solution",
                f"{archive['ap_count']} APs, {archive['coverage_pct']}%, ¥{archive['total_cost']}")
    return {"status": "success", "result": "archived", "data": {"archive": archive, "round": round_num}}
SkillRegistry.register("archive_solution", archive_solution)


# ============================================================
# get_panel_state
# ============================================================
def get_panel_state(**kwargs):
    return {
        "campus": {"width": CAMPUS_W, "height": CAMPUS_H},
        "interference": INTERFERENCE,
        "ap_placements": ap_placements,
        "coverage_reports": coverage_reports,
        "cost_estimates": cost_estimates,
        "ai_call_log": ai_call_log,
        "feasibility_checks": feasibility_checks,
        "budget": {"total": BUDGET, "unit_ap_cost": AP_UNIT_COST, "target_coverage_pct": TARGET_COVERAGE},
        "latest_coverage": coverage_reports[-1] if coverage_reports else None,
        "latest_cost": cost_estimates[-1] if cost_estimates else None,
        "event_log": event_log[-20:],
        "traffic_log": traffic_log[-20:],
    }
SkillRegistry.register("get_panel_state", get_panel_state)
