"""Database models for the clinic queue.

We use SQLModel to define the schema.  The database stores tickets and
settings.  Tickets represent patients waiting in the queue.  Settings
holds clinic‑level configuration such as the rolling average service time,
whether the queue is open, and the admin passcode.  Events are stored
to provide an audit trail.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class TicketStatus(str, Enum):
    """Possible statuses for a ticket."""

    waiting = "waiting"
    next = "next"
    in_room = "in_room"
    done = "done"
    no_show = "no_show"
    canceled = "canceled"
    urgent = "urgent"


class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    status: TicketStatus = Field(default=TicketStatus.waiting)
    phone: Optional[str] = Field(default=None, index=True)
    note: Optional[str] = None
    position: Optional[int] = Field(default=None, index=True)
    eta_minutes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    channel: str = Field(default="sms")  # sms, whatsapp, kiosk


class EventType(str, Enum):
    joined = "joined"
    promoted = "promoted"
    done = "done"
    no_show = "no_show"
    canceled = "canceled"
    notified_next = "notified_next"


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    event_type: EventType
    at: datetime = Field(default_factory=datetime.utcnow)


class Settings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    avg_service_minutes: float = Field(default=12.0)
    open: bool = Field(default=True)
    admin_passcode: str = Field(default="demo")
    clinic_name: str = Field(default="Clinic Queue")
