import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
HONCHO_API_KEY = os.getenv("HONCHO_API_KEY", "")
HONCHO_WORKSPACE_ID = os.getenv("HONCHO_WORKSPACE_ID", "kc-hq-v1")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/hq.db")
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days
