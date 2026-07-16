"""Compatibility import for the unified A2A communication manager.

New code must import from :mod:`agent_network.comm_management`.  The former
DirectBus and its broadcast operation have been removed.
"""

from agent_network.comm_management import CommManager

__all__ = ["CommManager"]
