# WhatsApp Guest Assistant POC

FastAPI backend for a rule-based WhatsApp assistant for guests whose bookings are already confirmed.

No AI or LLM is used in this POC. The assistant uses stored demo booking/property JSON and randomized approved response templates so replies feel conversational during a showcase.

## Features

- Welcome message and guest menu
- Confirmed guest lookup by WhatsApp phone number
- Check-in instructions
- Wi-Fi details
- Parking information
- Property facilities
- Live nearby places from guest location for grocery, medical/pharmacy and mall searches
- Checkout instructions
- Contact host
- Maintenance issue showcase flow
- Directions from guest location using Google Maps when `GOOGLE_MAPS_API_KEY` is configured
- Meta WhatsApp Cloud API webhook support
- Mock WhatsApp endpoints for local demos

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
919999000001 - Rahul - Casa Azul Beach Villa
919999000002 - Priya - Pink City Heritage Apartment
```

Unknown numbers receive a booking-not-found response.

## Mock Demo Flow

Open the mock menu:

```http
GET /api/mock-whatsapp/menu?phone=919999000001
```

Send a mock guest message:

```http
POST /api/mock-whatsapp/message
Content-Type: application/json
```

```json
{
  "phone": "919999000001",
  "text": "wifi"
}
```

Select a menu action:

```http
POST /api/mock-whatsapp/select
Content-Type: application/json
```

```json
{
  "phone": "919999000001",
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
  "phone": "919999000001",
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
  "phone": "919999000001",
  "latitude": 15.4909,
  "longitude": 73.8278,
  "travel_mode": "driving"
}
```

## WhatsApp Commands

Guests can type:

```text
menu
1 or check-in
2 or wifi
3 or parking
4 or facilities
5 or nearby places
6 or checkout
7 or contact host
8 or report issue
9 or directions
```

For live nearby places, the assistant asks the guest to choose grocery, medical/pharmacy or mall, then asks for their current WhatsApp location. If `GOOGLE_MAPS_API_KEY` is configured, the backend calls Google Places Nearby Search API and returns live place names, addresses, ratings and Maps links. Without the API key, it returns a Google Maps search link for demo continuity.

For maintenance, the assistant asks for one issue description and returns a host-ready acknowledgement. The POC does not persist issue reports.

For directions, the assistant asks the guest to share their WhatsApp location. If `GOOGLE_MAPS_API_KEY` is configured, the backend calls Google Maps Distance Matrix API and returns distance, travel time and a Maps route link. Without the API key, it still returns a Google Maps route link for demo continuity.

## Meta WhatsApp Setup

Set these environment variables for a real WhatsApp POC:

```text
WHATSAPP_PROVIDER=meta
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_access_token
WHATSAPP_GRAPH_API_VERSION=v20.0
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

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
