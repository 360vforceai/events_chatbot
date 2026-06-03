from app.services.date_ideas_service import build_date_resource_links, format_date_links_block


def test_date_resource_links():
    links = build_date_resource_links("coffee shop", "New Brunswick NJ")
    labels = {v["label"] for v in links}
    assert "Google Maps" in labels
    assert "Yelp" in labels
    assert "OpenTable" in labels
    assert all("https://" in v["url"] for v in links)


def test_format_date_links_markdown():
    block = format_date_links_block("romantic dinner")
    assert "[Yelp]" in block
    assert "yelp.com" in block
