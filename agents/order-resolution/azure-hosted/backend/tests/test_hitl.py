from app.modules.order_resolution.hitl import extract_order_id


def test_extract_order_id_preserves_requested_order() -> None:
    assert extract_order_id("Order ORD-1004 arrived damaged and broken.") == "ord-1004"
    assert extract_order_id("Please check ord 1009.") == "ord-1009"


def test_extract_order_id_retains_default_for_unspecified_order() -> None:
    assert extract_order_id("My order arrived late.") == "ord-1001"
