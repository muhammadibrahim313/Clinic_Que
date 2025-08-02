"""Debug version to identify Railway startup issues."""

import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Clinic Queue - Debug")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def debug_startup():
    """Debug startup to identify issues."""
    logger.info("🚀 Debug startup beginning...")
    
    # Check environment variables
    database_url = os.getenv("DATABASE_URL", "NOT_SET")
    redis_url = os.getenv("REDIS_URL", "NOT_SET")
    admin_pass = os.getenv("ADMIN_PASS", "NOT_SET")
    port = os.getenv("PORT", "NOT_SET")
    
    logger.info(f"📊 DATABASE_URL: {'SET' if database_url != 'NOT_SET' else 'NOT_SET'}")
    logger.info(f"⚡ REDIS_URL: {'SET' if redis_url != 'NOT_SET' else 'NOT_SET'}")
    logger.info(f"🔐 ADMIN_PASS: {'SET' if admin_pass != 'NOT_SET' else 'NOT_SET'}")
    logger.info(f"🌐 PORT: {port}")
    
    # Test imports
    try:
        import psycopg2
        logger.info("✅ psycopg2 import successful")
    except ImportError as e:
        logger.error(f"❌ psycopg2 import failed: {e}")
    
    try:
        import redis
        logger.info("✅ redis import successful")
    except ImportError as e:
        logger.error(f"❌ redis import failed: {e}")
    
    # Test database connection (only if URL is set)
    if database_url != "NOT_SET" and database_url.startswith("postgres"):
        try:
            import psycopg2
            conn = psycopg2.connect(database_url, connect_timeout=5)
            conn.close()
            logger.info("✅ Database connection successful")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
    
    logger.info("🎉 Debug startup complete!")

@app.get("/")
def root():
    """Root endpoint with debug info."""
    return {
        "status": "running",
        "service": "Clinic Queue Debug",
        "message": "App started successfully",
        "env_vars": {
            "DATABASE_URL": "SET" if os.getenv("DATABASE_URL") else "NOT_SET",
            "REDIS_URL": "SET" if os.getenv("REDIS_URL") else "NOT_SET", 
            "ADMIN_PASS": "SET" if os.getenv("ADMIN_PASS") else "NOT_SET",
            "PORT": os.getenv("PORT", "NOT_SET")
        }
    }

@app.get("/health")
def health():
    """Health check with dependency testing."""
    result = {"status": "healthy", "app": "working"}
    
    # Test imports
    try:
        import psycopg2
        result["psycopg2"] = "available"
    except ImportError:
        result["psycopg2"] = "missing"
    
    try:
        import redis
        result["redis"] = "available"
    except ImportError:
        result["redis"] = "missing"
    
    return result

@app.post("/webhooks/whatsapp", response_class=PlainTextResponse)
async def webhook_debug(request: Request) -> str:
    """Debug webhook."""
    return "Debug webhook working! Main functionality coming back online soon."

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)