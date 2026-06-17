from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
import uuid


class MobileEvent(BaseModel):
    # Usiamo una lambda per generare un nuovo UUID ogni volta
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    event_type: str  # login, transaction, location_ping, screen_view
    amount: Optional[float] = 0.0
    device_id: str
    location: str  # formato "lat,lon"
    # Usiamo una lambda per ottenere il timestamp UTC corrente
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskScore(BaseModel):
    event_id: str
    score: int  # 0-100
    label: str  # GREEN, YELLOW, RED
    rationale: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
