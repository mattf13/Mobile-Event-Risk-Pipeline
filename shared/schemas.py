"""Shared data schemas for the Mobile Event Risk Pipeline."""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class MobileEvent(BaseModel):
    """Schema for incoming mobile application events."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    event_type: str  # login, transaction, location_ping, screen_view
    amount: Optional[float] = 0.0
    device_id: str
    location: str  # Format: "lat,lon"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskScore(BaseModel):
    """Schema for the results of the risk analysis process."""

    event_id: str
    score: int  # Range: 0-100
    label: str  # GREEN, YELLOW, RED
    rationale: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
