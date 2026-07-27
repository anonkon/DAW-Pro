from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    # "gemini" (default, unchanged), "anthropic", or "openai" — selects which
    # provider backs the mentor-narrative LLM call in app/ai/chain.py.
    llm_provider: str = "gemini"
    # Overridable rather than hardcoded so a model rename/deprecation is a
    # config change, not a code change. anthropic_model has a real default;
    # openai_model deliberately doesn't — there's no current OpenAI model ID
    # we're confident enough to bake in, so an unset value is treated as
    # "openai not configured" the same way a missing API key is.
    anthropic_model: str = "claude-opus-5"
    openai_model: str | None = None

    supabase_url: str | None = None
    supabase_service_key: str | None = None

    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None


settings = Settings()
