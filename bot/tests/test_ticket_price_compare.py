from app.services.ticket_price_compare import (
    _parse_budget_max,
    _sort_cheapest_first,
    format_cheapest_tri_state_report,
)


def test_sort_cheapest_first():
    rows = [
        {"title": "A", "price_min": 120, "date": "2026-06-10"},
        {"title": "B", "price_min": 35, "date": "2026-06-11"},
        {"title": "C", "price_min": None, "date": "2026-06-09"},
    ]
    sorted_rows = _sort_cheapest_first(rows)
    assert sorted_rows[0]["title"] == "B"
    assert sorted_rows[-1]["title"] == "C"


def test_parse_budget_max():
    assert _parse_budget_max("under $50") == 50.0
    assert _parse_budget_max("no numbers") is None


def test_format_report_without_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.ticket_price_compare.settings.ticketmaster_api_key",
        "",
    )
    text = format_cheapest_tri_state_report(keyword="NBA")
    assert "TICKETMASTER_API_KEY" in text
