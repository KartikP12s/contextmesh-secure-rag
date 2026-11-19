from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://contextmesh:local-only@localhost:5440/contextmesh"
    embedding_provider: str = "fastembed"
    answer_provider: str = "extractive"
    model_cache: str = "data/models"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    cors_origin: str = "http://localhost:5174"
    min_score: float = 0.35
    demo_tokens_json: str = '{"local-acme-admin":{"user":"acme.admin","tenant":"acme","role":"admin","groups":["hr","engineering"]},"local-acme-hr":{"user":"acme.hr","tenant":"acme","role":"member","groups":["hr"]},"local-acme-engineering":{"user":"acme.engineer","tenant":"acme","role":"member","groups":["engineering"]},"local-northstar-admin":{"user":"northstar.admin","tenant":"northstar","role":"admin","groups":["hr","engineering"]},"local-northstar-hr":{"user":"northstar.hr","tenant":"northstar","role":"member","groups":["hr"]},"local-northstar-engineering":{"user":"northstar.engineer","tenant":"northstar","role":"member","groups":["engineering"]},"local-orbit-hr":{"user":"orbit.hr","tenant":"orbit","role":"member","groups":["hr"]},"local-orbit-admin":{"user":"orbit.admin","tenant":"orbit","role":"admin","groups":["hr","engineering"]},"local-orbit-engineering":{"user":"orbit.engineer","tenant":"orbit","role":"member","groups":["engineering"]}}'


@lru_cache
def settings():
    return Settings()
