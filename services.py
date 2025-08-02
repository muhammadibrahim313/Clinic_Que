"""Database and business logic using sqlite3.

This module provides helper functions to manage the queue, using the
built‑in `sqlite3` library so that no external database driver is
required.  All operations accept a `sqlite3.Connection` instance.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# Determine the path to the SQLite file.  If DATABASE_URL is provided and
# starts with a supported scheme, it will be used as‑is; otherwise, default
# to a file named ``queue.db`` located in the same directory as this module.
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_FILENAME = os.path.join(PROJECT_DIR, "queue.db")

DB_PATH = os.getenv("DATABASE_URL", DEFAULT_DB_FILENAME)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection.  Ensures foreign keys are enabled."""
    # If a full URL is provided (e.g., postgresql), ignore and fallback to SQLite.
    if DB_PATH.startswith("postgres"):
        # Postgres not supported in this fallback.
        raise RuntimeError("PostgreSQL is not supported in this environment")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist."""
    conn.executescript(
        """
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
        """
    )
    conn.commit()


def get_settings(conn: sqlite3.Connection) -> sqlite3.Row:
    cur = conn.execute("SELECT * FROM settings WHERE id = 1")
    return cur.fetchone()


def set_admin_pass(conn: sqlite3.Connection, passcode: str) -> None:
    conn.execute("UPDATE settings SET admin_passcode = ? WHERE id = 1", (passcode,))
    conn.commit()


def recompute_positions_and_etas(conn: sqlite3.Connection) -> None:
    """Recalculate positions and ETAs for waiting and urgent tickets."""
    settings = get_settings(conn)
    avg_service = settings["avg_service_minutes"] or 12.0
    # Fetch waiting and urgent tickets ordered by created_at
    cur = conn.execute(
        "SELECT id, status FROM tickets WHERE status IN ('waiting','urgent') ORDER BY datetime(created_at)"
    )
    rows = cur.fetchall()
    ordered: List[Tuple[int, str]] = []
    # urgent first, preserve order
    urgent = [r for r in rows if r["status"] == "urgent"]
    normal = [r for r in rows if r["status"] == "waiting"]
    ordered = urgent + normal
    for idx, row in enumerate(ordered, start=1):
        eta = int(idx * avg_service)
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET position = ?, eta_minutes = ?, updated_at = ? WHERE id = ?",
            (idx, eta, now, row["id"]),
        )
    conn.commit()


def generate_code() -> str:
    ts = int(datetime.utcnow().timestamp())
    return f"Q{ts % 10000:04d}"


def create_ticket(conn: sqlite3.Connection, phone: Optional[str], note: Optional[str], channel: str) -> sqlite3.Row:
    code = generate_code()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO tickets (code, phone, note, status, position, eta_minutes, created_at, updated_at, channel)"
        " VALUES (?, ?, ?, 'waiting', NULL, NULL, ?, ?, ?)",
        (code, phone, note, now, now, channel),
    )
    conn.commit()
    recompute_positions_and_etas(conn)
    # Insert event
    cur = conn.execute("SELECT id FROM tickets WHERE code = ?", (code,))
    tid = cur.fetchone()["id"]
    conn.execute(
        "INSERT INTO events (ticket_id, event_type, at) VALUES (?, 'joined', ?)",
        (tid, now),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM tickets WHERE id = ?", (tid,))
    return cur.fetchone()


def update_ticket_status(conn: sqlite3.Connection, code: str, new_status: str) -> Optional[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM tickets WHERE code = ?", (code,))
    ticket = cur.fetchone()
    if not ticket:
        return None
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE code = ?",
        (new_status, now, code),
    )
    conn.commit()
    # Insert event
    conn.execute(
        "INSERT INTO events (ticket_id, event_type, at) VALUES (?, ?, ?)",
        (ticket["id"], new_status, now),
    )
    conn.commit()
    recompute_positions_and_etas(conn)
    cur2 = conn.execute("SELECT * FROM tickets WHERE code = ?", (code,))
    return cur2.fetchone()


def get_board(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    statuses = ["waiting", "next", "in_room", "done", "no_show", "urgent"]
    board: Dict[str, List[Dict[str, Any]]] = {s: [] for s in statuses}
    cur = conn.execute("SELECT * FROM tickets ORDER BY datetime(created_at)")
    for row in cur.fetchall():
        ticket_dict = {
            "code": row["code"],
            "status": row["status"],
            "position": row["position"],
            "eta_minutes": row["eta_minutes"],
            "note": row["note"],
            "created_at": row["created_at"],
        }
        s = row["status"]
        if s not in board:
            board[s] = []
        board[s].append(ticket_dict)
    return board


def get_ticket_by_phone(conn: sqlite3.Connection, phone: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM tickets WHERE phone = ? AND status IN ('waiting','urgent') ORDER BY datetime(created_at) DESC",
        (phone,),
    )
    return cur.fetchone()