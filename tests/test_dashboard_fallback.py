"""The dashboard must render even when the warehouse is unreachable."""
from bizlens.dashboard import app as dash_app


def test_loaders_fall_back_to_demo(monkeypatch):
    # Force every warehouse call to fail; loaders should return demo data,
    # not raise, so the UI is always explorable.
    def boom(*args, **kwargs):
        raise RuntimeError("warehouse down")

    monkeypatch.setattr(dash_app.warehouse, "kpi_cards", boom)
    monkeypatch.setattr(dash_app.warehouse, "revenue_trend", boom)
    monkeypatch.setattr(dash_app.warehouse, "retention_matrix", boom)
    monkeypatch.setattr(dash_app.warehouse, "funnel", boom)

    cards, live = dash_app.load_cards()
    assert live is False
    assert cards and cards[0].name == "DAU"
    assert not dash_app.load_trend().empty
    assert not dash_app.load_retention().empty
    assert dash_app.load_funnel()[0].users > 0


def test_build_app_constructs_layout(monkeypatch):
    # build_app() must succeed regardless of DB availability.
    def boom(*args, **kwargs):
        raise RuntimeError("warehouse down")

    for name in ("kpi_cards", "revenue_trend", "retention_matrix", "funnel"):
        monkeypatch.setattr(dash_app.warehouse, name, boom)

    app = dash_app.build_app()
    assert app.layout is not None
