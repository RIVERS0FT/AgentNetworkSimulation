"""
统一通信层 — 抽象 Agent 间通信，内存/容器模式共用同一接口。

LocalBus:  内存模式，直接通过 EventBus 通信（零网络开销）
RemoteBus: 容器模式，通过 Message Bus HTTP 中转（进程隔离）
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
    """容器模式 — 通过 Message Bus HTTP 中转"""

    def __init__(self, message_bus_url: str = "http://localhost:9000"):
        self._bus_url = message_bus_url.rstrip("/")
        self.inbox: List[Dict[str, Any]] = []

    def register_agent(self, agent_id: str, name: str, url: str = "") -> None:
        """向消息总线注册"""
        try:
            requests.post(
                f"{self._bus_url}/register",
                params={"agent_id": agent_id, "url": url, "name": name},
                timeout=3,
            )
        except Exception:
            pass

    def send(self, from_id: str, from_name: str, target: str, content: str) -> bool:
        """通过消息总线发送消息"""
        try:
            resp = requests.post(f"{self._bus_url}/relay", json={
                "from_id": from_id,
                "from_name": from_name,
                "to": target,
                "content": content,
            }, timeout=5)
            return resp.ok
        except Exception:
            return False

    def broadcast(self, from_id: str, from_name: str, content: str) -> bool:
        """广播 — 消息总线 relay 到 broadcast"""
        return self.send(from_id, from_name, "broadcast", content)
