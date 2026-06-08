"""Shared LLM configuration — single source of truth."""

# Default model used across brain.py, llm_parser.py, terrain.py
DEFAULT_LLM_MODEL = "claude-sonnet-4-6"

# OpenAI-compatible fallback
DEFAULT_OPENAI_MODEL = "deepseek-chat"
DEFAULT_OPENAI_BASE = "https://api.deepseek.com/v1"
