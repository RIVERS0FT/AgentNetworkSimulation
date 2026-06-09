"""
统一通信层 — 抽象 Agent 间通信，内存/容器模式共用同一接口。

LocalBus:  内存模式，直接通过 EventBus 通信（零网络开销）
RemoteBus: 容器模式，IP 直连目标 Agent（回退到 Message Bus 中转）
"""

import os
import json
import time
import requests
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class CommLayer(ABC):
    """Agent 通信层抽象基类"""

    inbox: List[Dict[str, Any]]

    @abstractmethod
    def send(self, from_id: str, from_name: str, target: str, content: str) -> bool:
        """发送消息给目标 Agent"""
        ...

    @abstractmethod
    def broadcast(self, from_id: str, from_name: str, content: str) -> bool:
        """广播消息给所有 Agent"""
        ...

    @abstractmethod
    def register_agent(self, agent_id: str, name: str, url: str = "") -> None:
        """向通信层注册 Agent"""
        ...


class RemoteBus(CommLayer):
    """容器模式 — IP 直连，回退 Message Bus 中转"""

    def __init__(self, message_bus_url: str = "http://localhost:9000",
                 server_url: str = "http://localhost:8000"):
        self._bus_url = message_bus_url.rstrip("/")
        self._server_url = server_url.rstrip("/")
        self.inbox: List[Dict[str, Any]] = []
        self._agent_cache: Dict[str, str] = {}  # agent_id → url

    def register_agent(self, agent_id: str, name: str, url: str = "") -> None:
        """向消息总线和服务器注册"""
        try:
            requests.post(
                f"{self._bus_url}/register",
                params={"agent_id": agent_id, "url": url, "name": name},
                timeout=3,
            )
        except Exception:
            pass

    def _lookup_target_url(self, target: str) -> Optional[str]:
        """查询目标 Agent 的 URL（缓存 + API）"""
        tid = target.lower().strip()
        if tid in self._agent_cache:
            return self._agent_cache[tid]

        try:
            resp = requests.get(
                f"{self._server_url}/api/agents/{tid}",
                timeout=2,
            )
            if resp.ok:
                data = resp.json()
                # Agent status includes url from container info
                url = data.get("url") or data.get("container_url", "")
                if url:
                    self._agent_cache[tid] = url
                    return url
        except Exception:
            pass

        # Try listing all agents
        try:
            resp = requests.get(f"{self._server_url}/api/agents", timeout=2)
            if resp.ok:
                for a in resp.json():
                    aid = a.get("agent_id", "").lower()
                    url = a.get("url") or a.get("container_url", "")
                    if url:
                        self._agent_cache[aid] = url
                    # Also index by name
                    name = a.get("name", "").lower()
                    if name:
                        self._agent_cache[name] = url
                return self._agent_cache.get(tid)
        except Exception:
            pass

        return None

    def _log_send(self, from_id: str, from_name: str, target: str, content: str, ok: bool):
        """记录发包到服务器日志"""
        try:
            requests.post(f"{self._server_url}/api/logs/agent", json={
                "agent_id": from_id,
                "agent_name": from_name,
                "event": "packet_send",
                "detail": f"{'OK' if ok else 'FAIL'} → {target}: {content[:100]}",
            }, timeout=1)
        except Exception:
            pass

    def send(self, from_id: str, from_name: str, target: str, content: str) -> bool:
        """IP 直连目标 Agent"""
        target_url = self._lookup_target_url(target)
        if not target_url:
            self._log_send(from_id, from_name, target, content, False)
            return False
        try:
            resp = requests.post(f"{target_url}/message", json={
                "from_id": from_id,
                "from_name": from_name,
                "content": content,
            }, timeout=5)
            ok = resp.ok
            self._log_send(from_id, from_name, target, content, ok)
            return ok
        except Exception:
            self._agent_cache.pop(target.lower().strip(), None)
            self._log_send(from_id, from_name, target, content, False)
            return False

    def broadcast(self, from_id: str, from_name: str, content: str) -> bool:
        """广播：拉取所有 Agent URL 逐个 IP 直连"""
        try:
            resp = requests.get(f"{self._server_url}/api/agents", timeout=2)
            if resp.ok:
                agents = resp.json()
                ok = 0
                for a in agents:
                    url = a.get("url") or a.get("container_url", "")
                    if not url:
                        continue
                    aid = a.get("agent_id", "")
                    if aid.lower() == from_id.lower():
                        continue
                    try:
                        r = requests.post(f"{url}/message", json={
                            "from_id": from_id,
                            "from_name": from_name,
                            "content": content,
                        }, timeout=3)
                        if r.ok:
                            ok += 1
                    except Exception:
                        pass
                self._log_send(from_id, from_name, "broadcast", content, ok > 0)
                return ok > 0
        except Exception:
            pass

        return False
