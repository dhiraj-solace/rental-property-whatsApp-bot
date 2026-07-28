from __future__ import annotations

import logging
import os
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .schemas import DirectionPreviewIn, MockMessageIn, MockSelectIn, NearbyPreviewIn
from .services import (
    DEMO_DATA_PATH,
    MENU_OPTIONS,
    PREDEFINED_MESSAGE,
    directions_response,
    guest_context,
    load_demo_data,
    menu_payload,
    mock_action_response,
    nearby_places_response,
    normalize_phone,
    process_whatsapp_webhook_payload,
    receive_mock_message,
    whatsapp_provider,
)


DEFAULT_VERIFY_TOKEN = "dev_verify_token"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("guest_assistant.api")

app = FastAPI(title="WhatsApp Guest Assistant POC", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "name": "WhatsApp Guest Assistant POC",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "mock_menu": "/api/mock-whatsapp/menu?phone=919999000001",
    }


@app.get("/health")
def health() -> dict:
    data = load_demo_data()
    return {
        "status": "ok",
        "assistant": "guest_assistant",
        "ai_enabled": False,
        "reply_style": "rule_based_random_templates",
        "whatsapp_provider": whatsapp_provider(),
        "demo_data_path": str(DEMO_DATA_PATH),
        "properties": len(data.get("properties", [])),
        "confirmed_bookings": len([item for item in data.get("bookings", []) if item.get("status") == "confirmed"]),
        "google_maps_configured": bool(os.getenv("GOOGLE_MAPS_API_KEY", "").strip()),
    }


@app.get("/webhook/whatsapp", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> str:
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", DEFAULT_VERIFY_TOKEN)
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("webhook_verify status=success")
        return hub_challenge
    logger.warning("webhook_verify status=failed mode=%s", hub_mode)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook/whatsapp")
async def receive_webhook(request: Request) -> dict:
    payload = await request.json()
    logger.info("webhook_received entries=%s", len(payload.get("entry") or []))
    results = process_whatsapp_webhook_payload(payload)
    return {"ok": True, "processed": results}


@app.get("/api/mock-whatsapp/menu")
def get_mock_menu(phone: str = "") -> dict:
    return menu_payload(phone)


@app.post("/api/mock-whatsapp/message")
def receive_mock_whatsapp_message(payload: MockMessageIn) -> dict:
    return receive_mock_message(payload.phone, payload.text)


@app.post("/api/mock-whatsapp/select")
def select_mock_option(payload: MockSelectIn) -> dict:
    return mock_action_response(payload.phone, payload.action)


@app.get("/api/guest/profile")
def guest_profile(phone: str) -> dict:
    context = guest_context(phone)
    if not context:
        return {"known_guest": False, "phone": normalize_phone(phone)}
    return {
        "known_guest": True,
        "phone": normalize_phone(phone),
        "booking": context["booking"],
        "property": context["property"],
        "available_actions": [{"id": key, "title": title} for key, title in MENU_OPTIONS.items()],
    }


@app.post("/api/directions/preview")
def directions_preview(payload: DirectionPreviewIn) -> dict:
    return directions_response(
        payload.phone,
        payload.latitude,
        payload.longitude,
        payload.travel_mode,
    )


@app.post("/api/nearby/preview")
def nearby_preview(payload: NearbyPreviewIn) -> dict:
    return nearby_places_response(
        payload.phone,
        payload.category,
        payload.latitude,
        payload.longitude,
        payload.radius_meters,
    )


@app.get("/api/entry-point")
def entry_point(phone: str = "") -> dict:
    normalized = normalize_phone(phone)
    encoded = quote(PREDEFINED_MESSAGE)
    return {
        "predefined_message": PREDEFINED_MESSAGE,
        "whatsapp_link": f"https://wa.me/{normalized}?text={encoded}" if normalized else f"https://wa.me/?text={encoded}",
        "qr_note": "Use this WhatsApp link in a QR generator for the guest assistant demo.",
    }
