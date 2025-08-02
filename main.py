"""FastAPI application for the clinic queue system.

The app exposes endpoints for SMS/WhatsApp webhooks, an admin board, and a
simple kiosk.  It reads configuration from environment variables (loaded
via `python-dotenv` when available) and connects to a relational
database using SQLModel.  Redis is optional and used only for event
publishing.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import sqlite3
from typing import Any, Dict
from services import (
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

# We do not rely on python-dotenv in this environment; environment variables
# should be set by the user or defaults will apply.

ADMIN_PASS = os.getenv("ADMIN_PASS")

app = FastAPI(title="Clinic Queue by SMS/WhatsApp")


@app.on_event("startup")
def on_startup() -> None:
    # Initialise the database and settings
    conn_tmp = get_connection()
    init_db(conn_tmp)
    if ADMIN_PASS:
        set_admin_pass(conn_tmp, ADMIN_PASS)
    recompute_positions_and_etas(conn_tmp)
    conn_tmp.close()


@app.post("/webhooks/sms/twilio", response_class=PlainTextResponse)
async def sms_inbound(request: Request) -> str:
    """Handle incoming SMS from Twilio.

    Supported commands (case‑insensitive):

    * `JOIN [note]` – join the queue with an optional note.
    * `STATUS` – get current position and ETA.
    * `LEAVE` – remove your ticket from the queue.
    * `HELP` – return usage instructions.
    """
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
    if not check_rate_limit(from_num, "sms", limit=10, window=300):  # 10 messages per 5 minutes
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
    """Handle incoming WhatsApp messages from Twilio.
    
    Uses the same command logic as SMS but for WhatsApp.
    """
    try:
        import urllib.parse
        
        # Twilio posts form-encoded data for WhatsApp too
        body_bytes = await request.body()
        parsed = urllib.parse.parse_qs(body_bytes.decode('utf-8', errors='ignore'))
        from_num = parsed.get('From', [''])[0]
        text = parsed.get('Body', [''])[0]
        body = (text or "").strip().lower()
        parts = body.split(maxsplit=1)
        command = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else None

        # Rate limiting check (safe - returns True if Redis fails)
        try:
            if not check_rate_limit(from_num, "whatsapp", limit=10, window=300):
                return "Too many requests. Please wait a few minutes before trying again."
        except Exception as e:
            print(f"Rate limit check failed: {e}")
            # Continue without rate limiting

        if command == "join":
            try:
                conn_local = get_connection()
                ticket = create_ticket(conn_local, phone=from_num, note=arg, channel="whatsapp")
                conn_local.close()
                return f"Your ticket is {ticket['code']}. Position #{ticket['position']}. ETA {ticket['eta_minutes']} min. Reply STATUS anytime."
            except Exception as e:
                print(f"Database error during JOIN: {e}")
                return "Service temporarily unavailable. Please try again later."
                
        elif command == "status":
            try:
                conn_local = get_connection()
                ticket = get_ticket_by_phone(conn_local, from_num)
                conn_local.close()
                if not ticket:
                    return "No active ticket. Reply JOIN to enter the queue."
                return f"Ticket {ticket['code']}. Position #{ticket['position']}. ETA {ticket['eta_minutes']} min."
            except Exception as e:
                print(f"Database error during STATUS: {e}")
                return "Service temporarily unavailable. Please try again later."
                
        elif command == "leave":
            try:
                conn_local = get_connection()
                ticket = get_ticket_by_phone(conn_local, from_num)
                if not ticket:
                    conn_local.close()
                    return "No active ticket. Reply JOIN to enter the queue."
                update_ticket_status(conn_local, ticket['code'], 'canceled')
                conn_local.close()
                return f"Ticket {ticket['code']} canceled. Thank you."
            except Exception as e:
                print(f"Database error during LEAVE: {e}")
                return "Service temporarily unavailable. Please try again later."
                
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
            
    except Exception as e:
        print(f"WhatsApp webhook global error: {e}")
        return "Service temporarily unavailable. Please try again later."


@app.post("/webhooks/whatsapp/status", response_class=PlainTextResponse)
async def whatsapp_status(request: Request) -> str:
    """Handle WhatsApp message status callbacks (delivered, read, etc.)"""
    return "OK"


@app.get("/admin/board")
def admin_board(passcode: str) -> Dict[str, Any]:
    """Return the current board state.

    Requires a passcode that matches the stored settings.  If the passcode is
    incorrect, returns HTTP 401.

    A fresh database connection is opened for each request and closed
    immediately after reading the board.  This avoids reliance on a global
    connection that may be unavailable in multi‑threaded or test contexts.
    """
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
    """Perform an action on a ticket (promote, done, no_show, urgent, cancel).

    After the action, returns the updated board.

    A fresh connection is used per request to avoid sharing state across
    concurrent requests.  Any errors (bad passcode, invalid action or missing
    ticket) result in an appropriate HTTPException.
    """
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
    """Return a minimal kiosk check‑in page.

    This page posts to `/kiosk/join` when the button is clicked.
    """
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Kiosk Check‑In</title>
    <style>
        body { font-family: sans-serif; text-align: center; margin-top: 50px; }
        button { font-size: 2rem; padding: 1rem 2rem; }
    </style>
</head>
<body>
    <h1>Join the queue</h1>
    <form method="post" action="/kiosk/join">
        <input type="text" name="note" placeholder="Optional note" style="font-size:1.2rem; padding:0.5rem;" />
        <br/><br/>
        <button type="submit">Join</button>
    </form>
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
    # Use a fresh connection for kiosk operations
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

# Server startup for Railway deployment
if __name__ == "__main__":
    import uvicorn
    
    # Ensure DATABASE_URL is set to Neon database
    if not os.getenv("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "postgresql://checking_owner:npg_MdnKY0Gh1amc@ep-super-scene-a51ij7h2-pooler.us-east-2.aws.neon.tech/checking?sslmode=require&channel_binding=require"
    
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    print(f"🗄️ Using database: {os.getenv('DATABASE_URL')[:50]}...")
    
    # Initialize database
    try:
        conn = get_connection()
        init_db(conn)
        conn.close()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
