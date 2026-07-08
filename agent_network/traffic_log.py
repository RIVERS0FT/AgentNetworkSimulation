"""
Docker HTTP 流量监管：记录容器间 HTTP 流量并写入 network.jsonl。

不做 MITM 解密，外部 HTTPS 只记录元数据。
"""

import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SENSITIVE_KEYS = {
    "authorization", "x-api-key", "api-key", "api_key", "token",
    "password", "secret", "x-auth-token", "cookie",
    "set-cookie", "anthropic-api-key", "llm-api-key",
    "key",
}

EXCLUDED_PATHS = {
    "/api/logs/ingest",
    "/api/logs/agent",
    "/api/minesweeper",
    "/ws",
    "/static",
    "/health",
}

MAX_BODY_BYTES = 64 * 1024


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _sanitize_headers(headers: dict) -> dict:
    result = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_KEYS:
            result[key] = "***REDACTED***"
        else:
            result[key] = value
    return result


def _sanitize_body(obj: Any, depth: int = 0) -> Any:
    if depth > 10:
        return obj
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            lowered = key.lower()
            if lowered in SENSITIVE_KEYS or any(
                marker in lowered for marker in ("secret", "password", "token")
            ):
                result[key] = "***REDACTED***"
            elif isinstance(value, (dict, list)):
                result[key] = _sanitize_body(value, depth + 1)
            else:
                result[key] = value
        return result
    if isinstance(obj, list):
        return [_sanitize_body(item, depth + 1) for item in obj]
    return obj


def _should_skip(path: str) -> bool:
    return any(path.startswith(excluded) for excluded in EXCLUDED_PATHS)


def _parse_body(body: bytes, content_type: str) -> Any:
    if not body:
        return ""
    if len(body) > MAX_BODY_BYTES:
        body = body[:MAX_BODY_BYTES]
    if "application/json" in (content_type or "").lower():
        try:
            return json.loads(body.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    try:
        return body.decode("utf-8", errors="replace")[:MAX_BODY_BYTES]
    except Exception:
        return f"<binary {len(body)} bytes>"


class TrafficMiddleware(BaseHTTPMiddleware):
    """捕获入站 HTTP 流量。"""

    def __init__(self, app, component: str = "unknown", server_url: str = ""):
        super().__init__(app)
        self.component = component
        self.server_url = server_url

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if _should_skip(path):
            return await call_next(request)

        start = time.time()
        request_body = await request.body()

        async def receive():
            return {"type": "http.request", "body": request_body}

        request._receive = receive
        response: Response = await call_next(request)
        latency_ms = (time.time() - start) * 1000

        import threading
        threading.Thread(
            target=_send_traffic_record,
            args=(
                self.server_url,
                self.component,
                "inbound",
                request.method,
                path,
                response.status_code,
                latency_ms,
                request_body,
                response.body if hasattr(response, "body") else b"",
                dict(request.headers),
                dict(response.headers),
            ),
            daemon=True,
        ).start()
        return response


def _send_traffic_record(
    server_url: str,
    component: str,
    direction: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    req_body: bytes,
    resp_body: bytes,
    req_headers: dict,
    resp_headers: dict,
):
    content_type = resp_headers.get("content-type", "")
    request_content_type = req_headers.get("content-type", "")
    parsed_request = _parse_body(req_body, request_content_type)
    parsed_response = _parse_body(resp_body, content_type)
    if isinstance(parsed_request, dict):
        parsed_request = _sanitize_body(parsed_request)
    if isinstance(parsed_response, dict):
        parsed_response = _sanitize_body(parsed_response)

    record = {
        "log_type": "network",
        "timestamp": _now_iso(),
        "event": f"docker_http_{direction}",
        "actor": {},
        "target": {},
        "action": {"name": method, "status": str(status_code)},
        "payload": {
            "request": {
                "method": method,
                "path": path,
                "headers": _sanitize_headers(req_headers),
                "body": parsed_request,
            },
            "response": {
                "status": status_code,
                "headers": _sanitize_headers(resp_headers),
                "body": parsed_response,
            },
        },
        "network": {
            "direction": direction,
            "latency_ms": round(latency_ms, 1),
            "request_bytes": len(req_body),
            "response_bytes": len(resp_body),
            "component": component,
        },
        "trace": {},
    }
    try:
        import requests as requests_client
        requests_client.post(
            f"{server_url}/api/logs/ingest",
            json=record,
            timeout=1,
        )
    except Exception:
        pass


def traffic_post_json(
    url: str,
    json_data: dict,
    *,
    component: str = "unknown",
    server_url: str = "",
    timeout: float = 10,
    **kwargs,
) -> Tuple[bool, Optional[dict]]:
    import requests as requests_client
    start = time.time()
    response = None
    error = None
    try:
        response = requests_client.post(
            url,
            json=json_data,
            timeout=timeout,
            **kwargs,
        )
        response_json = response.json() if response.ok else None
    except Exception as exc:
        error = str(exc)
        response_json = None

    latency_ms = (time.time() - start) * 1000
    status_code = response.status_code if response is not None else 0
    response_body = response.content if response is not None else b""
    response_headers = dict(response.headers) if response is not None else {}
    response_text = ""
    if response_body:
        try:
            response_text = response_body.decode(
                "utf-8", errors="replace"
            )[:2000]
        except Exception:
            response_text = f"<{len(response_body)} bytes>"

    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path or "/"

    record = {
        "log_type": "network",
        "timestamp": _now_iso(),
        "event": "docker_http_outbound",
        "actor": {},
        "target": {"host": parsed.netloc},
        "action": {
            "name": "POST",
            "status": f"error:{error}" if error else str(status_code),
        },
        "payload": {
            "request": {
                "method": "POST",
                "path": path,
                "url": url,
                "body": (
                    _sanitize_body(json_data)
                    if isinstance(json_data, dict)
                    else json_data
                ),
            },
            "response": {
                "status": status_code,
                "headers": _sanitize_headers(response_headers),
                "body": response_text[:2000] if response_text else "",
                "error": error,
            },
        },
        "network": {
            "direction": "outbound",
            "latency_ms": round(latency_ms, 1),
            "request_bytes": (
                len(json.dumps(json_data, ensure_ascii=False).encode())
                if isinstance(json_data, dict)
                else 0
            ),
            "response_bytes": len(response_body),
            "target_host": parsed.netloc,
            "component": component,
        },
        "trace": {},
    }

    if server_url:
        import threading

        def send_record():
            try:
                requests_client.post(
                    f"{server_url}/api/logs/ingest",
                    json=record,
                    timeout=1,
                )
            except Exception:
                pass

        threading.Thread(target=send_record, daemon=True).start()

    return (response is not None and response.ok), response_json


def traffic_requests_post(
    url: str,
    *,
    component: str = "unknown",
    server_url: str = "",
    json_data: dict = None,
    timeout: float = 10,
    **kwargs,
):
    if not traffic_enabled() or not server_url:
        try:
            return requests_post_fallback(
                url,
                json=json_data,
                timeout=timeout,
                **kwargs,
            )
        except Exception:
            return None
    ok, response_json = traffic_post_json(
        url,
        json_data,
        component=component,
        server_url=server_url,
        timeout=timeout,
        **kwargs,
    )
    if ok:
        class FakeResponse:
            def __init__(self, data, status):
                self._json = data
                self.status_code = status
                self.ok = True

            def json(self):
                return self._json

        return FakeResponse(response_json, 200)
    return None


def requests_post_fallback(url: str, **kwargs):
    import requests as requests_client
    return requests_client.post(url, **kwargs)


def traffic_enabled() -> bool:
    return os.environ.get("LOG_DOCKER_HTTP", "0") == "1"
