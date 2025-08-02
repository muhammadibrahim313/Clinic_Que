"""Emergency fallback app if PostgreSQL fails."""

import os
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Clinic Queue - Emergency Mode")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "status": "emergency_mode",
        "service": "Clinic Queue API",
        "message": "Running in emergency mode - PostgreSQL connection failed",
        "port": os.getenv("PORT", "unknown")
    }

@app.get("/health")
def health():
    """Health check."""
    return {
        "status": "degraded",
        "message": "Emergency mode - database unavailable",
        "database": "postgresql_failed",
        "app_working": True
    }

@app.post("/webhooks/whatsapp", response_class=PlainTextResponse)
async def whatsapp_emergency(request: Request) -> str:
    """Emergency WhatsApp webhook."""
    return "Service is temporarily in maintenance mode. Please try again in a few minutes."

@app.post("/webhooks/whatsapp/status", response_class=PlainTextResponse)
async def whatsapp_status_emergency(request: Request) -> str:
    """Emergency WhatsApp status webhook."""
    return "OK"

@app.get("/admin/board")
def admin_board_emergency():
    """Emergency admin board."""
    return {
        "error": "Database unavailable",
        "message": "System is in emergency mode",
        "waiting": [],
        "recent": []
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚨 Starting emergency app on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)