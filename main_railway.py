"""FastAPI application for the clinic queue system - Railway deployment version.

This version uses PostgreSQL for production and includes all necessary
configurations for Railway deployment.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
from typing import Any, Dict

# Import Railway-compatible services
from services_railway import (
    get_connection,
    init_db,
    get_settings,
    set_admin_pass,
    recompute_positions_and_etas,
    create_ticket,
    update_ticket_status,
    get_board,
    get_ticket_by_phone,
    check_rate_limit,
    get_redis,
)
from schemas import ActionRequest

# Load environment variables
ADMIN_PASS = os.getenv("ADMIN_PASS")
PORT = int(os.getenv("PORT", 8000))

app = FastAPI(
    title="Clinic Queue by SMS/WhatsApp",
    description="Virtual queue management system for healthcare facilities",
    version="1.0.0"
)

# Add CORS middleware for Railway
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize the database and settings on startup."""
    print("🚀 Starting Clinic Queue application...")
    print(f"🗄️ Database URL: {'PostgreSQL' if os.getenv('DATABASE_URL', '').startswith('postgres') else 'SQLite'}")
    print(f"⚡ Redis URL: {'Connected' if os.getenv('REDIS_URL') else 'Not configured'}")
    
    conn_tmp = get_connection()
    init_db(conn_tmp)
    
    if ADMIN_PASS:
        set_admin_pass(conn_tmp, ADMIN_PASS)
        print(f"🔐 Admin password set from environment")
    
    recompute_positions_and_etas(conn_tmp)
    conn_tmp.close()
    
    print("✅ Clinic Queue started successfully!")


@app.get("/")
def root():
    """Root endpoint with system status."""
    return {
        "service": "Clinic Queue API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "admin_dashboard": "/static/admin.html",
            "kiosk": "/kiosk",
            "admin_api": "/admin/board",
            "webhooks": {
                "sms": "/webhooks/sms/twilio",
                "whatsapp": "/webhooks/whatsapp"
            }
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint for Railway."""
    try:
        conn = get_connection()
        settings = get_settings(conn)
        conn.close()
        
        redis_status = "connected" if get_redis() else "unavailable"
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": redis_status,
            "clinic_name": settings.get("clinic_name", "Clinic Queue")
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/webhooks/sms/twilio", response_class=PlainTextResponse)
async def sms_inbound(request: Request) -> str:
    """Handle incoming SMS from Twilio."""
    import urllib.parse

    # Twilio posts form-encoded data; parse manually to avoid python-multipart
    body_bytes = await request.body()
    parsed = urllib.parse.parse_qs(body_bytes.decode())
    from_num = parsed.get('From', [''])[0]
    text = parsed.get('Body', [''])[0]
    body = (text or "").strip().lower()
    parts = body.split(maxsplit=1)
    command = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else None

    # Rate limiting check
    if not check_rate_limit(from_num, "sms", limit=10, window=300):
        return "Too many requests. Please wait a few minutes before trying again."

    if command == "join":
        conn_local = get_connection()
        ticket = create_ticket(conn_local, phone=from_num, note=arg, channel="sms")
        conn_local.close()
        return f"Your ticket is {ticket['code']}. Position #{ticket['position']}. ETA {ticket['eta_minutes']} min. Reply STATUS anytime."
    elif command == "status":
        conn_local = get_connection()
        ticket = get_ticket_by_phone(conn_local, from_num)
        conn_local.close()
        if not ticket:
            return "No active ticket. Reply JOIN to enter the queue."
        return f"Ticket {ticket['code']}. Position #{ticket['position']}. ETA {ticket['eta_minutes']} min."
    elif command == "leave":
        conn_local = get_connection()
        ticket = get_ticket_by_phone(conn_local, from_num)
        if not ticket:
            conn_local.close()
            return "No active ticket. Reply JOIN to enter the queue."
        update_ticket_status(conn_local, ticket['code'], 'canceled')
        conn_local.close()
        return f"Ticket {ticket['code']} canceled. Thank you."
    elif command == "help":
        return (
            "Commands:\n"
            "JOIN [note] – join the queue with an optional note (e.g., fever).\n"
            "STATUS – check your current position and ETA.\n"
            "LEAVE – cancel your ticket.\n"
            "HELP – show this message."
        )
    else:
        return "Unknown command. Send HELP for usage."


@app.post("/webhooks/whatsapp", response_class=PlainTextResponse)
async def whatsapp_inbound(request: Request) -> str:
    """Handle incoming WhatsApp messages from Twilio."""
    import urllib.parse
    
    # Twilio posts form-encoded data for WhatsApp too
    body_bytes = await request.body()
    parsed = urllib.parse.parse_qs(body_bytes.decode())
    from_num = parsed.get('From', [''])[0]
    text = parsed.get('Body', [''])[0]
    body = (text or "").strip().lower()
    parts = body.split(maxsplit=1)
    command = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else None

    # Rate limiting check
    if not check_rate_limit(from_num, "whatsapp", limit=10, window=300):
        return "Too many requests. Please wait a few minutes before trying again."

    if command == "join":
        conn_local = get_connection()
        ticket = create_ticket(conn_local, phone=from_num, note=arg, channel="whatsapp")
        conn_local.close()
        return f"Your ticket is {ticket['code']}. Position #{ticket['position']}. ETA {ticket['eta_minutes']} min. Reply STATUS anytime."
    elif command == "status":
        conn_local = get_connection()
        ticket = get_ticket_by_phone(conn_local, from_num)
        conn_local.close()
        if not ticket:
            return "No active ticket. Reply JOIN to enter the queue."
        return f"Ticket {ticket['code']}. Position #{ticket['position']}. ETA {ticket['eta_minutes']} min."
    elif command == "leave":
        conn_local = get_connection()
        ticket = get_ticket_by_phone(conn_local, from_num)
        if not ticket:
            conn_local.close()
            return "No active ticket. Reply JOIN to enter the queue."
        update_ticket_status(conn_local, ticket['code'], 'canceled')
        conn_local.close()
        return f"Ticket {ticket['code']} canceled. Thank you."
    elif command == "help":
        return (
            "Commands:\n"
            "JOIN [note] – join the queue with an optional note (e.g., fever).\n"
            "STATUS – check your current position and ETA.\n"
            "LEAVE – cancel your ticket.\n"
            "HELP – show this message."
        )
    else:
        return "Unknown command. Send HELP for usage."


@app.post("/webhooks/whatsapp/status", response_class=PlainTextResponse)
async def whatsapp_status(request: Request) -> str:
    """Handle WhatsApp message status callbacks (delivered, read, etc.)"""
    return "OK"


@app.get("/admin/board")
def admin_board(passcode: str) -> Dict[str, Any]:
    """Return the current board state."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        board = get_board(conn_local)
        return board
    finally:
        conn_local.close()


@app.post("/admin/action")
def admin_action(request: ActionRequest) -> Dict[str, Any]:
    """Perform an action on a ticket."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if request.passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        action = request.action
        code = request.code
        status_map = {
            "promote": "next",
            "in_room": "in_room",
            "done": "done",
            "no_show": "no_show",
            "urgent": "urgent",
            "cancel": "canceled",
        }
        new_status = status_map.get(action)
        if not new_status:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        updated = update_ticket_status(conn_local, code, new_status)
        if not updated:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        board = get_board(conn_local)
        return board
    finally:
        conn_local.close()


@app.get("/kiosk", response_class=HTMLResponse)
def kiosk_page() -> str:
    """Return a minimal kiosk check-in page."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Kiosk Check-In</title>
    <style>
        body { font-family: sans-serif; text-align: center; margin-top: 50px; background: #f5f5f5; }
        .container { max-width: 500px; margin: 0 auto; background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #333; margin-bottom: 2rem; }
        input { font-size: 1.2rem; padding: 0.8rem; width: 100%; margin-bottom: 1rem; border: 2px solid #ddd; border-radius: 5px; }
        button { font-size: 1.5rem; padding: 1rem 2rem; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 Join the Queue</h1>
        <form method="post" action="/kiosk/join">
            <input type="text" name="note" placeholder="Reason for visit (optional)" />
            <br/>
            <button type="submit">Get Ticket</button>
        </form>
    </div>
</body>
</html>
    """


@app.post("/kiosk/join", response_class=PlainTextResponse)
async def kiosk_join(request: Request) -> str:
    """Create a ticket from the kiosk."""
    import urllib.parse

    body_bytes = await request.body()
    parsed = urllib.parse.parse_qs(body_bytes.decode())
    note = parsed.get("note", [None])[0]
    
    conn_local = get_connection()
    try:
        ticket = create_ticket(conn_local, phone=None, note=note, channel="kiosk")
        return f"Your ticket is {ticket['code']}. You are #{ticket['position']}. ETA {ticket['eta_minutes']} min. Please stay nearby."
    finally:
        conn_local.close()


@app.get("/admin/events")
async def admin_events(passcode: str):
    """Server-Sent Events endpoint for real-time admin board updates."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
    finally:
        conn_local.close()
    
    async def event_stream():
        redis_client = get_redis()
        if not redis_client:
            # Fallback: just send periodic board updates
            while True:
                try:
                    conn_local = get_connection()
                    board = get_board(conn_local, use_cache=False)
                    conn_local.close()
                    yield f"data: {json.dumps({'type': 'board_update', 'data': {'tickets': board}})}\n\n"
                    await asyncio.sleep(5)
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    await asyncio.sleep(5)
        else:
            # Use Redis pub/sub for real-time updates
            pubsub = redis_client.pubsub()
            pubsub.subscribe("clinic:updates")
            
            try:
                while True:
                    try:
                        message = pubsub.get_message(timeout=5.0)
                        if message and message['type'] == 'message':
                            yield f"data: {message['data']}\n\n"
                        else:
                            # Send heartbeat
                            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                        await asyncio.sleep(1)
            finally:
                pubsub.close()
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


# Mount static files (admin board script)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)