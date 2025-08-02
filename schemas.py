"""Pydantic schemas for requests.

We define only the request body for admin actions here.  Responses are
returned as plain dicts directly from the service layer.
"""
from typing import Optional

from pydantic import BaseModel


class ActionRequest(BaseModel):
    passcode: str
    action: str
    code: str
    note: Optional[str] = None
