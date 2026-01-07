from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    
    # Database - Railway will provide this via environment variable
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/Devcon")
    
    # Security - Use environment variables for production
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Email Configuration
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "msaadbinmazhar@gmail.com")
 
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
 
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "put your token here")
 
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "msaadbinmazhar@gmail.com")
    
    # File Uploads - Use /tmp for Railway (ephemeral storage)
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(5 * 1024 * 1024)))  # 5MB
    ALLOWED_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".pdf"]
    
    # QR Codes - Use /tmp for Railway
    QR_CODE_DIR: str = os.getenv("QR_CODE_DIR", "/tmp/qrcodes")
    
    # Event Configuration
    TEAM_MIN_SIZE: int = int(os.getenv("TEAM_MIN_SIZE", "2"))
    TEAM_MAX_SIZE: int = int(os.getenv("TEAM_MAX_SIZE", "5"))
    
    # Payment
    REGISTRATION_FEE: float = float(os.getenv("REGISTRATION_FEE", "1000.0"))
    
    # Environment
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("RAILWAY_ENVIRONMENT", "development")
    
    # Railway specific
    PORT: int = int(os.getenv("PORT", "8000"))
    
    class Config:
        env_file = ".env"

settings = Settings()
