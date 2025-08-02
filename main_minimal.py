"""Minimal Railway deployment to get app working again."""

import os
import sys
import logging
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("🚀 Starting Clinic Queue Minimal App...")
logger.info(f"🐍 Python version: {sys.version}")
logger.info(f"📁 Working directory: {os.getcwd()}")
logger.info(f"🌐 PORT environment variable: {os.getenv('PORT', 'NOT_SET')}")

try:
    app = FastAPI(title="Clinic Queue - Minimal")
    logger.info("✅ FastAPI app created successfully")
except Exception as e:
    logger.error(f"❌ Failed to create FastAPI app: {e}")
    logger.error(f"❌ Traceback: {traceback.format_exc()}")
    raise

# Add CORS
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("✅ CORS middleware added successfully")
except Exception as e:
    logger.error(f"❌ Failed to add CORS middleware: {e}")
    logger.error(f"❌ Traceback: {traceback.format_exc()}")
    raise

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to catch any unhandled errors."""
    logger.error(f"🔥 GLOBAL EXCEPTION: {exc}")
    logger.error(f"🔥 Request URL: {request.url}")
    logger.error(f"🔥 Request method: {request.method}")
    logger.error(f"🔥 Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses."""
    logger.info(f"🌐 INCOMING REQUEST: {request.method} {request.url}")
    logger.info(f"🌐 Request headers: {dict(request.headers)}")
    
    try:
        response = await call_next(request)
        logger.info(f"✅ RESPONSE: Status {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ REQUEST ERROR: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise

@app.on_event("startup")
async def startup_event():
    """Startup event with logging."""
    logger.info("🎯 App startup event triggered")
    logger.info("🎉 Minimal app startup complete!")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event with logging."""
    logger.info("🛑 App shutdown event triggered")

@app.get("/")
def root():
    """Root endpoint."""
    logger.info("📍 Root endpoint called")
    try:
        response = {
            "status": "running",
            "service": "Clinic Queue API",
            "version": "minimal",
            "message": "App is working - database will be connected next",
            "port": os.getenv("PORT", "unknown")
        }
        logger.info(f"✅ Root endpoint responding: {response}")
        return response
    except Exception as e:
        logger.error(f"❌ Root endpoint error: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise

@app.get("/health")
def health():
    """Health check."""
    logger.info("🏥 Health endpoint called")
    try:
        response = {
            "status": "healthy",
            "message": "Minimal version running",
            "database": "not_connected_yet",
            "app_working": True,
            "port": os.getenv("PORT", "unknown"),
            "python_version": sys.version.split()[0]
        }
        logger.info(f"✅ Health endpoint responding: {response}")
        return response
    except Exception as e:
        logger.error(f"❌ Health endpoint error: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise

@app.post("/webhooks/whatsapp", response_class=PlainTextResponse)
async def whatsapp_minimal(request: Request) -> str:
    """Minimal WhatsApp webhook that always works."""
    logger.info("📞 WhatsApp webhook called")
    try:
        # Just return a working response
        response = "Clinic Queue is being updated. Please try again in a few minutes."
        logger.info(f"✅ WhatsApp webhook responding: {response}")
        return response
    except Exception as e:
        error_msg = f"Service update in progress. Error: {str(e)}"
        logger.error(f"❌ WhatsApp webhook error: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return error_msg

@app.post("/webhooks/whatsapp/debug", response_class=PlainTextResponse)
async def debug_minimal(request: Request) -> str:
    """Debug endpoint."""
    logger.info("🔍 Debug webhook called")
    try:
        body = await request.body()
        response = f"DEBUG: App is running. Body size: {len(body)} bytes. Raw: {body[:100]}"
        logger.info(f"✅ Debug webhook responding: {response}")
        return response
    except Exception as e:
        error_msg = f"DEBUG_ERROR: {str(e)}"
        logger.error(f"❌ Debug webhook error: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return error_msg

# Log module completion
logger.info("📝 All endpoints and middleware defined successfully")

if __name__ == "__main__":
    logger.info("🚀 Starting uvicorn server...")
    try:
        import uvicorn
        port = int(os.getenv("PORT", 8000))
        logger.info(f"🌐 Starting server on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"❌ Failed to start uvicorn: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise