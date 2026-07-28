from __future__ import annotations

from pydantic import BaseModel, Field


class MockMessageIn(BaseModel):
    phone: str
    text: str = ""


class MockSelectIn(BaseModel):
    phone: str
    action: str


class DirectionPreviewIn(BaseModel):
    phone: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    travel_mode: str = "driving"


class NearbyPreviewIn(BaseModel):
    phone: str
    category: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meters: int = Field(default=1500, gt=0, le=50000)


class WebhookPayload(BaseModel):
    entry: list[dict] = []
