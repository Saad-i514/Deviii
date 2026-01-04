from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
from app.api.v1.api import api_router
from app.config import settings
from app.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="Devcon '26 Registration System API",
    description="Backend API for Devcon '26 Registration System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Create upload directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.QR_CODE_DIR, exist_ok=True)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Devcon '26 Registration API",
        "status": "operational",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )