# WhatsApp Guest Assistant POC

## Architecture Overview

The POC is a backend-only WhatsApp guest assistant. A confirmed guest messages the WhatsApp business number, the backend matches their phone number against demo JSON booking data, and returns rule-based answers from approved response templates.

```mermaid
flowchart LR
    Guest["Confirmed Guest<br/>WhatsApp User"]
    Meta["Meta WhatsApp<br/>Cloud API"]
    API["FastAPI Backend<br/>Webhook + Preview APIs"]
    Data["Demo JSON<br/>Bookings + Properties + Templates"]
    Maps["Google Maps APIs<br/>Places + Distance"]
    Host["Host / Property Team"]

    Guest -->|"Menu, questions, location"| Meta
    Meta -->|"Webhook events"| API
    API -->|"Text replies"| Meta
    Meta -->|"Assistant response"| Guest

    API -->|"Read only"| Data
    API -->|"Live places / route lookup"| Maps
    API -->|"Maintenance acknowledgement"| Host
```

## Component Responsibilities

| Component | Responsibility |
| --- | --- |
| Guest | Uses WhatsApp to request stay information. |
| Meta WhatsApp Cloud API | Delivers inbound guest messages and outbound assistant replies. |
| FastAPI Backend | Handles webhook verification, message parsing, guest lookup, menu routing, template selection and Maps calls. |
| Demo JSON | Stores confirmed bookings, property instructions and randomized reply templates. |
| Google Maps APIs | Return live nearby places, distance and travel time when a guest shares location. |
| Host | Receives the maintenance issue in the production version; this POC only showcases the acknowledgement. |

## Guest Flow

```mermaid
flowchart TD
    Start([Guest sends Hi / menu]) --> Lookup{"Phone linked to confirmed booking?"}
    Lookup -->|"No"| Unknown["Return booking-not-found message"]
    Lookup -->|"Yes"| Menu["Return personalized guest menu"]

    Menu --> Action{"Guest selects option"}
    Action --> CheckIn["Check-in instructions"]
    Action --> Wifi["Wi-Fi details"]
    Action --> Parking["Parking information"]
    Action --> Facilities["Property facilities"]
    Action --> Nearby["Live nearby places"]
    Action --> Checkout["Checkout instructions"]
    Action --> Contact["Host contact"]
    Action --> Issue["Ask for maintenance issue"]
    Action --> Directions["Ask guest to share location"]

    Issue --> IssueText["Guest describes issue"]
    IssueText --> IssueAck["Return host-ready acknowledgement"]

    Nearby --> NearbyCategory["Guest chooses grocery, medical or mall"]
    NearbyCategory --> NearbyLocation["Guest shares WhatsApp location"]
    NearbyLocation --> Places{"Google Maps key configured?"}
    Places -->|"Yes"| LivePlaces["Return live places with Maps links"]
    Places -->|"No"| SearchLink["Return Maps search link only"]

    Directions --> Location["Guest shares WhatsApp location"]
    Location --> Maps{"Google Maps key configured?"}
    Maps -->|"Yes"| LiveRoute["Return distance, ETA and Maps link"]
    Maps -->|"No"| LinkOnly["Return Maps route link only"]
```

## API Surface

| Area | Endpoint | Purpose |
| --- | --- | --- |
| Health | `GET /health` | Confirms assistant status and demo configuration. |
| WhatsApp verify | `GET /webhook/whatsapp` | Used by Meta to verify the callback URL. |
| WhatsApp receive | `POST /webhook/whatsapp` | Receives WhatsApp messages, buttons, locations and status updates. |
| Menu preview | `GET /api/whatsapp/menu-preview` | Shows the menu for a demo phone number. |
| Message preview | `POST /api/whatsapp/message-preview` | Previews a guest text message flow. |
| Select preview | `POST /api/whatsapp/select-preview` | Previews a menu/button action. |
| Guest profile | `GET /api/guest/profile` | Exposes matched demo guest/property context. |
| Nearby places | `POST /api/nearby/preview` | Simulates live nearby grocery, medical or mall search. |
| Directions | `POST /api/directions/preview` | Simulates location-based route calculation. |
| Entry point | `GET /api/entry-point` | Generates a WhatsApp deep link for QR/demo use. |

## Data Model

The POC data is read from `backend/data/guest_assistant_demo.json`.

```mermaid
erDiagram
    BOOKING }o--|| PROPERTY : references
    PROPERTY ||--|| HOST : has
    RESPONSE_TEMPLATE }o--|| INTENT : supports

    BOOKING {
        string booking_id
        string guest_name
        string guest_phone
        string property_id
        string status
    }

    PROPERTY {
        string id
        string name
        string address
        float latitude
        float longitude
    }

    RESPONSE_TEMPLATE {
        string intent
        string text_variant
    }
```

## Current Scope

Completed:

- Rule-based WhatsApp guest assistant.
- Randomized approved response variants.
- Confirmed guest lookup from JSON.
- Check-in, Wi-Fi, parking, facilities, live nearby places, checkout and host contact.
- Maintenance issue acknowledgement without storage.
- Location-based Google Places nearby search with search-link fallback.
- Location-based directions with Google Maps API support and link-only fallback.
- Backend-only Vercel deployment config.

Deferred:

- Real PMS/channel-manager booking sync.
- Persistent maintenance issue ticketing.
- Host dashboard.
- Multilingual templates.
- Media/document handling.
