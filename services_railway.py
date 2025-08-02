"""Database and business logic for Railway deployment.

This module provides helper functions to manage the queue, supporting both
SQLite (local development) and PostgreSQL (Railway production).
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

# Database imports
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

import sqlite3

# Redis imports
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_FILENAME = os.path.join(PROJECT_DIR, "queue.db")

# Redis connection
_redis_client = None

def get_redis() -> Optional[redis.Redis]:
    """Get Redis client if available and configured."""
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
    """Return database connection (PostgreSQL for Railway, SQLite for local)."""
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("PostgreSQL not available - install psycopg2-binary")
        
        # Railway PostgreSQL connection
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        # Local SQLite connection
        db_path = DATABASE_URL if DATABASE_URL else DEFAULT_DB_FILENAME
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def init_db(conn) -> None:
    """Create tables if they do not exist (works for both PostgreSQL and SQLite)."""
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        # PostgreSQL version
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    avg_service_minutes REAL DEFAULT 12.0,
                    open BOOLEAN DEFAULT true,
                    admin_passcode TEXT DEFAULT 'demo',
                    clinic_name TEXT DEFAULT 'Clinic Queue'
                );
                
                INSERT INTO settings (id, avg_service_minutes, open, admin_passcode, clinic_name) 
                VALUES (1, 12.0, true, 'demo', 'Clinic Queue') 
                ON CONFLICT (id) DO NOTHING;
                
                CREATE TABLE IF NOT EXISTS tickets (
                    id SERIAL PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'waiting',
                    phone TEXT,
                    note TEXT,
                    position INTEGER,
                    eta_minutes INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    channel TEXT NOT NULL DEFAULT 'sms'
                );
                
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    ticket_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
                );
            """)
    else:
        # SQLite version (for local development)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                avg_service_minutes REAL DEFAULT 12.0,
                open INTEGER DEFAULT 1,
                admin_passcode TEXT DEFAULT 'demo',
                clinic_name TEXT DEFAULT 'Clinic Queue'
            );
            INSERT OR IGNORE INTO settings (id) VALUES (1);

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'waiting',
                phone TEXT,
                note TEXT,
                position INTEGER,
                eta_minutes INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'sms'
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );
        """)
    
    conn.commit()


def get_settings(conn, use_cache: bool = True) -> Dict[str, Any]:
    # Try cache first
    if use_cache:
        cached_settings = get_cached_settings()
        if cached_settings:
            return cached_settings
    
    # Get from database
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM settings WHERE id = 1")
            settings_row = cur.fetchone()
    else:
        cur = conn.execute("SELECT * FROM settings WHERE id = 1")
        settings_row = cur.fetchone()
    
    if settings_row:
        settings_dict = dict(settings_row)
        cache_settings(settings_dict)
        return settings_dict
    
    return {}


def set_admin_pass(conn, passcode: str) -> None:
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor() as cur:
            cur.execute("UPDATE settings SET admin_passcode = %s WHERE id = 1", (passcode,))
    else:
        conn.execute("UPDATE settings SET admin_passcode = ? WHERE id = 1", (passcode,))
    conn.commit()


def recompute_positions_and_etas(conn) -> None:
    """Recalculate positions and ETAs for waiting and urgent tickets."""
    settings = get_settings(conn)
    avg_service = settings.get("avg_service_minutes", 12.0)
    
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, status FROM tickets 
                WHERE status IN ('waiting','urgent') 
                ORDER BY created_at
            """)
            rows = cur.fetchall()
            
            # urgent first, preserve order
            urgent = [r for r in rows if r["status"] == "urgent"]
            normal = [r for r in rows if r["status"] == "waiting"]
            ordered = urgent + normal
            
            for idx, row in enumerate(ordered, start=1):
                eta = int(idx * avg_service)
                cur.execute("""
                    UPDATE tickets 
                    SET position = %s, eta_minutes = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (idx, eta, row["id"]))
    else:
        cur = conn.execute("""
            SELECT id, status FROM tickets 
            WHERE status IN ('waiting','urgent') 
            ORDER BY datetime(created_at)
        """)
        rows = cur.fetchall()
        
        # urgent first, preserve order
        urgent = [r for r in rows if r["status"] == "urgent"]
        normal = [r for r in rows if r["status"] == "waiting"]
        ordered = urgent + normal
        
        for idx, row in enumerate(ordered, start=1):
            eta = int(idx * avg_service)
            now = datetime.utcnow().isoformat()
            conn.execute("""
                UPDATE tickets 
                SET position = ?, eta_minutes = ?, updated_at = ? 
                WHERE id = ?
            """, (idx, eta, now, row["id"]))
    
    conn.commit()


def generate_code() -> str:
    ts = int(datetime.utcnow().timestamp())
    return f"Q{ts % 10000:04d}"


def create_ticket(conn, phone: Optional[str], note: Optional[str], channel: str) -> Dict[str, Any]:
    code = generate_code()
    
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO tickets (code, phone, note, status, position, eta_minutes, channel)
                VALUES (%s, %s, %s, 'waiting', NULL, NULL, %s)
                RETURNING id
            """, (code, phone, note, channel))
            ticket_id = cur.fetchone()["id"]
    else:
        now = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT INTO tickets (code, phone, note, status, position, eta_minutes, created_at, updated_at, channel)
            VALUES (?, ?, ?, 'waiting', NULL, NULL, ?, ?, ?)
        """, (code, phone, note, now, now, channel))
        cur = conn.execute("SELECT id FROM tickets WHERE code = ?", (code,))
        ticket_id = cur.fetchone()["id"] if DATABASE_URL and DATABASE_URL.startswith("postgres") else cur.fetchone()[0]
    
    conn.commit()
    recompute_positions_and_etas(conn)
    
    # Insert event
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events (ticket_id, event_type, at) 
                VALUES (%s, 'joined', CURRENT_TIMESTAMP)
            """, (ticket_id,))
    else:
        now = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT INTO events (ticket_id, event_type, at) 
            VALUES (?, 'joined', ?)
        """, (ticket_id, now))
    
    conn.commit()
    
    # Return the created ticket
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
            return dict(cur.fetchone())
    else:
        cur = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        result = cur.fetchone()
        return dict(result) if result else {}


def update_ticket_status(conn, code: str, new_status: str) -> Optional[Dict[str, Any]]:
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tickets WHERE code = %s", (code,))
            ticket = cur.fetchone()
            
            if not ticket:
                return None
            
            cur.execute("""
                UPDATE tickets 
                SET status = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE code = %s
            """, (new_status, code))
            
            # Insert event
            cur.execute("""
                INSERT INTO events (ticket_id, event_type, at) 
                VALUES (%s, %s, CURRENT_TIMESTAMP)
            """, (ticket["id"], new_status))
    else:
        cur = conn.execute("SELECT * FROM tickets WHERE code = ?", (code,))
        ticket = cur.fetchone()
        
        if not ticket:
            return None
        
        now = datetime.utcnow().isoformat()
        conn.execute("""
            UPDATE tickets 
            SET status = ?, updated_at = ? 
            WHERE code = ?
        """, (new_status, now, code))
        
        # Insert event
        conn.execute("""
            INSERT INTO events (ticket_id, event_type, at) 
            VALUES (?, ?, ?)
        """, (ticket["id"], new_status, now))
    
    conn.commit()
    recompute_positions_and_etas(conn)
    
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tickets WHERE code = %s", (code,))
            result = cur.fetchone()
            return dict(result) if result else None
    else:
        cur = conn.execute("SELECT * FROM tickets WHERE code = ?", (code,))
        result = cur.fetchone()
        return dict(result) if result else None


def get_board(conn, use_cache: bool = True) -> Dict[str, List[Dict[str, Any]]]:
    # Try cache first
    if use_cache:
        cached_board = get_cached_board()
        if cached_board:
            return cached_board
    
    # Build from database
    statuses = ["waiting", "next", "in_room", "done", "no_show", "urgent"]
    board: Dict[str, List[Dict[str, Any]]] = {s: [] for s in statuses}
    
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tickets ORDER BY created_at")
            rows = cur.fetchall()
    else:
        cur = conn.execute("SELECT * FROM tickets ORDER BY datetime(created_at)")
        rows = cur.fetchall()
    
    for row in rows:
        ticket_dict = {
            "code": row["code"],
            "status": row["status"],
            "position": row["position"],
            "eta_minutes": row["eta_minutes"],
            "note": row["note"],
            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], 'isoformat') else row["created_at"],
        }
        s = row["status"]
        if s not in board:
            board[s] = []
        board[s].append(ticket_dict)
    
    # Cache and publish update
    cache_board_data({"tickets": board})
    publish_board_update({"tickets": board})
    
    return board


def get_ticket_by_phone(conn, phone: str) -> Optional[Dict[str, Any]]:
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM tickets 
                WHERE phone = %s AND status IN ('waiting','urgent') 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (phone,))
            result = cur.fetchone()
            return dict(result) if result else None
    else:
        cur = conn.execute("""
            SELECT * FROM tickets 
            WHERE phone = ? AND status IN ('waiting','urgent') 
            ORDER BY datetime(created_at) DESC
        """, (phone,))
        result = cur.fetchone()
        return dict(result) if result else None


# ===== REDIS HELPER FUNCTIONS =====

def cache_board_data(board_data: Dict[str, Any]) -> None:
    """Cache board data in Redis with 30 second TTL."""
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.setex("clinic:board", 30, json.dumps(board_data))
        except Exception as e:
            print(f"Redis cache error: {e}")


def get_cached_board() -> Optional[Dict[str, Any]]:
    """Get cached board data from Redis."""
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get("clinic:board")
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Redis get error: {e}")
    return None


def publish_board_update(board_data: Dict[str, Any]) -> None:
    """Publish board update to Redis channel for real-time updates."""
    redis_client = get_redis()
    if redis_client:
        try:
            redis_client.publish("clinic:updates", json.dumps({
                "type": "board_update",
                "data": board_data,
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            print(f"Redis publish error: {e}")


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
            redis_client.setex("clinic:settings", 300, json.dumps(settings_data))
        except Exception as e:
            print(f"Redis cache settings error: {e}")


def get_cached_settings() -> Optional[Dict[str, Any]]:
    """Get cached settings from Redis."""
    redis_client = get_redis()
    if redis_client:
        try:
            cached = redis_client.get("clinic:settings")
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Redis get settings error: {e}")
    return None