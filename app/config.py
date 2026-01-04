from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/Devcon"
    #For OnlineService
    #postgresql://<username>:<password>@<host>:<port>/<database_name>
# Use this Structure
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "msaadbinmazhar@gmail.com"
    SMTP_PASSWORD: str = "pcfc jxzl actk lgbn"
    FROM_EMAIL: str = "noreply@devcon26.com"
    
    # File Uploads
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".pdf"]
    
    # QR Codes
    QR_CODE_DIR: str = "app/static/qrcodes"
    
    # Event
    TEAM_MIN_SIZE: int = 2
    TEAM_MAX_SIZE: int = 5
    
    # Payment
    REGISTRATION_FEE: float = 1000.0
    
    # Debug
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()