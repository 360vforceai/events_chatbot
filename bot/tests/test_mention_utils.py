from discord_bot.mention_utils import goal_from_mention, strip_bot_mention, thread_name_for


def test_strip_bot_mention():
    assert strip_bot_mention("<@123> cheap concert this weekend", 123) == "cheap concert this weekend"
    assert strip_bot_mention("<@!123>   hello  ", 123) == "hello"


def test_goal_from_mention_empty():
    assert "Rutgers" in goal_from_mention("<@99>", 99)


def test_thread_name_for():
    name = thread_name_for("alice", "NBA tickets under $50")
    assert name.startswith("alice-")
    assert len(name) <= 90
