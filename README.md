# Silkhaus WhatsApp Concierge POC

FastAPI backend for a Silkhaus-branded WhatsApp AI concierge for guests whose bookings are already confirmed.

The assistant uses Silkhaus demo booking/property data, conversational support matching and randomized response variants so replies feel polished during a showcase.

## Features

- Silkhaus-branded welcome message and guest menu
- Confirmed guest lookup by WhatsApp phone number
- Self check-in and access instructions
- Wi-Fi details
- Parking information
- Apartment amenities
- Live nearby places from guest location for grocery, medical/pharmacy and mall searches
- Checkout instructions
- Contact Silkhaus support
- Apartment issue showcase flow
- Directions from guest location using Google Maps when `GOOGLE_MAPS_API_KEY` is configured
- Meta WhatsApp Cloud API webhook support with interactive menu lists and category buttons
- Silkhaus AI Concierge showcase for guest questions
- WhatsApp preview endpoints for backend demos

## Structure

```text
backend/
  app/
    main.py        FastAPI routes and webhook endpoints
    services.py    Rule-based guest assistant logic
    schemas.py     Request models
  data/
    guest_assistant_demo.json
  tests/
    test_guest_assistant_api.py
api/
  index.py         Vercel Python entrypoint
```

## Backend Setup

Install dependencies:

```powershell
& 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install -r backend\requirements.txt --target backend\.deps
```

Run FastAPI:

```powershell
$env:PYTHONPATH = "$PWD\backend\.deps;$PWD\backend"
& 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -c "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8000)"
```

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```powershell
$env:PYTHONPATH = "$PWD\backend\.deps;$PWD\backend"
& 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s backend\tests -v
```

## Demo Guests

The demo data is stored in `backend/data/guest_assistant_demo.json`.

Known guest numbers:

```text
918459294241 - Dhiraj Rajput - Silkhaus Dubai Marina Premium Apartment
919999000002 - Priya - Silkhaus Yas Island Serviced Apartment
```

Unknown numbers receive a booking-not-found response.

## Preview Demo Flow

Open the menu preview:

```http
GET /api/whatsapp/menu-preview?phone=918459294241
```

Preview a guest message:

```http
POST /api/whatsapp/message-preview
Content-Type: application/json
```

```json
{
  "phone": "918459294241",
  "text": "wifi"
}
```

Select a menu action:

```http
POST /api/whatsapp/select-preview
Content-Type: application/json
```

```json
{
  "phone": "918459294241",
  "action": "nearby_places"
}
```

The assistant will ask for a category, then ask the guest to share their current WhatsApp location.

Preview live nearby places:

```http
POST /api/nearby/preview
Content-Type: application/json
```

```json
{
  "phone": "918459294241",
  "category": "grocery",
  "latitude": 15.4909,
  "longitude": 73.8278,
  "radius_meters": 1500
}
```

Preview directions:

```http
POST /api/directions/preview
Content-Type: application/json
```

```json
{
  "phone": "918459294241",
  "latitude": 15.4909,
  "longitude": 73.8278,
  "travel_mode": "driving"
}
```

## WhatsApp Commands

In WhatsApp, guests receive an interactive list for the main menu and quick-reply buttons for nearby categories. Text commands still work as fallback:

```text
menu
1 or check-in
2 or wifi
3 or parking
4 or facilities
5 or nearby places
6 or checkout
7 or AI Concierge
8 or contact support
9 or report issue
10 or directions
```

## Silkhaus AI Concierge Demo

This POC includes a client-facing "Silkhaus AI Concierge" option for natural guest questions about the stay.

Example questions:

```text
What is Silkhaus?
Can I extend my stay?
How does self check-in work?
Is Wi-Fi included?
What amenities are included?
How can I contact support?
When is my booking confirmed?
```

For live nearby places, the assistant asks the guest to choose grocery, medical/pharmacy or mall, then asks for their current WhatsApp location. If `GOOGLE_MAPS_API_KEY` is configured, the backend calls Google Places Nearby Search API and returns live place names, addresses, ratings and Maps links. Without the API key, it returns a Google Maps search link for demo continuity.

For maintenance, the assistant asks for one issue description and returns a support-ready acknowledgement.

For directions, the assistant asks the guest to share their WhatsApp location. If `GOOGLE_MAPS_API_KEY` is configured, the backend calls Google Maps Distance Matrix API and returns distance, travel time and a Maps route link. Without the API key, it still returns a Google Maps route link for demo continuity.

## Meta WhatsApp Setup

Set these environment variables for a real WhatsApp POC:

```text
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_GRAPH_API_VERSION=v20.0
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

For real WhatsApp replies, `WHATSAPP_ACCESS_TOKEN` must be a valid Meta Cloud API token and `WHATSAPP_PHONE_NUMBER_ID` must be the Phone Number ID for the WhatsApp sender. If Meta returns `401` with OAuth code `190`, refresh the token and redeploy.

Webhook callback URL:

```text
https://YOUR_PUBLIC_DOMAIN/webhook/whatsapp
```

Local verification token defaults to:

```text
dev_verify_token
```

## Deployment

This repo is backend-only. `vercel.json` routes `/api/*`, `/webhook/*` and `/health` to the FastAPI serverless function.
