"""Configuration settings for the Amazon Product Monitoring Tool."""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Redis Configuration  
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # Application Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # Cache Configuration
    cache_ttl_seconds: int = Field(default=86400, env="CACHE_TTL_SECONDS")  # 24 hours
    cache_stale_seconds: int = Field(default=3600, env="CACHE_STALE_SECONDS")  # 1 hour
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()