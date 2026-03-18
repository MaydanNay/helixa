from pydantic import Field
from pydantic_settings import BaseSettings
from arq.connections import RedisSettings

class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/1"
    llm_api_key: str = ""
    alem_api_key: str = Field(default="", alias="ALEM_API_KEY")
    gemini_api_key: str = ""
    gemma_api_key: str = ""
    qwen_api_key: str = ""
    gpt_oss_api_key: str = ""
    openai_api_key: str = ""
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    secret_key: str = "super_secret_jwt_key_helixa"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    llm_provider: str = "alemllm"
    auditor_provider: str = "alemllm"
    generator_provider: str = "alemllm"
    judge_provider: str = "alemllm"
    structured_provider: str = "alemllm"
    local_llm_url: str = ""
    enable_consensus: str = "true"  # Set to "false" to skip consensus review (faster/cheaper)
    enable_judge: str = "true"      # Set to "false" to disable Super Judge (single model, faster)
    daily_generation_limit: int = 5 # Prevent financial DoS

    helixa_database_url: str = Field(default="postgresql+asyncpg://helixa:helixa_secret@localhost:5432/helixa")
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_password: str = "helixa_graph_secret"

    class Config:
        env_file = ".env"
        populate_by_name = True
        extra = "ignore"

    @property
    def redis_settings(self) -> RedisSettings:
        return RedisSettings.from_dsn(self.redis_url)

settings = Settings()
