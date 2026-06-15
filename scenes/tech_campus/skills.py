import random
import time

# ============================================================
# 模块级状态 — 三类流量追踪
# ============================================================
traffic_log = []       # 所有流量事件 [{round, type, source, target, action, bytes}]
event_log = []         # 业务事件 [{event_type, round, source, target, action, detail}]

# 技能执行状态
git_commits = []
model_submissions = []
design_submissions = []
documents = []
test_reports = []
copilot_requests = []
external_api_calls = []
ci_pipelines = []


def _emit_traffic(round_num, traffic_type, source, target, action, bytes_est=0):
    """记录流量事件。type: EAST_WEST | NORTH_SOUTH | INTERNAL"""
    event = {
        "round": round_num,
        "type": traffic_type,
        "source": source,
        "target": target,
        "action": action,
        "bytes": bytes_est,
    }
    traffic_log.append(event)
    return event


def _emit_event(event_type, round_num, source, target, action, detail=""):
    e = {"event_type": event_type, "round": round_num, "source": source, "target": target, "action": action, "detail": detail}
    event_log.append(e)
    return e


# ============================================================
# SkillRegistry
# ============================================================
class SkillRegistry:
    _skills = {}

    @classmethod
    def register(cls, name, fn):
        cls._skills[name] = fn

    @classmethod
    def execute(cls, name, **kwargs):
        if name not in cls._skills:
            return {"status": "error", "result": None, "data": {"error": f"Skill '{name}' not found"}}
        return cls._skills[name](**kwargs)

    @classmethod
    def list_skills(cls):
        return list(cls._skills.keys())


# ============================================================
# 开发侧技能
# ============================================================

def submit_code(**kwargs):
    """
    提交代码到Git仓库，触发CI/CD。
    参数: developer(str), repo(str), files_changed(int), round(int)
    流量: developer→REPO_ADMIN (东西向, ~files_changed*2KB)
    """
    developer = kwargs.get("developer", "unknown")
    repo = kwargs.get("repo", "main")
    files = kwargs.get("files_changed", random.randint(1, 5))
    current_round = kwargs.get("round", 0)

    commit_id = f"commit_{len(git_commits)+1}_{int(time.time()%100000)}"
    git_commits.append({"developer": developer, "repo": repo, "commit_id": commit_id, "files": files, "round": current_round})

    # 东西向流量：dev→repo
    _emit_traffic(current_round, "EAST_WEST", developer, "REPO_ADMIN", "git_push", files * 2048)

    # 触发CI/CD
    pipeline_id = f"ci_{len(ci_pipelines)+1}"
    ci_pipelines.append({"pipeline_id": pipeline_id, "triggered_by": commit_id, "status": "running", "round": current_round})
    # 内部流量：REPO_ADMIN→CI runner
    _emit_traffic(current_round, "INTERNAL", "REPO_ADMIN", "CI_RUNNER", "trigger_pipeline", 512)

    _emit_event("CODE_SUBMITTED", current_round, developer, "REPO_ADMIN", "push", f"{commit_id} ({files} files)")

    return {
        "status": "success", "result": "code_submitted",
        "data": {"commit_id": commit_id, "files": files, "pipeline_id": pipeline_id, "round": current_round}
    }
SkillRegistry.register("submit_code", submit_code)


def request_copilot_assist(**kwargs):
    """
    请求Copilot辅助编码/文档。
    参数: requester(str), request_type(str: code|document), prompt(str), round(int)
    流量: requester→COPILOT (东西向 ~1KB)
    Copilot 内部调用 LLM API 时触发南北向流量
    """
    requester = kwargs.get("requester", "unknown")
    request_type = kwargs.get("request_type", "code")
    prompt = kwargs.get("prompt", "")
    current_round = kwargs.get("round", 0)

    req_id = f"copilot_{len(copilot_requests)+1}_{int(time.time()%100000)}"
    copilot_requests.append({"requester": requester, "type": request_type, "req_id": req_id, "round": current_round})

    # 东西向：requester→Copilot
    _emit_traffic(current_round, "EAST_WEST", requester, "COPILOT", "assist_request", 1024)

    # Copilot 内部自动调用 LLM API（南北向）
    api_call_id = SkillRegistry.execute("request_external_api",
                                         requester="COPILOT", api_name="LLM_INFERENCE",
                                         payload_size=len(prompt)*4 if prompt else 2048, round=current_round)

    # Copilot 返回结果（东西向）
    _emit_traffic(current_round, "EAST_WEST", "COPILOT", requester, "assist_response", 2048)

    _emit_event("COPILOT_ASSIST", current_round, requester, "COPILOT", request_type, f"{req_id}")

    return {
        "status": "success", "result": "assist_completed",
        "data": {"req_id": req_id, "type": request_type, "api_call": api_call_id.get("data", {}).get("call_id"), "round": current_round}
    }
SkillRegistry.register("request_copilot_assist", request_copilot_assist)


# ============================================================
# AI/IC 侧技能
# ============================================================

def submit_model(**kwargs):
    """
    提交训练好的模型文件。
    参数: developer(str), model_name(str), size_mb(float), round(int)
    流量: developer→REPO_ADMIN (内部流量, ~size*1MB)
    """
    developer = kwargs.get("developer", "unknown")
    model_name = kwargs.get("model_name", "model_v1")
    size_mb = kwargs.get("size_mb", random.randint(50, 500))
    current_round = kwargs.get("round", 0)

    model_id = f"model_{len(model_submissions)+1}_{int(time.time()%100000)}"
    model_submissions.append({"developer": developer, "model_name": model_name, "model_id": model_id, "size_mb": size_mb, "round": current_round})

    _emit_traffic(current_round, "INTERNAL", developer, "REPO_ADMIN", "model_push", int(size_mb * 1_048_576))
    _emit_event("MODEL_SUBMITTED", current_round, developer, "REPO_ADMIN", "push", f"{model_id} ({size_mb}MB)")

    return {"status": "success", "result": "model_submitted", "data": {"model_id": model_id, "size_mb": size_mb, "round": current_round}}
SkillRegistry.register("submit_model", submit_model)


def submit_design(**kwargs):
    """
    提交芯片设计文件。
    参数: developer(str), design_name(str), size_mb(float), round(int)
    流量: developer→REPO_ADMIN (内部流量)
    """
    developer = kwargs.get("developer", "unknown")
    design_name = kwargs.get("design_name", "design_v1")
    size_mb = kwargs.get("size_mb", random.randint(100, 2000))
    current_round = kwargs.get("round", 0)

    design_id = f"design_{len(design_submissions)+1}_{int(time.time()%100000)}"
    design_submissions.append({"developer": developer, "design_name": design_name, "design_id": design_id, "size_mb": size_mb, "round": current_round})

    _emit_traffic(current_round, "INTERNAL", developer, "REPO_ADMIN", "design_push", int(size_mb * 1_048_576))
    _emit_event("DESIGN_SUBMITTED", current_round, developer, "REPO_ADMIN", "push", f"{design_id} ({size_mb}MB)")

    return {"status": "success", "result": "design_submitted", "data": {"design_id": design_id, "size_mb": size_mb, "round": current_round}}
SkillRegistry.register("submit_design", submit_design)


def request_external_api(**kwargs):
    """
    通过 API_GW 请求外部资源（南北向流量）。
    参数: requester(str), api_name(str: LLM_INFERENCE|EDA_CLOUD|CLOUD_BUILD), payload_size(float,KB), round(int)
    内部调用 API_GW.rate_limit → API_GW.forward_request
    """
    requester = kwargs.get("requester", "unknown")
    api_name = kwargs.get("api_name", "external_service")
    payload_size = kwargs.get("payload_size", random.randint(1, 100))
    current_round = kwargs.get("round", 0)

    # 先经过限流检查
    limit_check = SkillRegistry.execute("rate_limit", caller=requester, payload_size=payload_size, round=current_round)
    if not limit_check["data"]["allowed"]:
        _emit_event("API_BLOCKED", current_round, requester, "API_GW", "rate_limited", f"{api_name} blocked")
        return {"status": "error", "result": "rate_limited", "data": {"api_name": api_name, "reason": "超过限流阈值"}}

    # 南北向：requester→API_GW→external
    call_id = f"api_{len(external_api_calls)+1}_{int(time.time()%100000)}"
    _emit_traffic(current_round, "NORTH_SOUTH", requester, "API_GW", f"request:{api_name}", int(payload_size * 1024))

    # 网关转发到外部（南北向出站）
    forward_result = SkillRegistry.execute("forward_request", call_id=call_id, api_name=api_name, round=current_round)

    # 外部响应回程流量
    resp_size = payload_size * random.uniform(0.5, 2.0)
    _emit_traffic(current_round, "NORTH_SOUTH", "API_GW", requester, f"response:{api_name}", int(resp_size * 1024))

    external_api_calls.append({"requester": requester, "api_name": api_name, "call_id": call_id, "payload_kb": payload_size, "round": current_round})
    _emit_event("EXTERNAL_API_CALL", current_round, requester, "API_GW", api_name, f"{call_id} ({payload_size}KB)")

    return {
        "status": "success", "result": "api_call_completed",
        "data": {"call_id": call_id, "api_name": api_name, "payload_kb": payload_size, "response_kb": round(resp_size, 1), "round": current_round}
    }
SkillRegistry.register("request_external_api", request_external_api)


# ============================================================
# 架构师/PM/文档侧技能
# ============================================================

def review_document(**kwargs):
    """
    审查设计文档并通知相关方。
    参数: reviewer(str), doc_id(str), target_dev(str), round(int)
    流量: reviewer→target_dev (东西向通知)
    """
    reviewer = kwargs.get("reviewer", "ARCHITECT")
    doc_id = kwargs.get("doc_id", f"doc_{len(documents)+1}")
    target_dev = kwargs.get("target_dev", "")
    current_round = kwargs.get("round", 0)

    decision = random.choice(["approved", "revision_required"])
    _emit_traffic(current_round, "EAST_WEST", reviewer, target_dev or "DEV_TEAM", "review_feedback", 4096)

    if decision == "revision_required" and target_dev:
        SkillRegistry.execute("notify_team", sender=reviewer, target=target_dev,
                              message=f"文档 {doc_id} 需修改", round=current_round)

    _emit_event("DOC_REVIEWED", current_round, reviewer, target_dev or "DEV_TEAM", decision, doc_id)

    return {"status": "success", "result": decision, "data": {"doc_id": doc_id, "decision": decision, "target_dev": target_dev, "round": current_round}}
SkillRegistry.register("review_document", review_document)


def write_document(**kwargs):
    """
    编写/协作编辑文档。
    参数: author(str), doc_type(str: requirement|design|api|test_plan), title(str), round(int)
    流量: author→REPO_ADMIN (内部推送)
    """
    author = kwargs.get("author", "unknown")
    doc_type = kwargs.get("doc_type", "requirement")
    title = kwargs.get("title", "untitled")
    current_round = kwargs.get("round", 0)

    doc_id = f"doc_{len(documents)+1}_{int(time.time()%100000)}"
    size_kb = random.randint(10, 200)
    documents.append({"author": author, "type": doc_type, "doc_id": doc_id, "title": title, "size_kb": size_kb, "status": "draft", "round": current_round})

    _emit_traffic(current_round, "INTERNAL", author, "REPO_ADMIN", "doc_push", size_kb * 1024)
    _emit_event("DOC_CREATED", current_round, author, "REPO_ADMIN", doc_type, f"{doc_id}: {title}")

    return {"status": "success", "result": "document_created", "data": {"doc_id": doc_id, "title": title, "size_kb": size_kb, "round": current_round}}
SkillRegistry.register("write_document", write_document)


# ============================================================
# 通知/CI/测试侧技能
# ============================================================

def notify_team(**kwargs):
    """
    发送通知。
    参数: sender(str), target(str), message(str), round(int)
    流量: sender→target (东西向)
    """
    sender = kwargs.get("sender", "unknown")
    target = kwargs.get("target", "unknown")
    message = kwargs.get("message", "")
    current_round = kwargs.get("round", 0)

    _emit_traffic(current_round, "EAST_WEST", sender, target, "notify", len(message.encode()) if message else 256)
    _emit_event("NOTIFY", current_round, sender, target, "notify", message[:80])

    return {"status": "success", "result": "notified", "data": {"sender": sender, "target": target, "round": current_round}}
SkillRegistry.register("notify_team", notify_team)


def run_test(**kwargs):
    """
    执行自动化测试。
    参数: tester(str), target(str), test_suite(str), round(int)
    流量: QA→target (东西向通知结果)
    """
    tester = kwargs.get("tester", "QA")
    target = kwargs.get("target", "DEV_FE")
    test_suite = kwargs.get("test_suite", "regression")
    current_round = kwargs.get("round", 0)

    test_id = f"test_{len(test_reports)+1}_{int(time.time()%100000)}"
    passed = random.random() > 0.3
    test_reports.append({"tester": tester, "target": target, "test_id": test_id, "passed": passed, "round": current_round})

    _emit_traffic(current_round, "EAST_WEST", tester, target, "test_report", 2048)
    _emit_event("TEST_COMPLETED", current_round, tester, target, "passed" if passed else "failed", test_id)

    if not passed:
        SkillRegistry.execute("notify_team", sender=tester, target=target, message=f"测试失败: {test_suite}", round=current_round)

    return {"status": "success", "result": "passed" if passed else "failed", "data": {"test_id": test_id, "passed": passed, "target": target, "round": current_round}}
SkillRegistry.register("run_test", run_test)


# ============================================================
# Copilot 侧技能
# ============================================================

def assist_code(**kwargs):
    """
    Copilot生成代码（内部调用LLM API）。
    参数: requester(str), language(str), context(str), round(int)
    """
    requester = kwargs.get("requester", "unknown")
    language = kwargs.get("language", "python")
    context = kwargs.get("context", "")
    current_round = kwargs.get("round", 0)

    # 内部南北向：调用LLM推理API
    tokens = random.randint(50, 500)
    SkillRegistry.execute("request_external_api", requester="COPILOT", api_name="LLM_INFERENCE",
                           payload_size=tokens * 4 / 1024, round=current_round)

    snippet = f"# {language} code for {requester}\ndef generated_func():\n    # {tokens} tokens generated\n    pass"

    return {"status": "success", "result": "code_generated", "data": {"language": language, "tokens": tokens, "round": current_round}}
SkillRegistry.register("assist_code", assist_code)


def assist_document(**kwargs):
    """
    Copilot辅助生成文档（内部调用LLM API）。
    参数: requester(str), doc_type(str), topic(str), round(int)
    """
    requester = kwargs.get("requester", "unknown")
    doc_type = kwargs.get("doc_type", "api_doc")
    current_round = kwargs.get("round", 0)

    SkillRegistry.execute("request_external_api", requester="COPILOT", api_name="LLM_INFERENCE",
                           payload_size=random.randint(2, 10), round=current_round)

    return {"status": "success", "result": "document_draft_generated", "data": {"doc_type": doc_type, "round": current_round}}
SkillRegistry.register("assist_document", assist_document)


# ============================================================
# REPO_ADMIN 侧技能
# ============================================================

def handle_push(**kwargs):
    """
    处理代码/模型/设计推送，触发CI/CD。
    参数: pusher(str), push_type(str: code|model|design|doc), artifact_id(str), round(int)
    """
    pusher = kwargs.get("pusher", "unknown")
    push_type = kwargs.get("push_type", "code")
    artifact_id = kwargs.get("artifact_id", "unknown")
    current_round = kwargs.get("round", 0)

    # 触发CI/CD
    pipeline_id = f"ci_{len(ci_pipelines)+1}_{int(time.time()%100000)}"
    ci_pipelines.append({"pipeline_id": pipeline_id, "type": push_type, "triggered_by": pusher, "status": "running", "round": current_round})

    # 内部流量：触发构建
    _emit_traffic(current_round, "INTERNAL", "REPO_ADMIN", "CI_RUNNER", "trigger_build", 4096)
    _emit_event("PUSH_HANDLED", current_round, "REPO_ADMIN", pusher, push_type, f"{artifact_id}→{pipeline_id}")

    # 模拟构建完成
    build_result = random.choice(["success", "success", "success", "failed"])
    ci_pipelines[-1]["status"] = build_result
    _emit_traffic(current_round, "INTERNAL", "CI_RUNNER", "REPO_ADMIN", "build_result", 1024)

    if build_result == "success" and push_type in ("code", "model"):
        # 推送镜像到Registry（内部流量）
        img_size_mb = random.randint(50, 500)
        _emit_traffic(current_round, "INTERNAL", "REPO_ADMIN", "REGISTRY", "image_push", int(img_size_mb * 1_048_576))
        _emit_event("IMAGE_PUSHED", current_round, "REPO_ADMIN", "REGISTRY", "push", f"{pipeline_id} ({img_size_mb}MB)")

    return {
        "status": "success", "result": build_result,
        "data": {"pipeline_id": pipeline_id, "push_type": push_type, "build_result": build_result, "round": current_round}
    }
SkillRegistry.register("handle_push", handle_push)


def trigger_ci_cd(**kwargs):
    """
    手动触发CI/CD流水线。
    参数: trigger_by(str), target_artifact(str), round(int)
    """
    trigger_by = kwargs.get("trigger_by", "unknown")
    target_artifact = kwargs.get("target_artifact", "latest")
    current_round = kwargs.get("round", 0)

    pipeline_id = f"ci_{len(ci_pipelines)+1}_{int(time.time()%100000)}"
    ci_pipelines.append({"pipeline_id": pipeline_id, "type": "manual", "triggered_by": trigger_by, "status": "running", "round": current_round})

    _emit_traffic(current_round, "INTERNAL", trigger_by, "CI_RUNNER", "manual_trigger", 512)
    _emit_event("CI_TRIGGERED", current_round, trigger_by, "CI_RUNNER", "trigger", pipeline_id)

    return {"status": "success", "result": "ci_triggered", "data": {"pipeline_id": pipeline_id, "round": current_round}}
SkillRegistry.register("trigger_ci_cd", trigger_ci_cd)


# ============================================================
# API_GW 侧技能
# ============================================================

def rate_limit(**kwargs):
    """
    API网关限流检查。
    参数: caller(str), payload_size(float), round(int)
    """
    caller = kwargs.get("caller", "unknown")
    current_round = kwargs.get("round", 0)

    # 每轮限10次外部调用
    current = len([c for c in external_api_calls if c["round"] == current_round])
    limit = 10
    allowed = current < limit

    return {"status": "success", "result": "rate_limit_checked", "data": {"allowed": allowed, "current": current, "limit": limit, "round": current_round}}
SkillRegistry.register("rate_limit", rate_limit)


def forward_request(**kwargs):
    """
    转发请求到外部服务。模拟外部响应延迟。
    参数: call_id(str), api_name(str), round(int)
    """
    call_id = kwargs.get("call_id", "unknown")
    api_name = kwargs.get("api_name", "external")
    current_round = kwargs.get("round", 0)

    # 模拟延迟和响应大小
    latency_ms = random.randint(50, 500)
    response_status = random.choices([200, 200, 200, 200, 429, 500], weights=[7, 0, 0, 0, 2, 1])[0]

    _emit_event("API_FORWARDED", current_round, "API_GW", api_name,
                 f"{response_status}", f"{call_id} latency={latency_ms}ms")

    return {
        "status": "success",
        "result": "forwarded",
        "data": {"call_id": call_id, "api_name": api_name, "latency_ms": latency_ms, "response_status": response_status, "round": current_round}
    }
SkillRegistry.register("forward_request", forward_request)
