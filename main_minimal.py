"""Minimal Railway deployment to get app working again."""

import os
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Clinic Queue - Minimal")

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
        "status": "running",
        "service": "Clinic Queue API",
        "version": "minimal",
        "message": "App is working - database will be connected next"
    }

@app.get("/health")
def health():
    """Health check."""
    return {
        "status": "healthy",
        "message": "Minimal version running",
        "database": "not_connected_yet",
        "app_working": True
    }

@app.post("/webhooks/whatsapp", response_class=PlainTextResponse)
async def whatsapp_minimal(request: Request) -> str:
    """Minimal WhatsApp webhook that always works."""
    try:
        # Just return a working response
        return "Clinic Queue is being updated. Please try again in a few minutes."
    except Exception as e:
        return f"Service update in progress. Error: {str(e)}"

@app.post("/webhooks/whatsapp/debug", response_class=PlainTextResponse)
async def debug_minimal(request: Request) -> str:
    """Debug endpoint."""
    import json
    try:
        body = await request.body()
        return f"DEBUG: App is running. Body size: {len(body)} bytes. Raw: {body[:100]}"
    except Exception as e:
        return f"DEBUG_ERROR: {str(e)}"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)