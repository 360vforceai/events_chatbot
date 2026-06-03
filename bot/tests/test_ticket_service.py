from app.services.ticket_service import (
    build_purchase_links,
    format_purchase_links_block,
    _resolve_search_query,
)


def test_build_purchase_links_has_major_vendors():
    links = build_purchase_links("Rutgers basketball tickets")
    labels = {v["label"] for v in links}
    assert "SeatGeek" in labels
    assert "Gametime" in labels
    assert "Ticketmaster" in labels
    assert all(v["url"].startswith("https://") for v in links)


def test_format_block_includes_markdown_links():
    block = format_purchase_links_block("comedy NYC")
    assert "[SeatGeek]" in block
    assert "seatgeek.com" in block


def test_resolve_search_custom_query():
    q = _resolve_search_query("concert", "Drake")
    assert "Drake" in q
    assert "tickets" in q.lower()


def test_resolve_search_default_category():
    q = _resolve_search_query("comedy", None)
    assert "comedy" in q.lower()
