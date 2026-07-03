"""HAR parsing: journey extraction with static-asset filtering."""

from pathlib import Path

from shamal.har import parse_har

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseHar:
    def test_static_assets_filtered(self) -> None:
        journey = parse_har(FIXTURES / "session.har")
        urls = [step.url for step in journey.steps]
        assert not any(".js" in u or ".png" in u or ".css" in u for u in urls)

    def test_api_steps_kept_in_order(self) -> None:
        journey = parse_har(FIXTURES / "session.har")
        assert [(s.method, s.url) for s in journey.steps] == [
            ("GET", "https://shop.example/api/products?category=sale"),
            ("POST", "https://shop.example/api/cart"),
            ("POST", "https://shop.example/api/checkout"),
        ]

    def test_post_bodies_preserved(self) -> None:
        journey = parse_har(FIXTURES / "session.har")
        cart = journey.steps[1]
        assert cart.body == '{"productId": 42, "qty": 1}'
        assert cart.mime_type == "application/json"

    def test_base_url_is_dominant_api_origin(self) -> None:
        journey = parse_har(FIXTURES / "session.har")
        assert journey.base_url == "https://shop.example"
