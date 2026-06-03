from app.services.command_guide import (
    append_next_steps,
    build_find_goal,
    format_topic_guide,
)
from app.services.coach_session_service import detect_domain


def test_build_find_goal_with_details():
    g = build_find_goal("tri_state", "jazz under $40")
    assert "jazz" in g


def test_format_topic_guide_tri_state():
    text = format_topic_guide("tri_state", "NBA")
    assert "/compare_prices NBA" in text
    assert "/find" in text


def test_append_next_steps_ask_tri_state():
    body = append_next_steps("Answer here.", command="ask", user_text="cheap concert MSG")
    assert "/compare_prices" in body
    assert "/find" in body


def test_detect_domain_still_works():
    assert detect_domain("NBA finals tickets") == "tri_state"
