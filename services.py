"""Database and business logic using PostgreSQL.

This module provides helper functions to manage the queue using PostgreSQL
via psycopg2. All operations accept a psycopg2 connection instance.
"""

from __future__ import annotations

import os
import psycopg2
import psycopg2.extras
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://checking_owner:npg_MdnKY0Gh1amc@ep-super-scene-a51ij7h2-pooler.us-east-2.aws.neon.tech/checking?sslmode=require&channel_binding=require")
REDIS_URL = os.getenv("REDIS_URL")

# Global Redis client
_redis_client = None

def get_redis():
    """Get Redis client, return None if unavailable."""
    global _redis_client
    
    if not REDIS_AVAILABLE or not REDIS_URL:
        return None
    
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            _redis_client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}")
            _redis_client = None
    
    return _redis_client


def get_connection():
    """Return a PostgreSQL connection with RealDictCursor."""
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print(f"🔗 DATABASE_URL: {DATABASE_URL[:50]}...")
        raise


def init_db(conn) -> None:
    """Create tables if they do not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                admin_passcode TEXT,
                avg_service_minutes INTEGER DEFAULT 12
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                phone TEXT,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'called', 'served', 'no_show', 'canceled')),
                position INTEGER,
                eta_minutes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                channel TEXT DEFAULT 'sms' CHECK (channel IN ('sms', 'whatsapp', 'kiosk'))
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Insert default settings if not exists
        cur.execute("""
            INSERT INTO settings (id, admin_passcode, avg_service_minutes)
            VALUES (1, 'demo', 12)
            ON CONFLICT (id) DO NOTHING;
        """)
        
    conn.commit()


def get_settings(conn) -> Dict[str, Any]:
    """Get application settings."""
    # Try Redis cache first
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get("settings")
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Redis cache read error: {e}")
    
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM settings WHERE id = 1")
        row = cur.fetchone()
        
        if row:
            settings_data = dict(row)
            # Cache in Redis for 5 minutes
            cache_settings(settings_data)
            return settings_data
        else:
            # Default settings
            default_settings = {"admin_passcode": "demo", "avg_service_minutes": 12}
            cache_settings(default_settings)
            return default_settings


def set_admin_pass(conn, new_pass: str) -> None:
    """Set the admin passcode."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO settings (id, admin_passcode, avg_service_minutes)
            VALUES (1, %s, 12)
            ON CONFLICT (id) DO UPDATE SET admin_passcode = EXCLUDED.admin_passcode;
        """, (new_pass,))
    conn.commit()
    
    # Clear cache
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.delete("settings")
        except Exception:
            pass


def recompute_positions_and_etas(conn) -> None:
    """Recompute position and ETA for all waiting tickets."""
    settings = get_settings(conn)
    avg_service = settings.get("avg_service_minutes", 12)
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM tickets 
            WHERE status = 'waiting' 
            ORDER BY created_at
        """)
        waiting_tickets = cur.fetchall()
        
        for idx, ticket in enumerate(waiting_tickets, 1):
            eta = int(idx * avg_service)
            cur.execute("""
                UPDATE tickets 
                SET position = %s, eta_minutes = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (idx, eta, ticket['id']))
    
    conn.commit()


def generate_code() -> str:
    """Generate a unique ticket code."""
    ts = int(datetime.utcnow().timestamp())
    return f"Q{ts % 10000:04d}"


def create_ticket(conn, phone: Optional[str], note: Optional[str], channel: str) -> Dict[str, Any]:
    """Create a new ticket."""
    code = generate_code()
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tickets (code, phone, note, status, channel, created_at, updated_at)
            VALUES (%s, %s, %s, 'waiting', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING *
        """, (code, phone, note, channel))
        
        ticket = cur.fetchone()
    
    conn.commit()
    
    # Recompute positions for all waiting tickets
    recompute_positions_and_etas(conn)
    
    # Get updated ticket with position/ETA
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM tickets WHERE code = %s", (code,))
        updated_ticket = cur.fetchone()
    
    # Clear board cache and publish update
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.delete("board_data")
            publish_board_update()
        except Exception:
            pass
    
    return dict(updated_ticket)


def update_ticket_status(conn, code: str, new_status: str) -> bool:
    """Update ticket status."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tickets 
            SET status = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE code = %s
        """, (new_status, code))
        
        if cur.rowcount == 0:
            return False
    
    conn.commit()
    
    # Recompute positions for remaining waiting tickets
    recompute_positions_and_etas(conn)
    
    # Clear board cache and publish update
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.delete("board_data")
            publish_board_update()
        except Exception:
            pass
    
    return True


def get_board(conn) -> Dict[str, Any]:
    """Get the current board data (cached)."""
    # Try Redis cache first
    cached_board = get_cached_board()
    if cached_board:
        return cached_board
    
    with conn.cursor() as cur:
        # Get waiting tickets
        cur.execute("""
            SELECT * FROM tickets 
            WHERE status = 'waiting' 
            ORDER BY created_at
        """)
        waiting = [dict(row) for row in cur.fetchall()]
        
        # Get recently called tickets
        cur.execute("""
            SELECT * FROM tickets 
            WHERE status IN ('called', 'served') 
            ORDER BY updated_at DESC 
            LIMIT 5
        """)
        recent = [dict(row) for row in cur.fetchall()]
    
    board_data = {
        "waiting": waiting,
        "recent": recent,
        "stats": {
            "waiting_count": len(waiting),
            "avg_wait": get_settings(conn).get("avg_service_minutes", 12)
        }
    }
    
    # Cache and publish
    cache_board_data(board_data)
    
    return board_data


def get_ticket_by_phone(conn, phone: str) -> Optional[Dict[str, Any]]:
    """Get active ticket by phone number."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM tickets 
            WHERE phone = %s AND status = 'waiting' 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (phone,))
        
        row = cur.fetchone()
        return dict(row) if row else None


def check_rate_limit(phone: str, action: str = "sms", limit: int = 5, window: int = 300) -> bool:
    """Check if phone number is rate limited. Returns True if allowed, False if rate limited."""
    redis_client = get_redis()
    if not redis_client:
        return True  # Allow if Redis unavailable
    
    try:
        key = f"rate_limit:{action}:{phone}"
        current = redis_client.get(key)
        
        if current is None:
            # First request - set counter
            redis_client.setex(key, window, 1)
            return True
        elif int(current) < limit:
            # Under limit - increment
            redis_client.incr(key)
            return True
        else:
            # Over limit
            return False
    except Exception as e:
        print(f"Redis rate limit error: {e}")
        return True  # Allow if error


def cache_settings(settings_data: Dict[str, Any]) -> None:
    """Cache settings in Redis with 5 minute TTL."""
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.setex("settings", 300, json.dumps(settings_data))
        except Exception as e:
            print(f"Redis cache write error: {e}")


def get_cached_settings() -> Optional[Dict[str, Any]]:
    """Get cached settings from Redis."""
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get("settings")
            return json.loads(cached) if cached else None
        except Exception:
            return None
    return None


def cache_board_data(board_data: Dict[str, Any]) -> None:
    """Cache board data in Redis with 1 minute TTL."""
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.setex("board_data", 60, json.dumps(board_data, default=str))
        except Exception as e:
            print(f"Redis board cache error: {e}")


def get_cached_board() -> Optional[Dict[str, Any]]:
    """Get cached board data from Redis."""
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get("board_data")
            return json.loads(cached) if cached else None
        except Exception:
            return None
    return None


def publish_board_update() -> None:
    """Publish board update to Redis pub/sub for real-time updates."""
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.publish("board_updates", json.dumps({"event": "update", "timestamp": datetime.utcnow().isoformat()}))
        except Exception as e:
            print(f"Redis publish error: {e}")