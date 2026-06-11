import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
# Any OpenAI-compatible endpoint (Nous Portal, OpenRouter, self-hosted...).
# If LLM_API_KEY is set, this takes precedence over Anthropic.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "Hermes-4-405B")
HONCHO_API_KEY = os.getenv("HONCHO_API_KEY", "")
HONCHO_WORKSPACE_ID = os.getenv("HONCHO_WORKSPACE_ID", "kc-hq-v1")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/hq.db")
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days
