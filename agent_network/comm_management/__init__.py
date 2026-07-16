"""Unified Agent-to-Agent communication management."""

from .comm_manager import (
    A2A_MEDIA_TYPE,
    A2A_PROTOCOL_VERSION,
    BatchSendResult,
    CommManager,
    CommunicationError,
    SendResult,
)

__all__ = [
    "A2A_MEDIA_TYPE",
    "A2A_PROTOCOL_VERSION",
    "BatchSendResult",
    "CommManager",
    "CommunicationError",
    "SendResult",
]
