from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    admin_password: str
    llm_url: str = "http://llm-chat:8080"
    embed_url: str = "http://llm-embed:8080"
    llm_concurrency: int = 4        
    llm_max_queue: int = 12         
    jwt_ttl_hours: int = 8

settings = Settings()