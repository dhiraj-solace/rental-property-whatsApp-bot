from __future__ import annotations

import json
import logging
import os
import random
import urllib.error
import urllib.parse
import urllib.request
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PREDEFINED_MESSAGE = "I need help with my stay."
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DEMO_DATA_PATH = Path(os.getenv("GUEST_ASSISTANT_DATA_PATH", str(DATA_DIR / "guest_assistant_demo.json")))
logger = logging.getLogger("guest_assistant.services")

MENU_OPTIONS = {
    "check_in": "Check-in and access",
    "wifi": "Wi-Fi details",
    "parking": "Parking",
    "facilities": "Apartment amenities",
    "nearby_places": "Live nearby places",
    "checkout": "Checkout instructions",
    "ai_support": "Silkhaus AI Concierge",
    "contact_host": "Contact support",
    "report_issue": "Report apartment issue",
    "directions": "Get directions",
}

NEARBY_CATEGORIES = {
    "grocery": {
        "label": "Grocery",
        "query": "grocery",
        "types": ["grocery_store", "supermarket", "convenience_store"],
    },
    "medical": {
        "label": "Medical",
        "query": "medical pharmacy",
        "types": ["pharmacy", "hospital", "doctor", "medical_clinic"],
    },
    "mall": {
        "label": "Mall",
        "query": "mall shopping",
        "types": ["shopping_mall"],
    },
}

TEXT_ALIASES = {
    "1": "check_in",
    "check in": "check_in",
    "check-in": "check_in",
    "checkin": "check_in",
    "2": "wifi",
    "wifi": "wifi",
    "wi-fi": "wifi",
    "internet": "wifi",
    "3": "parking",
    "parking": "parking",
    "4": "facilities",
    "facility": "facilities",
    "facilities": "facilities",
    "amenities": "facilities",
    "amenity": "facilities",
    "5": "nearby_places",
    "nearby": "nearby_places",
    "nearby places": "nearby_places",
    "places": "nearby_places",
    "restaurants": "nearby_places",
    "grocery": "nearby_category:grocery",
    "groceries": "nearby_category:grocery",
    "supermarket": "nearby_category:grocery",
    "medical": "nearby_category:medical",
    "medicine": "nearby_category:medical",
    "pharmacy": "nearby_category:medical",
    "hospital": "nearby_category:medical",
    "mall": "nearby_category:mall",
    "shopping": "nearby_category:mall",
    "shopping mall": "nearby_category:mall",
    "6": "checkout",
    "check out": "checkout",
    "check-out": "checkout",
    "checkout": "checkout",
    "7": "ai_support",
    "ai": "ai_support",
    "ai support": "ai_support",
    "ai concierge": "ai_support",
    "assistant": "ai_support",
    "concierge": "ai_support",
    "faq": "ai_support",
    "question": "ai_support",
    "ask question": "ai_support",
    "8": "contact_host",
    "host": "contact_host",
    "support": "contact_host",
    "contact": "contact_host",
    "contact host": "contact_host",
    "contact support": "contact_host",
    "9": "report_issue",
    "issue": "report_issue",
    "maintenance": "report_issue",
    "report issue": "report_issue",
    "apartment issue": "report_issue",
    "10": "directions",
    "direction": "directions",
    "directions": "directions",
    "location": "directions",
    "map": "directions",
    "maps": "directions",
}

_SESSIONS: dict[str, dict[str, Any]] = {}
_DEMO_CACHE: dict[str, Any] | None = None
_CURRENT_WHATSAPP_PHONE_NUMBER_ID: ContextVar[str | None] = ContextVar(
    "current_whatsapp_phone_number_id",
    default=None,
)


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_phone(phone: str | None) -> str:
    value = "".join(ch for ch in (phone or "") if ch.isdigit())
    return value or "0000000000"


def whatsapp_provider() -> str:
    return "meta"


def load_demo_data(force_reload: bool = False) -> dict[str, Any]:
    global _DEMO_CACHE
    if _DEMO_CACHE is not None and not force_reload:
        return _DEMO_CACHE
    with DEMO_DATA_PATH.open("r", encoding="utf-8") as handle:
        _DEMO_CACHE = json.load(handle)
    return _DEMO_CACHE


def brand_values() -> dict[str, str]:
    brand = load_demo_data().get("brand", {})
    return {
        "brand_name": brand.get("name", "Silkhaus"),
        "concierge_name": brand.get("concierge_name", "Silkhaus AI Concierge"),
        "support_phone": brand.get("support_phone", ""),
        "support_email": brand.get("support_email", ""),
    }


def clear_runtime_state() -> None:
    _SESSIONS.clear()


def send_whatsapp_text(to_phone: str, body: str) -> dict[str, Any]:
    to_phone = normalize_phone(to_phone)
    request_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": True, "body": body},
    }
    return send_whatsapp_payload(to_phone, request_body, body)


def send_whatsapp_buttons(
    to_phone: str,
    body: str,
    buttons: list[dict[str, str]],
) -> dict[str, Any]:
    to_phone = normalize_phone(to_phone)
    request_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": button["id"][:256],
                            "title": button["title"][:20],
                        },
                    }
                    for button in buttons[:3]
                ]
            },
        },
    }
    return send_whatsapp_payload(to_phone, request_body, body)


def send_whatsapp_list(
    to_phone: str,
    body: str,
    button_text: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    to_phone = normalize_phone(to_phone)
    request_body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body[:1024]},
            "action": {
                "button": button_text[:20],
                "sections": sections[:10],
            },
        },
    }
    return send_whatsapp_payload(to_phone, request_body, body)


def send_whatsapp_payload(
    to_phone: str,
    request_body: dict[str, Any],
    log_body: str,
) -> dict[str, Any]:
    provider = whatsapp_provider()
    logger.info("whatsapp_send_start provider=%s to=%s body_chars=%s", provider, to_phone, len(log_body))
    phone_number_id = (
        _CURRENT_WHATSAPP_PHONE_NUMBER_ID.get()
        or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    )
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    graph_version = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v20.0").strip() or "v20.0"
    logger.info(
        "whatsapp_send_sender phone_number_id=%s source=%s message_type=%s",
        phone_number_id or "missing",
        "webhook_metadata" if _CURRENT_WHATSAPP_PHONE_NUMBER_ID.get() else "env",
        request_body.get("type"),
    )
    if not phone_number_id or not access_token:
        logger.warning("whatsapp_send_meta_not_configured to=%s", to_phone)
        return {
            "delivery_status": "meta_not_configured",
            "provider_message_id": None,
            "request_body": request_body,
        }

    url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
    request = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("whatsapp_send_meta_http_error to=%s status=%s detail=%s", to_phone, exc.code, detail[:500])
        return {"delivery_status": f"meta_error_{exc.code}", "provider_message_id": None, "error": detail}
    except Exception as exc:
        logger.error("whatsapp_send_meta_error to=%s error=%s", to_phone, exc)
        return {"delivery_status": "meta_error", "provider_message_id": None, "error": str(exc)}

    message_id = None
    if data.get("messages"):
        message_id = data["messages"][0].get("id")
    return {"delivery_status": "meta_sent", "provider_message_id": message_id, "provider_response": data}


def find_booking(phone: str) -> dict[str, Any] | None:
    normalized = normalize_phone(phone)
    for booking in load_demo_data().get("bookings", []):
        if normalize_phone(booking.get("guest_phone")) == normalized and booking.get("status") == "confirmed":
            return dict(booking)
    return None


def property_for_booking(booking: dict[str, Any]) -> dict[str, Any]:
    property_id = booking.get("property_id")
    for item in load_demo_data().get("properties", []):
        if item.get("id") == property_id:
            return dict(item)
    raise KeyError(f"Demo property {property_id!r} was not found")


def guest_context(phone: str) -> dict[str, Any] | None:
    booking = find_booking(phone)
    if not booking:
        return None
    prop = property_for_booking(booking)
    context: dict[str, Any] = {
        "phone": normalize_phone(phone),
        **brand_values(),
        "guest_name": booking.get("guest_name", "Guest"),
        "booking_id": booking.get("booking_id", ""),
        "check_in_date": booking.get("check_in_date", ""),
        "check_out_date": booking.get("check_out_date", ""),
        "property_name": prop.get("name", ""),
        "property_address": prop.get("address", ""),
        "check_in_time": prop.get("check_in", {}).get("time", ""),
        "checkout_time": prop.get("checkout", {}).get("time", ""),
        "wifi_network": prop.get("wifi", {}).get("network", ""),
        "wifi_password": prop.get("wifi", {}).get("password", ""),
        "parking_summary": prop.get("parking", {}).get("summary", ""),
        "host_name": prop.get("host", {}).get("name", ""),
        "host_phone": prop.get("host", {}).get("phone", ""),
        "host_email": prop.get("host", {}).get("email", ""),
        "property_latitude": prop.get("location", {}).get("latitude"),
        "property_longitude": prop.get("location", {}).get("longitude"),
    }
    context["check_in_steps"] = "\n".join(f"- {step}" for step in prop.get("check_in", {}).get("steps", []))
    context["checkout_steps"] = "\n".join(f"- {step}" for step in prop.get("checkout", {}).get("steps", []))
    context["facilities"] = "\n".join(f"- {item}" for item in prop.get("facilities", []))
    return {"booking": booking, "property": prop, "values": context}


def pick_reply(intent: str, values: dict[str, Any] | None = None) -> str:
    templates = load_demo_data().get("response_templates", {})
    options = templates.get(intent) or templates.get("fallback") or ["How can I help with your stay?"]
    template = random.choice(options)
    return template.format_map(SafeFormatDict(values or {})).strip()


def menu_text(values: dict[str, Any]) -> str:
    rows = [f"{index}. {label}" for index, label in enumerate(MENU_OPTIONS.values(), start=1)]
    return pick_reply("welcome", values) + "\n\n" + "\n".join(rows)


def menu_sections() -> list[dict[str, Any]]:
    return [
        {
            "title": "Stay Info",
            "rows": [
                {"id": "check_in", "title": "Check-in access", "description": "Arrival and entry details"},
                {"id": "wifi", "title": "Wi-Fi details", "description": "Network and password"},
                {"id": "parking", "title": "Parking", "description": "Where to park"},
                {"id": "facilities", "title": "Apartment amenities", "description": "What is included"},
                {"id": "checkout", "title": "Checkout", "description": "Departure checklist"},
            ],
        },
        {
            "title": "Help",
            "rows": [
                {"id": "nearby_places", "title": "Nearby places", "description": "Grocery, medical or mall"},
                {"id": "ai_support", "title": "AI Concierge", "description": "Ask about your stay"},
                {"id": "contact_host", "title": "Contact support", "description": "Support phone and email"},
                {"id": "report_issue", "title": "Report issue", "description": "Send apartment issue"},
                {"id": "directions", "title": "Directions", "description": "Route to the apartment"},
            ],
        },
    ]


def send_guest_menu(phone: str, values: dict[str, Any]) -> dict[str, Any]:
    body = pick_reply("welcome", values)
    return send_whatsapp_list(phone, body, "Open menu", menu_sections())


def menu_payload(phone: str) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        values = {"phone": normalize_phone(phone), **brand_values()}
        return {
            "phone": values["phone"],
            "known_guest": False,
            "reply": pick_reply("unknown_guest", values),
            "options": [],
        }
    values = context["values"]
    return {
        "phone": values["phone"],
        "known_guest": True,
        "booking": context["booking"],
        "property": context["property"],
        "reply": menu_text(values),
        "options": [{"id": key, "title": label} for key, label in MENU_OPTIONS.items()],
    }


def remember_session(phone: str, **updates: Any) -> dict[str, Any]:
    normalized = normalize_phone(phone)
    session = _SESSIONS.setdefault(normalized, {"phone": normalized, "created_at": now_iso()})
    session.update(updates)
    session["updated_at"] = now_iso()
    return session


def get_session(phone: str) -> dict[str, Any]:
    return _SESSIONS.setdefault(normalize_phone(phone), {"phone": normalize_phone(phone), "created_at": now_iso()})


def resolve_intent(text: str) -> str | None:
    raw = text.strip()
    if raw in MENU_OPTIONS or raw.startswith("nearby_category:"):
        return raw
    cleaned = " ".join(text.strip().lower().replace("_", " ").split())
    if cleaned in TEXT_ALIASES:
        return TEXT_ALIASES[cleaned]
    if text in MENU_OPTIONS:
        return text
    for phrase, intent in TEXT_ALIASES.items():
        if len(phrase) > 2 and phrase in cleaned:
            return intent
    return None


def ai_support_examples() -> str:
    questions = load_demo_data().get("ai_support_questions", [])
    return "\n".join(f"- {item.get('question', '')}" for item in questions[:5])


def match_ai_support_question(text: str) -> dict[str, Any] | None:
    cleaned = " ".join(text.strip().lower().replace("?", " ").replace("_", " ").split())
    if not cleaned:
        return None

    best_match: dict[str, Any] | None = None
    best_score = 0
    for item in load_demo_data().get("ai_support_questions", []):
        score = 0
        question = " ".join(str(item.get("question", "")).lower().replace("?", " ").split())
        if question and question in cleaned:
            score += 100
        for keyword in item.get("keywords", []):
            normalized_keyword = " ".join(str(keyword).lower().replace("?", " ").split())
            if normalized_keyword and normalized_keyword in cleaned:
                score += max(1, len(normalized_keyword))
        if score > best_score:
            best_score = score
            best_match = item
    return best_match if best_score >= 4 else None


def start_ai_support_flow(phone: str, values: dict[str, Any]) -> dict[str, Any]:
    remember_session(phone, pending_action="ai_support")
    values = dict(values)
    values["ai_question_examples"] = ai_support_examples()
    reply = pick_reply("ai_support_prompt", values)
    delivery = send_whatsapp_text(phone, reply)
    return {"action": "ai_support_prompt", "reply": reply, "delivery": delivery}


def answer_ai_support_question(phone: str, text: str) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        reply = pick_reply("unknown_guest", {"phone": normalize_phone(phone), **brand_values()})
        delivery = send_whatsapp_text(phone, reply)
        return {"action": "unknown_guest", "reply": reply, "delivery": delivery}

    values = dict(context["values"])
    values["ai_question_examples"] = ai_support_examples()
    match = match_ai_support_question(text)
    if not match:
        remember_session(phone, pending_action="ai_support")
        reply = pick_reply("ai_support_unknown", values)
        delivery = send_whatsapp_text(phone, reply)
        return {"action": "ai_support_unknown", "reply": reply, "delivery": delivery}

    answer_template = random.choice(match.get("answers") or ["I can help with that from your Silkhaus booking details."])
    values["ai_question"] = match.get("question", text)
    values["ai_answer"] = answer_template.format_map(SafeFormatDict(values)).strip()
    remember_session(phone, pending_action="ai_support", last_ai_question=match.get("id"))
    reply = pick_reply("ai_support_answer", values)
    delivery = send_whatsapp_text(phone, reply)
    return {
        "action": "ai_support_answer",
        "question_id": match.get("id"),
        "reply": reply,
        "delivery": delivery,
    }


def start_directions_flow(phone: str, values: dict[str, Any]) -> dict[str, Any]:
    remember_session(phone, pending_action="directions")
    reply = pick_reply("directions_request_location", values)
    delivery = send_whatsapp_text(phone, reply)
    return {"action": "directions_request_location", "reply": reply, "delivery": delivery}


def directions_link(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> str:
    query = urllib.parse.urlencode(
        {
            "api": "1",
            "origin": f"{origin_lat},{origin_lng}",
            "destination": f"{dest_lat},{dest_lng}",
            "travelmode": "driving",
        }
    )
    return f"https://www.google.com/maps/dir/?{query}"


def maps_distance(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    travel_mode: str = "driving",
) -> dict[str, Any]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    link = directions_link(origin_lat, origin_lng, dest_lat, dest_lng)
    if not api_key:
        return {
            "configured": False,
            "distance_text": "Maps API key not configured",
            "duration_text": "Open the link for live directions",
            "maps_url": link,
        }

    query = urllib.parse.urlencode(
        {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "mode": travel_mode,
            "key": api_key,
        }
    )
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{query}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.error("google_maps_distance_error error=%s", exc)
        return {
            "configured": True,
            "distance_text": "Distance unavailable",
            "duration_text": "Open the link for live directions",
            "maps_url": link,
            "error": str(exc),
        }

    element = (((payload.get("rows") or [{}])[0].get("elements") or [{}])[0])
    if payload.get("status") != "OK" or element.get("status") != "OK":
        return {
            "configured": True,
            "distance_text": "Distance unavailable",
            "duration_text": "Open the link for live directions",
            "maps_url": link,
            "provider_response": payload,
        }

    return {
        "configured": True,
        "distance_text": element.get("distance", {}).get("text", "Distance unavailable"),
        "duration_text": element.get("duration", {}).get("text", "Time unavailable"),
        "maps_url": link,
        "provider_response": payload,
    }


def directions_response(
    phone: str,
    latitude: float,
    longitude: float,
    travel_mode: str = "driving",
) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        reply = pick_reply("unknown_guest", {"phone": normalize_phone(phone), **brand_values()})
        return {"action": "unknown_guest", "reply": reply}
    values = dict(context["values"])
    dest_lat = float(values["property_latitude"])
    dest_lng = float(values["property_longitude"])
    result = maps_distance(latitude, longitude, dest_lat, dest_lng, travel_mode)
    values.update(result)
    reply = pick_reply("directions_result", values)
    remember_session(phone, pending_action=None, last_location={"latitude": latitude, "longitude": longitude})
    delivery = send_whatsapp_text(phone, reply)
    return {"action": "directions_result", "reply": reply, "directions": result, "delivery": delivery}


def start_nearby_flow(phone: str, values: dict[str, Any]) -> dict[str, Any]:
    remember_session(phone, pending_action="live_nearby_category", nearby_category=None)
    reply = pick_reply("nearby_category_prompt", values)
    delivery = send_whatsapp_buttons(
        phone,
        reply,
        [
            {"id": "nearby_category:grocery", "title": "Grocery"},
            {"id": "nearby_category:medical", "title": "Medical"},
            {"id": "nearby_category:mall", "title": "Mall"},
        ],
    )
    return {"action": "nearby_category_prompt", "reply": reply, "delivery": delivery}


def normalize_nearby_category(value: str | None) -> str | None:
    cleaned = (value or "").strip().lower()
    if cleaned.startswith("nearby_category:"):
        cleaned = cleaned.split(":", 1)[1]
    cleaned = " ".join(cleaned.replace("_", " ").split())
    if cleaned in {"1", "grocery", "groceries", "supermarket", "store", "food store"}:
        return "grocery"
    if cleaned in {"2", "medical", "medicine", "pharmacy", "hospital", "doctor", "clinic"}:
        return "medical"
    if cleaned in {"3", "mall", "shopping", "shopping mall"}:
        return "mall"
    return None


def choose_nearby_category(phone: str, category: str) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        reply = pick_reply("unknown_guest", {"phone": normalize_phone(phone), **brand_values()})
        return {"action": "unknown_guest", "reply": reply}
    normalized_category = normalize_nearby_category(category)
    values = dict(context["values"])
    if not normalized_category:
        reply = pick_reply("nearby_category_invalid", values)
        send_whatsapp_text(phone, reply)
        return {"action": "nearby_category_invalid", "reply": reply}
    values["nearby_category"] = NEARBY_CATEGORIES[normalized_category]["label"]
    remember_session(phone, pending_action="live_nearby_location", nearby_category=normalized_category)
    reply = pick_reply("nearby_location_prompt", values)
    delivery = send_whatsapp_text(phone, reply)
    return {
        "action": "nearby_location_prompt",
        "category": normalized_category,
        "reply": reply,
        "delivery": delivery,
    }


def nearby_search_link(category: str, latitude: float, longitude: float) -> str:
    category_config = NEARBY_CATEGORIES[category]
    query = urllib.parse.urlencode(
        {
            "api": "1",
            "query": f"{category_config['query']} near {latitude},{longitude}",
        }
    )
    return f"https://www.google.com/maps/search/?{query}"


def search_live_nearby_places(
    category: str,
    latitude: float,
    longitude: float,
    radius_meters: int = 1500,
) -> dict[str, Any]:
    category = normalize_nearby_category(category) or "grocery"
    category_config = NEARBY_CATEGORIES[category]
    search_url = nearby_search_link(category, latitude, longitude)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return {
            "configured": False,
            "category": category,
            "category_label": category_config["label"],
            "places": [],
            "maps_search_url": search_url,
        }

    request_body = {
        "includedTypes": category_config["types"],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
        "rankPreference": "DISTANCE",
    }
    request = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchNearby",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.shortFormattedAddress,places.googleMapsUri,"
                "places.rating,places.location,places.primaryType"
            ),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("google_places_nearby_http_error status=%s detail=%s", exc.code, detail[:500])
        return {
            "configured": True,
            "category": category,
            "category_label": category_config["label"],
            "places": [],
            "maps_search_url": search_url,
            "error": detail,
        }
    except Exception as exc:
        logger.error("google_places_nearby_error error=%s", exc)
        return {
            "configured": True,
            "category": category,
            "category_label": category_config["label"],
            "places": [],
            "maps_search_url": search_url,
            "error": str(exc),
        }

    places = []
    for place in payload.get("places") or []:
        display_name = place.get("displayName") or {}
        places.append(
            {
                "name": display_name.get("text") or "Unnamed place",
                "address": place.get("shortFormattedAddress") or "",
                "rating": place.get("rating"),
                "maps_url": place.get("googleMapsUri") or search_url,
                "primary_type": place.get("primaryType"),
                "location": place.get("location"),
            }
        )

    return {
        "configured": True,
        "category": category,
        "category_label": category_config["label"],
        "places": places,
        "maps_search_url": search_url,
        "provider_response": payload,
    }


def format_nearby_places(result: dict[str, Any]) -> str:
    places = result.get("places") or []
    if not places:
        return f"No live place results returned. Open Google Maps search: {result['maps_search_url']}"
    lines = []
    for index, place in enumerate(places[:5], start=1):
        address = f"\nAddress: {place['address']}" if place.get("address") else ""
        rating = f"\nRating: {place['rating']}" if place.get("rating") else ""
        lines.append(f"{index}. {place['name']}{address}{rating}\nMaps: {place['maps_url']}")
    return "\n\n".join(lines)


def nearby_places_response(
    phone: str,
    category: str,
    latitude: float,
    longitude: float,
    radius_meters: int = 1500,
) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        reply = pick_reply("unknown_guest", {"phone": normalize_phone(phone), **brand_values()})
        return {"action": "unknown_guest", "reply": reply}
    normalized_category = normalize_nearby_category(category)
    if not normalized_category:
        values = context["values"]
        reply = pick_reply("nearby_category_invalid", values)
        send_whatsapp_text(phone, reply)
        return {"action": "nearby_category_invalid", "reply": reply}

    result = search_live_nearby_places(normalized_category, latitude, longitude, radius_meters)
    values = dict(context["values"])
    values["nearby_category"] = result["category_label"]
    values["nearby_results"] = format_nearby_places(result)
    reply = pick_reply("nearby_live_result", values)
    remember_session(
        phone,
        pending_action=None,
        nearby_category=None,
        last_location={"latitude": latitude, "longitude": longitude},
        last_nearby_search={
            "category": normalized_category,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": now_iso(),
        },
    )
    delivery = send_whatsapp_text(phone, reply)
    return {"action": "nearby_live_result", "reply": reply, "nearby": result, "delivery": delivery}


def answer_intent(phone: str, intent: str) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        reply = pick_reply("unknown_guest", {"phone": normalize_phone(phone), **brand_values()})
        delivery = send_whatsapp_text(phone, reply)
        return {"action": "unknown_guest", "reply": reply, "delivery": delivery}

    values = context["values"]
    if intent == "directions":
        return start_directions_flow(phone, values)
    if intent == "nearby_places":
        return start_nearby_flow(phone, values)
    if intent == "ai_support":
        return start_ai_support_flow(phone, values)
    if intent.startswith("nearby_category:"):
        return choose_nearby_category(phone, intent.split(":", 1)[1])
    if intent == "menu":
        reply = menu_text(values)
        delivery = send_guest_menu(phone, values)
        return {
            "action": intent,
            "reply": reply,
            "delivery": delivery,
            "booking_id": context["booking"].get("booking_id"),
            "property_id": context["property"].get("id"),
        }
    elif intent == "report_issue":
        remember_session(phone, pending_action="report_issue")
        reply = pick_reply("report_issue_prompt", values)
    elif intent in MENU_OPTIONS:
        reply = pick_reply(intent, values)
    else:
        reply = pick_reply("fallback", values)

    delivery = send_whatsapp_text(phone, reply)
    return {
        "action": intent,
        "reply": reply,
        "delivery": delivery,
        "booking_id": context["booking"].get("booking_id"),
        "property_id": context["property"].get("id"),
    }


def handle_issue_description(phone: str, text: str) -> dict[str, Any]:
    context = guest_context(phone)
    if not context:
        reply = pick_reply("unknown_guest", {"phone": normalize_phone(phone), **brand_values()})
        return {"action": "unknown_guest", "reply": reply}
    values = dict(context["values"])
    values["issue_summary"] = text.strip()
    remember_session(
        phone,
        pending_action=None,
        last_issue={
            "description": text.strip(),
            "booking_id": context["booking"].get("booking_id"),
            "property_id": context["property"].get("id"),
            "created_at": now_iso(),
        },
    )
    reply = pick_reply("report_issue_confirm", values)
    delivery = send_whatsapp_text(phone, reply)
    return {"action": "report_issue_confirm", "reply": reply, "delivery": delivery, "stored": False}


def receive_preview_message(phone: str, text: str) -> dict[str, Any]:
    return process_incoming_whatsapp_message(phone, {"type": "text", "text": text})


def preview_action_response(phone: str, action: str) -> dict[str, Any]:
    return answer_intent(phone, resolve_intent(action) or action)


def process_incoming_whatsapp_message(
    phone: str,
    message: dict[str, Any],
    message_id: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_phone(phone)
    message_type = message.get("type", "text")
    logger.info("incoming_message phone=%s message_id=%s type=%s", normalized, message_id, message_type)

    if message_type == "location":
        location = message.get("location") or {}
        try:
            session = get_session(normalized)
            if session.get("pending_action") == "live_nearby_location":
                category = session.get("nearby_category") or "grocery"
                return nearby_places_response(
                    normalized,
                    category,
                    float(location["latitude"]),
                    float(location["longitude"]),
                )
            return directions_response(
                normalized,
                float(location["latitude"]),
                float(location["longitude"]),
            )
        except (KeyError, TypeError, ValueError):
            reply = "Please share a valid WhatsApp location so I can calculate directions."
            send_whatsapp_text(normalized, reply)
            return {"action": "invalid_location", "reply": reply}

    text = _message_text(message).strip()
    remember_session(normalized, last_message=text)
    if not text:
        return answer_intent(normalized, "menu")

    lowered = text.lower().strip()
    if lowered in {"hi", "hello", "hey", "menu", "help", PREDEFINED_MESSAGE.lower()}:
        remember_session(normalized, pending_action=None, nearby_category=None)
        return answer_intent(normalized, "menu")

    session = get_session(normalized)
    if session.get("pending_action") == "report_issue":
        return handle_issue_description(normalized, text)
    if session.get("pending_action") == "ai_support":
        if match_ai_support_question(text):
            return answer_ai_support_question(normalized, text)
        intent = resolve_intent(text)
        if intent and intent != "ai_support":
            remember_session(normalized, pending_action=None)
            return answer_intent(normalized, intent)
        return answer_ai_support_question(normalized, text)
    if session.get("pending_action") == "live_nearby_category":
        category = normalize_nearby_category(text)
        if category:
            return choose_nearby_category(normalized, category)
        context = guest_context(normalized)
        values = context["values"] if context else {"phone": normalized, **brand_values()}
        reply = pick_reply("nearby_category_invalid", values)
        send_whatsapp_text(normalized, reply)
        return {"action": "nearby_category_invalid", "reply": reply}
    if session.get("pending_action") == "live_nearby_location" and text.lower() not in {"menu", "hi", "hello"}:
        context = guest_context(normalized)
        values = context["values"] if context else {"phone": normalized, **brand_values()}
        category = session.get("nearby_category") or "grocery"
        values["nearby_category"] = NEARBY_CATEGORIES[category]["label"]
        reply = pick_reply("nearby_need_location", values)
        send_whatsapp_text(normalized, reply)
        return {"action": "nearby_need_location", "reply": reply}
    if session.get("pending_action") == "directions" and text.lower() not in {"menu", "hi", "hello"}:
        context = guest_context(normalized)
        values = context["values"] if context else {"phone": normalized, **brand_values()}
        reply = pick_reply("directions_need_location", values)
        send_whatsapp_text(normalized, reply)
        return {"action": "directions_need_location", "reply": reply}

    intent = resolve_intent(text)
    if intent:
        return answer_intent(normalized, intent)

    context = guest_context(normalized)
    values = context["values"] if context else {"phone": normalized, **brand_values()}
    if context and match_ai_support_question(text):
        return answer_ai_support_question(normalized, text)
    reply = pick_reply("fallback", values) if context else pick_reply("unknown_guest", values)
    delivery = send_whatsapp_text(normalized, reply)
    return {"action": "fallback" if context else "unknown_guest", "reply": reply, "delivery": delivery}


def _message_text(message: dict[str, Any]) -> str:
    if message.get("type") == "text":
        return str(message.get("text") or "").strip()
    if message.get("type") == "interactive":
        interactive = message.get("interactive") or {}
        button_reply = interactive.get("button_reply") or {}
        list_reply = interactive.get("list_reply") or {}
        return str(
            button_reply.get("id")
            or button_reply.get("title")
            or list_reply.get("id")
            or list_reply.get("title")
            or ""
        ).strip()
    if message.get("type") == "button":
        button = message.get("button") or {}
        return str(button.get("payload") or button.get("text") or "").strip()
    return ""


def process_whatsapp_webhook_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            receiving_phone_number_id = str(metadata.get("phone_number_id") or "").strip() or None
            display_phone_number = str(metadata.get("display_phone_number") or "").strip() or None
            for status in value.get("statuses") or []:
                logger.info("webhook_status provider_message_id=%s status=%s", status.get("id"), status.get("status"))
                results.append({"action": "message_status", "status": status.get("status"), "provider_message_id": status.get("id")})
            for raw_message in value.get("messages") or []:
                phone = raw_message.get("from") or ""
                if not phone:
                    continue
                message = _normalize_webhook_message(raw_message)
                token = _CURRENT_WHATSAPP_PHONE_NUMBER_ID.set(receiving_phone_number_id)
                try:
                    result = process_incoming_whatsapp_message(phone, message, raw_message.get("id"))
                finally:
                    _CURRENT_WHATSAPP_PHONE_NUMBER_ID.reset(token)
                result["receiving_phone_number_id"] = receiving_phone_number_id
                result["display_phone_number"] = display_phone_number
                results.append(result)
    return results


def _normalize_webhook_message(raw_message: dict[str, Any]) -> dict[str, Any]:
    message_type = raw_message.get("type")
    if message_type == "text":
        return {"type": "text", "text": ((raw_message.get("text") or {}).get("body") or "").strip()}
    if message_type == "interactive":
        return {"type": "interactive", "interactive": raw_message.get("interactive") or {}}
    if message_type == "button":
        return {"type": "button", "button": raw_message.get("button") or {}}
    if message_type == "location":
        return {"type": "location", "location": raw_message.get("location") or {}}
    return {"type": "text", "text": ""}
