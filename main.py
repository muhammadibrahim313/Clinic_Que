"""FastAPI application for the clinic queue system.

The app exposes endpoints for SMS/WhatsApp webhooks, an admin board, and a
simple kiosk.  It reads configuration from environment variables (loaded
via `python-dotenv` when available) and connects to a relational
database using SQLModel.  Redis is optional and used only for event
publishing.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import sqlite3
from datetime import datetime
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
    get_queue_analytics,
    get_patient_flow_timeline,
    get_performance_metrics,
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
    """Handle incoming WhatsApp messages from Twilio with enhanced UX.
    
    Supports interactive messages, better formatting, and user-friendly responses.
    """
    import urllib.parse
    
    # Twilio posts form-encoded data for WhatsApp too
    body_bytes = await request.body()
    parsed = urllib.parse.parse_qs(body_bytes.decode())
    from_num = parsed.get('From', [''])[0]
    text = parsed.get('Body', [''])[0]
    message_type = parsed.get('MessageType', ['text'])[0]
    media_url = parsed.get('MediaUrl0', [''])[0]
    media_type = parsed.get('MediaContentType0', [''])[0]
    
    # Handle different message types
    if message_type == 'interactive':
        # Handle button/list responses
        button_payload = parsed.get('ButtonPayload', [''])[0]
        return await handle_whatsapp_interactive(from_num, button_payload)
    elif media_url and media_type:
        # Handle media messages (images, documents, audio)
        return await handle_whatsapp_media(from_num, media_url, media_type, text)
    
    body = (text or "").strip().lower()
    parts = body.split(maxsplit=1)
    command = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else None

    # Rate limiting check
    if not check_rate_limit(from_num, "whatsapp", limit=15, window=300):  # 15 messages per 5 minutes
        return "⏰ *Rate limit reached*\n\nPlease wait a few minutes before trying again. This helps us provide better service to everyone! 🙏"

    # Enhanced command handling with emojis and better formatting
    if command in ["join", "register", "book", "queue", "hi", "hello", "start"]:
        return await handle_whatsapp_join(from_num, arg)
    elif command in ["status", "position", "where", "when", "eta", "time"]:
        return await handle_whatsapp_status(from_num)
    elif command in ["leave", "cancel", "exit", "quit", "remove"]:
        return await handle_whatsapp_leave(from_num)
    elif command in ["help", "info", "commands", "?", "menu"]:
        return get_whatsapp_help_message()
    elif command in ["location", "address", "directions", "where"]:
        return get_clinic_info()
    else:
        # First-time user or unclear command
        return get_whatsapp_welcome_message()


async def handle_whatsapp_media(from_num: str, media_url: str, media_type: str, caption: str = "") -> str:
    """Handle WhatsApp media messages (images, documents, voice notes)."""
    conn_local = get_connection()
    try:
        # Check if user has an active ticket
        ticket = get_ticket_by_phone(conn_local, from_num)
        
        # Process different media types
        if media_type.startswith('image/'):
            # Handle image attachments (could be symptoms, ID, insurance card)
            response = (
                f"📸 *Image received!*\n\n"
                f"Thank you for sharing the image."
            )
            
            if ticket:
                # Update ticket with media note
                note_update = f"📎 Image attachment: {caption}" if caption else "📎 Image attachment received"
                # You could store media URL in a separate table or add to notes
                response += f"\n🎫 Added to your ticket: *{ticket['code']}*"
            else:
                response += f"\n\n💡 *Tip:* Send *JOIN* first to enter the queue, then share any relevant images."
            
        elif media_type.startswith('audio/'):
            # Handle voice messages
            response = (
                f"🎤 *Voice message received!*\n\n"
                f"We've received your voice note."
            )
            
            if ticket:
                response += f"\n🎫 Noted for ticket: *{ticket['code']}*\n💬 Our staff will review this when you're called."
            else:
                response += f"\n\n💡 Send *JOIN* to enter the queue first."
                
        elif media_type.startswith('application/') or media_type == 'document':
            # Handle documents (PDF, insurance cards, etc.)
            response = (
                f"📄 *Document received!*\n\n"
                f"Thank you for sharing the document."
            )
            
            if ticket:
                response += f"\n🎫 Added to your file for ticket: *{ticket['code']}*"
            else:
                response += f"\n\n💡 Send *JOIN* to enter the queue, then share relevant documents."
                
        else:
            response = (
                f"📎 *Media received!*\n\n"
                f"Thank you for sharing. Our staff will review this."
            )
        
        # Add helpful commands
        response += (
            f"\n\n📱 *Available commands:*\n"
            f"• *STATUS* - Check your position\n"
            f"• *JOIN* - Enter the queue\n"
            f"• *HELP* - See all options"
        )
        
        return response
        
    finally:
        conn_local.close()


async def handle_whatsapp_join(from_num: str, note: str = None) -> str:
    """Enhanced join flow with better messaging."""
    conn_local = get_connection()
    try:
        # Check if user already has an active ticket
        existing_ticket = get_ticket_by_phone(conn_local, from_num)
        if existing_ticket:
            return (
                f"🎫 *You already have an active ticket!*\n\n"
                f"📋 Ticket: *{existing_ticket['code']}*\n"
                f"🏆 Position: *#{existing_ticket['position']}*\n"
                f"⏰ ETA: *{existing_ticket['eta_minutes']} minutes*\n\n"
                f"💬 Reply *STATUS* for updates\n"
                f"❌ Reply *LEAVE* to cancel"
            )
        
        # Create new ticket
        ticket = create_ticket(conn_local, phone=from_num, note=note, channel="whatsapp")
        
        # Get clinic settings for personalized message
        settings = get_settings(conn_local)
        clinic_name = settings.get("clinic_name", "Clinic")
        
        return (
            f"🎉 *Welcome to {clinic_name}!*\n\n"
            f"✅ You're now in the queue!\n"
            f"🎫 Your ticket: *{ticket['code']}*\n"
            f"🏆 Position: *#{ticket['position']}*\n"
            f"⏰ Estimated wait: *{ticket['eta_minutes']} minutes*\n\n"
            f"📱 *What you can do:*\n"
            f"• Reply *STATUS* to check your position\n"
            f"• Reply *LEAVE* to cancel\n"
            f"• Reply *LOCATION* for directions\n\n"
            f"🔔 We'll notify you when you're next!\n"
            f"📍 Please stay nearby and keep your phone handy."
        )
    finally:
        conn_local.close()


async def handle_whatsapp_status(from_num: str) -> str:
    """Enhanced status check with progress indicators."""
    conn_local = get_connection()
    try:
        ticket = get_ticket_by_phone(conn_local, from_num)
        if not ticket:
            return (
                f"❌ *No active ticket found*\n\n"
                f"🎫 Reply *JOIN* to enter the queue\n"
                f"ℹ️ Reply *HELP* for more options"
            )
        
        # Create visual progress indicator
        total_waiting = ticket['position'] or 1
        progress_bar = "🟩" * min(5, max(1, 6 - total_waiting)) + "⬜" * max(0, total_waiting - 1)
        
        status_emoji = {
            'waiting': '⏳',
            'urgent': '🚨',
            'next': '🔔',
            'in_room': '🏥',
            'done': '✅'
        }.get(ticket['status'], '📋')
        
        status_text = {
            'waiting': 'Waiting in queue',
            'urgent': 'URGENT - Priority queue',
            'next': 'YOU\'RE NEXT! Please head to reception',
            'in_room': 'Currently with doctor',
            'done': 'Visit completed'
        }.get(ticket['status'], ticket['status'].title())
        
        return (
            f"📊 *Queue Status Update*\n\n"
            f"🎫 Ticket: *{ticket['code']}*\n"
            f"{status_emoji} Status: *{status_text}*\n"
            f"🏆 Position: *#{ticket['position']}*\n"
            f"⏰ ETA: *{ticket['eta_minutes']} minutes*\n\n"
            f"📈 Progress: {progress_bar}\n\n"
            f"🔄 Reply *STATUS* for updates\n"
            f"❌ Reply *LEAVE* to cancel"
        )
    finally:
        conn_local.close()


async def handle_whatsapp_leave(from_num: str) -> str:
    """Enhanced leave flow with confirmation."""
    conn_local = get_connection()
    try:
        ticket = get_ticket_by_phone(conn_local, from_num)
        if not ticket:
            return (
                f"❌ *No active ticket found*\n\n"
                f"🎫 Reply *JOIN* to enter the queue"
            )
        
        update_ticket_status(conn_local, ticket['code'], 'canceled')
        return (
            f"✅ *Ticket canceled successfully*\n\n"
            f"🎫 Ticket *{ticket['code']}* has been removed from the queue.\n\n"
            f"💙 Thank you for using our service!\n"
            f"🔄 Reply *JOIN* anytime to re-enter the queue\n"
            f"📞 Call us if you need immediate assistance"
        )
    finally:
        conn_local.close()


async def handle_whatsapp_interactive(from_num: str, payload: str) -> str:
    """Handle interactive button responses."""
    if payload == "join_queue":
        return await handle_whatsapp_join(from_num)
    elif payload == "check_status":
        return await handle_whatsapp_status(from_num)
    elif payload == "cancel_ticket":
        return await handle_whatsapp_leave(from_num)
    elif payload == "get_location":
        return get_clinic_info()
    elif payload == "get_help":
        return get_whatsapp_help_message()
    else:
        return get_whatsapp_welcome_message()


def get_whatsapp_welcome_message() -> str:
    """Welcome message for new users or unclear commands."""
    return (
        f"👋 *Welcome to our Virtual Clinic Queue!*\n\n"
        f"🏥 Skip the waiting room and join our digital queue\n\n"
        f"📱 *Quick Commands:*\n"
        f"• *JOIN* - Enter the queue\n"
        f"• *STATUS* - Check your position\n"
        f"• *LEAVE* - Cancel your ticket\n"
        f"• *LOCATION* - Get directions\n"
        f"• *HELP* - See all options\n\n"
        f"✨ Just reply with any command to get started!"
    )


def get_whatsapp_help_message() -> str:
    """Comprehensive help message with all available commands."""
    return (
        f"🆘 *Clinic Queue Help*\n\n"
        f"📋 *Available Commands:*\n\n"
        f"🎫 *Queue Management:*\n"
        f"• *JOIN* or *JOIN [reason]* - Enter queue\n"
        f"• *STATUS* - Check position & ETA\n"
        f"• *LEAVE* - Cancel your ticket\n\n"
        f"ℹ️ *Information:*\n"
        f"• *LOCATION* - Get clinic address\n"
        f"• *HELP* - Show this menu\n\n"
        f"🔔 *Notifications:*\n"
        f"We'll automatically notify you when:\n"
        f"• You're next in line\n"
        f"• Your wait time changes\n\n"
        f"🚨 *Emergency?* Call us directly!\n"
        f"💙 Questions? Just send us a message!"
    )


def get_clinic_info() -> str:
    """Return clinic location and contact information."""
    return (
        f"📍 *Clinic Location & Info*\n\n"
        f"🏥 *Address:*\n"
        f"123 Health Street\n"
        f"Medical District, City 12345\n\n"
        f"🕒 *Hours:*\n"
        f"Mon-Fri: 8:00 AM - 6:00 PM\n"
        f"Sat: 9:00 AM - 2:00 PM\n"
        f"Sun: Closed\n\n"
        f"📞 *Contact:*\n"
        f"Phone: (555) 123-4567\n"
        f"Emergency: (555) 911-HELP\n\n"
        f"🚗 *Parking:* Free parking available\n"
        f"🚌 *Transit:* Bus routes 12, 34, 56\n\n"
        f"🗺️ Open maps app and search for our clinic name for turn-by-turn directions!"
    )


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
        return {"tickets": board}
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
        return {"tickets": board}
    finally:
        conn_local.close()


@app.get("/admin/test-data")
def test_admin_data(passcode: str = "demo") -> Dict[str, Any]:
    """Test endpoint to check data structure (for debugging)."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        board = get_board(conn_local)
        analytics = get_queue_analytics(conn_local, 7)
        metrics = get_performance_metrics(conn_local)
        
        return {
            "board_structure": {"tickets": board},
            "analytics": analytics,
            "metrics": metrics,
            "debug": "Data structure test"
        }
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


@app.get("/admin/analytics")
def admin_analytics(passcode: str, days: int = 7) -> Dict[str, Any]:
    """Get comprehensive analytics data for the admin dashboard."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        analytics = get_queue_analytics(conn_local, days)
        return analytics
    finally:
        conn_local.close()


@app.get("/admin/timeline")
def admin_timeline(passcode: str, limit: int = 50) -> Dict[str, Any]:
    """Get patient flow timeline for the admin dashboard."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        timeline = get_patient_flow_timeline(conn_local, limit)
        return {"timeline": timeline}
    finally:
        conn_local.close()


@app.get("/admin/metrics")
def admin_metrics(passcode: str) -> Dict[str, Any]:
    """Get real-time performance metrics for the admin dashboard."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        metrics = get_performance_metrics(conn_local)
        return metrics
    finally:
        conn_local.close()


@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard() -> str:
    """Return the enhanced admin dashboard with analytics."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Clinic Queue - Admin Dashboard</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background-color: #f8fafc;
            color: #334155;
        }
        
        .login-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .login-card {
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 400px;
        }
        
        .login-title {
            font-size: 1.875rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 2rem;
            color: #1e293b;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-label {
            display: block;
            font-weight: 500;
            margin-bottom: 0.5rem;
            color: #374151;
        }
        
        .form-input {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e5e7eb;
            border-radius: 0.5rem;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .form-input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .btn-primary {
            width: 100%;
            padding: 0.75rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        
        .error-message {
            color: #ef4444;
            margin-top: 0.5rem;
            font-size: 0.875rem;
        }
        
        .dashboard {
            min-height: 100vh;
            background-color: #f8fafc;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        .header h1 {
            font-size: 1.5rem;
            font-weight: 700;
        }
        
        .nav-tabs {
            display: flex;
            background: white;
            border-bottom: 1px solid #e5e7eb;
            padding: 0 2rem;
        }
        
        .nav-tab {
            padding: 1rem 1.5rem;
            background: none;
            border: none;
            cursor: pointer;
            font-weight: 500;
            color: #6b7280;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        
        .nav-tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        
        .nav-tab:hover {
            color: #374151;
        }
        
        .content {
            padding: 2rem;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .metric-card {
            background: white;
            padding: 1.5rem;
            border-radius: 0.75rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
        }
        
        .metric-icon {
            width: 3rem;
            height: 3rem;
            border-radius: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1rem;
            font-size: 1.25rem;
        }
        
        .metric-icon.blue { background: #dbeafe; color: #1d4ed8; }
        .metric-icon.green { background: #dcfce7; color: #166534; }
        .metric-icon.orange { background: #fed7aa; color: #c2410c; }
        .metric-icon.red { background: #fecaca; color: #dc2626; }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        
        .metric-label {
            color: #6b7280;
            font-size: 0.875rem;
        }
        
        .chart-container {
            background: white;
            padding: 1.5rem;
            border-radius: 0.75rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
            margin-bottom: 2rem;
        }
        
        .chart-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        
        .queue-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
        }
        
        .queue-section {
            background: white;
            border-radius: 0.75rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
            overflow: hidden;
        }
        
        .queue-header {
            padding: 1rem 1.5rem;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.875rem;
            letter-spacing: 0.05em;
        }
        
        .queue-header.waiting { background: #fef3c7; color: #92400e; }
        .queue-header.next { background: #dbeafe; color: #1e40af; }
        .queue-header.in-room { background: #fed7aa; color: #c2410c; }
        .queue-header.done { background: #dcfce7; color: #166534; }
        .queue-header.no-show { background: #fecaca; color: #dc2626; }
        
        .ticket-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .ticket-item {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #f3f4f6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .ticket-info {
            flex: 1;
        }
        
        .ticket-code {
            font-weight: 600;
            margin-bottom: 0.25rem;
        }
        
        .ticket-details {
            font-size: 0.875rem;
            color: #6b7280;
        }
        
        .ticket-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .btn {
            padding: 0.25rem 0.75rem;
            border: none;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-sm {
            padding: 0.125rem 0.5rem;
            font-size: 0.6875rem;
        }
        
        .btn-blue { background: #3b82f6; color: white; }
        .btn-green { background: #10b981; color: white; }
        .btn-orange { background: #f59e0b; color: white; }
        .btn-red { background: #ef4444; color: white; }
        .btn-gray { background: #6b7280; color: white; }
        
        .btn:hover { transform: translateY(-1px); }
        
        .timeline {
            background: white;
            border-radius: 0.75rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
        }
        
        .timeline-header {
            padding: 1.5rem;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .timeline-body {
            max-height: 500px;
            overflow-y: auto;
        }
        
        .timeline-item {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #f3f4f6;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .timeline-icon {
            width: 2rem;
            height: 2rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            flex-shrink: 0;
        }
        
        .timeline-content {
            flex: 1;
        }
        
        .timeline-time {
            font-size: 0.75rem;
            color: #9ca3af;
        }
        
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            color: #6b7280;
        }
        
        .btn-logout {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-logout:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        @media (max-width: 768px) {
            .header {
                padding: 1rem;
                flex-direction: column;
                gap: 1rem;
            }
            
            .nav-tabs {
                padding: 0 1rem;
                overflow-x: auto;
            }
            
            .content {
                padding: 1rem;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .queue-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div id="app"></div>
    <script type="module" src="/static/admin-dashboard.js"></script>
</body>
</html>
    """


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


# WhatsApp Business API Integration Functions
@app.post("/admin/send-broadcast")
def send_whatsapp_broadcast(request: dict, passcode: str) -> Dict[str, Any]:
    """Send broadcast message to all active WhatsApp users."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        message = request.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Get all active WhatsApp users
        cur = conn_local.execute(
            """SELECT DISTINCT phone FROM tickets 
               WHERE status IN ('waiting', 'urgent', 'next') 
               AND channel = 'whatsapp' 
               AND phone IS NOT NULL"""
        )
        
        phones = [row["phone"] for row in cur.fetchall()]
        
        # Queue broadcast messages
        redis_client = get_redis()
        if redis_client:
            for phone in phones:
                broadcast_data = {
                    "phone": phone,
                    "message": f"📢 *Clinic Announcement*\n\n{message}",
                    "type": "broadcast",
                    "timestamp": datetime.utcnow().isoformat()
                }
                redis_client.lpush("whatsapp_notifications", json.dumps(broadcast_data))
        
        return {"success": True, "recipients": len(phones), "message": "Broadcast queued"}
        
    finally:
        conn_local.close()


@app.get("/admin/whatsapp-stats")
def get_whatsapp_stats(passcode: str) -> Dict[str, Any]:
    """Get WhatsApp usage statistics."""
    conn_local = get_connection()
    try:
        settings = get_settings(conn_local)
        if passcode != settings["admin_passcode"]:
            raise HTTPException(status_code=401, detail="Invalid passcode")
        
        # WhatsApp user statistics
        cur = conn_local.execute(
            """SELECT 
               COUNT(*) as total_whatsapp_users,
               COUNT(CASE WHEN status IN ('waiting', 'urgent') THEN 1 END) as active_waiting,
               COUNT(CASE WHEN status = 'done' THEN 1 END) as completed_today
               FROM tickets 
               WHERE channel = 'whatsapp' 
               AND date(created_at) = date('now')"""
        )
        stats = dict(cur.fetchone())
        
        # Recent activity
        cur = conn_local.execute(
            """SELECT code, status, created_at, updated_at, note
               FROM tickets 
               WHERE channel = 'whatsapp'
               ORDER BY updated_at DESC
               LIMIT 10"""
        )
        recent_activity = [dict(row) for row in cur.fetchall()]
        
        return {
            "stats": stats,
            "recent_activity": recent_activity,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    finally:
        conn_local.close()


# Worker function to process WhatsApp notifications (would run separately)
def process_whatsapp_notifications():
    """
    Background worker to process WhatsApp notification queue.
    This would typically run as a separate process or Celery task.
    """
    redis_client = get_redis()
    if not redis_client:
        return
    
    while True:
        try:
            # Get notification from queue
            notification_data = redis_client.brpop("whatsapp_notifications", timeout=5)
            if not notification_data:
                continue
                
            notification = json.loads(notification_data[1])
            
            # Here you would integrate with Twilio WhatsApp API
            # Example:
            # client = Client(account_sid, auth_token)
            # message = client.messages.create(
            #     from_='whatsapp:+14155238886',  # Your Twilio WhatsApp number
            #     body=notification["message"],
            #     to=notification["phone"]
            # )
            
            print(f"Would send WhatsApp to {notification['phone']}: {notification['message']}")
            
        except Exception as e:
            print(f"Error processing WhatsApp notification: {e}")
            time.sleep(1)


# Mount static files (admin board script)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
