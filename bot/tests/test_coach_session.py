from app.services.coach_agent import format_coach_reply
from app.services.coach_session_service import (
    attach_thread,
    detect_domain,
    end_session,
    get_session,
    get_session_by_thread,
    start_session,
)


def test_detect_domain_tri_state():
    assert detect_domain("cheap concert in NYC this weekend") == "tri_state"


def test_detect_domain_campus():
    assert detect_domain("find a computer science club") == "campus"


def test_detect_domain_date():
    assert detect_domain("low pressure first date idea") == "date"


def test_session_lifecycle():
    session = start_session(user_id="u1", username="alice", goal="one concert under $40")
    assert session.user_id == "u1"
    assert session.domain == "tri_state"
    attach_thread("u1", 999, 111)
    assert get_session_by_thread(999) is session
    ended = end_session("u1")
    assert ended is not None
    assert get_session("u1") is None


def test_format_coach_reply_resolved_pick():
    session = start_session(user_id="u2", username="bob", goal="a show")
    data = {
        "reply": "Based on what you said, here's my call.",
        "status": "resolved",
        "top_pick": {
            "title": "Jazz at Newark",
            "why": "Fits your budget and train ride.",
            "when": "Friday night",
            "where": "Newark",
            "cost_tip": "Upper deck",
            "search_query": "jazz tickets Newark",
        },
    }
    text = format_coach_reply(data, session)
    assert "Your pick" in text
    assert "Jazz at Newark" in text
    assert "SeatGeek" in text
