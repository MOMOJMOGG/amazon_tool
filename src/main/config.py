"""Configuration settings for the Amazon Product Monitoring Tool."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )
    
    # Database Configuration
    database_url: str
    
    # Redis Configuration  
    redis_url: str = "redis://localhost:6379"
    
    # Application Configuration
    log_level: str = "INFO"
    environment: str = "development"
    
    # Logging Configuration
    log_dir: str = "logs"
    log_file: str = "app.log"
    error_log_file: str = "error.log"
    log_max_size: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Cache Configuration
    cache_ttl_seconds: int = 86400  # 24 hours
    cache_stale_seconds: int = 3600  # 1 hour
    
    # OpenAI Configuration (M5)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_max_tokens: int = 2000


# Global settings instance
settings = Settings()