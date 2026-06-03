from datetime import date
from unittest.mock import patch

from app.scrapers.getinvolved import _fetch_events_from_api, _valid_event_year, fetch_upcoming_events


def test_valid_event_year():
    assert _valid_event_year({"date": "2026-06-01"}) is True
    assert _valid_event_year({"date": "1970-01-01"}) is False


def test_fetch_stops_after_past_page_when_using_descending():
    """Regression: do not walk entire catalog when fewer than max upcoming exist."""

    def fake_get(url, headers=None, params=None, timeout=None):
        skip = params.get("skip", 0)
        if skip == 0:
            value = [
                {
                    "id": "1",
                    "name": "Future Meetup",
                    "startsOn": "2026-12-01T18:00:00+00:00",
                    "location": "Rutgers",
                    "organizationName": "Club",
                    "benefitNames": [],
                },
                {
                    "id": "2",
                    "name": "Old Meetup",
                    "startsOn": "2020-01-01T18:00:00+00:00",
                    "location": "Rutgers",
                    "organizationName": "Club",
                    "benefitNames": [],
                },
            ]
        else:
            value = [
                {
                    "id": "3",
                    "name": "Ancient",
                    "startsOn": "2015-01-01T18:00:00+00:00",
                    "location": "Rutgers",
                    "organizationName": "Club",
                    "benefitNames": [],
                },
            ]
        return type(
            "R",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"value": value, "@odata.count": 200},
            },
        )()

    with patch("app.scrapers.getinvolved.requests.get", side_effect=fake_get):
        events = _fetch_events_from_api(
            order_direction="descending",
            max_results=10,
            upcoming_only=True,
        )
    assert len(events) == 1
    assert events[0]["title"] == "Future Meetup"


def test_fetch_upcoming_passes_starts_after():
    with patch("app.scrapers.getinvolved._fetch_events_from_api", return_value=[]) as mock:
        fetch_upcoming_events(5)
    _, kwargs = mock.call_args
    assert kwargs["starts_after"] == date.today().isoformat()
    assert kwargs["order_direction"] == "ascending"
