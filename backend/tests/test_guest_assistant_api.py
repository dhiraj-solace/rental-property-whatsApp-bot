from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.main import (
    directions_preview,
    get_menu_preview,
    guest_profile,
    nearby_preview,
    receive_whatsapp_message_preview,
    select_whatsapp_option_preview,
)
from app.schemas import DirectionPreviewIn, MessagePreviewIn, NearbyPreviewIn, SelectPreviewIn
from app.services import clear_runtime_state, process_whatsapp_webhook_payload


KNOWN_PHONE = "918459294241"
UNKNOWN_PHONE = "919999009999"


class GuestAssistantApiTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_runtime_state()
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        os.environ.pop("WHATSAPP_PHONE_NUMBER_ID", None)
        os.environ.pop("WHATSAPP_ACCESS_TOKEN", None)

    def test_known_guest_receives_personal_menu(self) -> None:
        response = get_menu_preview(KNOWN_PHONE)

        self.assertTrue(response["known_guest"])
        self.assertEqual(response["booking"]["booking_id"], "SH-DXB-1001")
        self.assertEqual(response["property"]["name"], "Silkhaus Dubai Marina Premium Apartment")
        self.assertEqual(len(response["options"]), 10)
        self.assertIn("Silkhaus", response["reply"])

    def test_unknown_guest_gets_booking_fallback(self) -> None:
        response = get_menu_preview(UNKNOWN_PHONE)

        self.assertFalse(response["known_guest"])
        self.assertEqual(response["options"], [])
        self.assertTrue(
            any(word in response["reply"].lower() for word in ["booking", "confirmed", "host"])
        )

    def test_wifi_action_returns_stored_demo_details_with_variant_reply(self) -> None:
        response = select_whatsapp_option_preview(SelectPreviewIn(phone=KNOWN_PHONE, action="wifi"))

        self.assertEqual(response["action"], "wifi")
        self.assertIn("Silkhaus_Marina_Guest", response["reply"])
        self.assertIn("Silkhaus4521", response["reply"])

    def test_menu_message_sends_whatsapp_interactive_list(self) -> None:
        response = receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="hi"))

        request_body = response["delivery"]["request_body"]
        self.assertEqual(response["action"], "menu")
        self.assertEqual(request_body["type"], "interactive")
        self.assertEqual(request_body["interactive"]["type"], "list")
        self.assertEqual(request_body["interactive"]["action"]["button"], "Open menu")
        row_ids = [
            row["id"]
            for section in request_body["interactive"]["action"]["sections"]
            for row in section["rows"]
        ]
        self.assertIn("wifi", row_ids)
        self.assertIn("nearby_places", row_ids)
        self.assertIn("ai_support", row_ids)

    def test_ai_support_menu_option_prompts_fixed_questions(self) -> None:
        response = receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="AI Support"))

        self.assertEqual(response["action"], "ai_support_prompt")
        self.assertIn("Silkhaus", response["reply"])
        self.assertIn("Can I extend my stay?", response["reply"])

    def test_direct_fixed_question_returns_ai_support_answer(self) -> None:
        response = receive_whatsapp_message_preview(
            MessagePreviewIn(phone=KNOWN_PHONE, text="Can I extend my stay?")
        )

        self.assertEqual(response["action"], "ai_support_answer")
        self.assertEqual(response["question_id"], "flexible_stays")
        self.assertTrue(
            "extension" in response["reply"].lower()
            or "available" in response["reply"].lower()
            or "flexible" in response["reply"].lower()
        )

    def test_ai_support_session_prioritizes_fixed_faq_match(self) -> None:
        receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="AI Support"))
        response = receive_whatsapp_message_preview(
            MessagePreviewIn(phone=KNOWN_PHONE, text="Is Wi-Fi included?")
        )

        self.assertEqual(response["action"], "ai_support_answer")
        self.assertEqual(response["question_id"], "wifi_included")
        self.assertIn("Silkhaus_Marina_Guest", response["reply"])

    def test_nearby_places_starts_live_category_flow(self) -> None:
        response = receive_whatsapp_message_preview(
            MessagePreviewIn(phone=KNOWN_PHONE, text="nearby places")
        )

        self.assertEqual(response["action"], "nearby_category_prompt")
        self.assertIn("grocery", response["reply"].lower())
        self.assertIn("medical", response["reply"].lower())
        request_body = response["delivery"]["request_body"]
        self.assertEqual(request_body["type"], "interactive")
        self.assertEqual(request_body["interactive"]["type"], "button")
        button_ids = [
            button["reply"]["id"]
            for button in request_body["interactive"]["action"]["buttons"]
        ]
        self.assertEqual(
            button_ids,
            ["nearby_category:grocery", "nearby_category:medical", "nearby_category:mall"],
        )

    def test_nearby_category_asks_for_guest_location(self) -> None:
        receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="nearby places"))
        response = receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="grocery"))

        self.assertEqual(response["action"], "nearby_location_prompt")
        self.assertEqual(response["category"], "grocery")
        self.assertIn("location", response["reply"].lower())

    def test_interactive_nearby_category_button_asks_for_guest_location(self) -> None:
        receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="nearby places"))
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.demo.nearby.button",
                                        "from": KNOWN_PHONE,
                                        "type": "interactive",
                                        "interactive": {
                                            "button_reply": {
                                                "id": "nearby_category:grocery",
                                                "title": "Grocery",
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

        self.assertEqual(results[0]["action"], "nearby_location_prompt")
        self.assertEqual(results[0]["category"], "grocery")
        self.assertIn("location", results[0]["reply"].lower())

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
        prompt = receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="report issue"))
        response = receive_whatsapp_message_preview(
            MessagePreviewIn(phone=KNOWN_PHONE, text="Bedroom AC is not cooling")
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
            "Silkhaus Dubai Marina Premium Apartment" in response["reply"]
            or "Dubai Marina" in response["reply"]
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
        receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="nearby places"))
        receive_whatsapp_message_preview(MessagePreviewIn(phone=KNOWN_PHONE, text="mall"))
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

    def test_webhook_reply_uses_receiving_phone_number_id(self) -> None:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {
                                    "display_phone_number": "918000000000",
                                    "phone_number_id": "real_business_phone_id",
                                },
                                "messages": [
                                    {
                                        "id": "wamid.demo.same.sender",
                                        "from": KNOWN_PHONE,
                                        "type": "text",
                                        "text": {"body": "wifi"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        with patch.dict(
            os.environ,
            {
                "WHATSAPP_PHONE_NUMBER_ID": "wrong_env_phone_id",
                "WHATSAPP_ACCESS_TOKEN": "demo-token",
            },
            clear=False,
        ):
            with patch("app.services.urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = b'{"messages":[{"id":"wamid.out"}]}'
                results = process_whatsapp_webhook_payload(payload)

        request = urlopen.call_args.args[0]
        self.assertIn("/real_business_phone_id/messages", request.full_url)
        self.assertEqual(results[0]["display_phone_number"], "918000000000")
        self.assertEqual(results[0]["receiving_phone_number_id"], "real_business_phone_id")

    def test_guest_profile_exposes_demo_context_for_showcase(self) -> None:
        response = guest_profile(KNOWN_PHONE)

        self.assertTrue(response["known_guest"])
        self.assertEqual(response["property"]["id"], "silkhaus_dubai_marina_001")
        self.assertEqual(response["available_actions"][0]["id"], "check_in")


if __name__ == "__main__":
    unittest.main()
