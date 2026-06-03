from datetime import datetime, timedelta, timezone

from app.scrapers.getinvolved import _event_item_to_dict, _is_upcoming


def test_is_upcoming_future_event():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    event = {
        "date": future.strftime("%Y-%m-%d"),
        "_starts_on": future,
    }
    assert _is_upcoming(event) is True


def test_is_upcoming_past_event():
    past = datetime.now(timezone.utc) - timedelta(days=2)
    event = {"date": past.strftime("%Y-%m-%d"), "_starts_on": past}
    assert _is_upcoming(event) is False


def test_event_item_parses_rsvp_link():
    item = {
        "id": 999,
        "name": "Test Event",
        "startsOn": "2026-12-01T18:00:00+00:00",
        "location": "College Ave",
        "organizationName": "Test Club",
        "benefitNames": ["Free Food"],
        "description": "Hello",
    }
    parsed = _event_item_to_dict(item)
    assert parsed is not None
    assert "gi-999" in parsed["event_id"]
    assert parsed["free_food"] is True
    assert "engage/event/999" in parsed["rsvp_link"]
