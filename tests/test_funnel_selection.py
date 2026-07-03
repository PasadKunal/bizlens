"""The funnel must adapt to the event vocabulary present in the dataset."""
from bizlens.warehouse import CLICKSTREAM_FUNNEL, FULFILLMENT_FUNNEL, select_funnel


def test_selects_clickstream_for_synthetic_events():
    present = set(CLICKSTREAM_FUNNEL)
    assert select_funnel(present) == CLICKSTREAM_FUNNEL


def test_selects_fulfillment_for_olist_events():
    # Olist emits purchase/checkout/delivered - only two overlap the clickstream
    # funnel, so the fulfillment funnel must win.
    present = {"purchase", "checkout", "delivered"}
    assert select_funnel(present) == FULFILLMENT_FUNNEL


def test_falls_back_to_available_events():
    present = {"foo", "bar", "baz", "qux"}
    steps = select_funnel(present)
    assert set(steps) <= present
    assert len(steps) <= 5
