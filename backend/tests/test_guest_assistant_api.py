from __future__ import annotations

import os
import unittest

from app.main import (
    directions_preview,
    get_mock_menu,
    guest_profile,
    nearby_preview,
    receive_mock_whatsapp_message,
    select_mock_option,
)
from app.schemas import DirectionPreviewIn, MockMessageIn, MockSelectIn, NearbyPreviewIn
from app.services import clear_runtime_state, process_whatsapp_webhook_payload


KNOWN_PHONE = "919999000001"
UNKNOWN_PHONE = "919999009999"


class GuestAssistantApiTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_runtime_state()
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)

    def test_known_guest_receives_personal_menu(self) -> None:
        response = get_mock_menu(KNOWN_PHONE)

        self.assertTrue(response["known_guest"])
        self.assertEqual(response["booking"]["booking_id"], "BK-CASA-1001")
        self.assertEqual(response["property"]["name"], "Casa Azul Beach Villa")
        self.assertEqual(len(response["options"]), 9)
        self.assertIn("Casa Azul Beach Villa", response["reply"])

    def test_unknown_guest_gets_booking_fallback(self) -> None:
        response = get_mock_menu(UNKNOWN_PHONE)

        self.assertFalse(response["known_guest"])
        self.assertEqual(response["options"], [])
        self.assertTrue(
            any(word in response["reply"].lower() for word in ["booking", "confirmed", "host"])
        )

    def test_wifi_action_returns_stored_demo_details_with_variant_reply(self) -> None:
        response = select_mock_option(MockSelectIn(phone=KNOWN_PHONE, action="wifi"))

        self.assertEqual(response["action"], "wifi")
        self.assertIn("CasaAzul_Guest", response["reply"])
        self.assertIn("BeachStay4521", response["reply"])

    def test_nearby_places_starts_live_category_flow(self) -> None:
        response = receive_mock_whatsapp_message(
            MockMessageIn(phone=KNOWN_PHONE, text="nearby places")
        )

        self.assertEqual(response["action"], "nearby_category_prompt")
        self.assertIn("grocery", response["reply"].lower())
        self.assertIn("medical", response["reply"].lower())

    def test_nearby_category_asks_for_guest_location(self) -> None:
        receive_mock_whatsapp_message(MockMessageIn(phone=KNOWN_PHONE, text="nearby places"))
        response = receive_mock_whatsapp_message(MockMessageIn(phone=KNOWN_PHONE, text="grocery"))

        self.assertEqual(response["action"], "nearby_location_prompt")
        self.assertEqual(response["category"], "grocery")
        self.assertIn("location", response["reply"].lower())

    def test_nearby_preview_returns_maps_search_link_without_api_key(self) -> None:
        response = nearby_preview(
            NearbyPreviewIn(
                phone=KNOWN_PHONE,
                category="medical",
                latitude=15.4909,
                longitude=73.8278,
            )
        )

        self.assertEqual(response["action"], "nearby_live_result")
        self.assertFalse(response["nearby"]["configured"])
        self.assertEqual(response["nearby"]["category"], "medical")
        self.assertIn("https://www.google.com/maps/search/", response["nearby"]["maps_search_url"])
        self.assertIn("Medical", response["reply"])

    def test_report_issue_is_showcased_without_database_storage(self) -> None:
        prompt = receive_mock_whatsapp_message(MockMessageIn(phone=KNOWN_PHONE, text="report issue"))
        response = receive_mock_whatsapp_message(
            MockMessageIn(phone=KNOWN_PHONE, text="Bedroom AC is not cooling")
        )

        self.assertEqual(prompt["action"], "report_issue")
        self.assertEqual(response["action"], "report_issue_confirm")
        self.assertFalse(response["stored"])
        self.assertIn("Bedroom AC is not cooling", response["reply"])

    def test_directions_preview_returns_maps_link_without_api_key(self) -> None:
        response = directions_preview(
            DirectionPreviewIn(
                phone=KNOWN_PHONE,
                latitude=15.4909,
                longitude=73.8278,
            )
        )

        self.assertEqual(response["action"], "directions_result")
        self.assertFalse(response["directions"]["configured"])
        self.assertIn("https://www.google.com/maps/dir/", response["directions"]["maps_url"])
        self.assertTrue(
            "Casa Azul Beach Villa" in response["reply"]
            or "Candolim Beach Road" in response["reply"]
        )

    def test_webhook_location_message_triggers_directions_flow(self) -> None:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.demo.location",
                                        "from": KNOWN_PHONE,
                                        "type": "location",
                                        "location": {
                                            "latitude": 15.4909,
                                            "longitude": 73.8278,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        results = process_whatsapp_webhook_payload(payload)

        self.assertEqual(results[0]["action"], "directions_result")
        self.assertIn("maps_url", results[0]["directions"])

    def test_webhook_location_message_triggers_live_nearby_when_pending(self) -> None:
        receive_mock_whatsapp_message(MockMessageIn(phone=KNOWN_PHONE, text="nearby places"))
        receive_mock_whatsapp_message(MockMessageIn(phone=KNOWN_PHONE, text="mall"))
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.demo.nearby.location",
                                        "from": KNOWN_PHONE,
                                        "type": "location",
                                        "location": {
                                            "latitude": 15.4909,
                                            "longitude": 73.8278,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        results = process_whatsapp_webhook_payload(payload)

        self.assertEqual(results[0]["action"], "nearby_live_result")
        self.assertEqual(results[0]["nearby"]["category"], "mall")
        self.assertIn("maps_search_url", results[0]["nearby"])

    def test_interactive_menu_selection_returns_check_in_details(self) -> None:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.demo.button",
                                        "from": KNOWN_PHONE,
                                        "type": "interactive",
                                        "interactive": {
                                            "button_reply": {
                                                "id": "check_in",
                                                "title": "Check-in instructions",
                                            }
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        results = process_whatsapp_webhook_payload(payload)

        self.assertEqual(results[0]["action"], "check_in")
        self.assertIn("4521", results[0]["reply"])

    def test_guest_profile_exposes_demo_context_for_showcase(self) -> None:
        response = guest_profile(KNOWN_PHONE)

        self.assertTrue(response["known_guest"])
        self.assertEqual(response["property"]["id"], "goa_villa_001")
        self.assertEqual(response["available_actions"][0]["id"], "check_in")


if __name__ == "__main__":
    unittest.main()
