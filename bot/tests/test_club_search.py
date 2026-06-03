from app.services.club_search import (
    expand_search_terms,
    extract_social_links,
    get_instagram_link,
    rank_clubs,
    score_club,
)


def test_expand_computer_science():
    terms = expand_search_terms("computer science clubs")
    assert "computer science" in terms
    assert "usacs" in terms or "programming" in terms


def test_score_cs_club():
    club = {
        "name": "Undergraduate Student Alliance of Computer Scientists",
        "description": "USACS supports CS students",
        "category": ["Science, Technology, Engineering, and Math Community"],
        "tags": ["Academic Student Organizations"],
    }
    terms = expand_search_terms("computer science")
    assert score_club(club, terms) > 0


def test_rank_returns_multiple_cs_clubs():
    clubs = [
        {
            "name": "USACS",
            "description": "CS org",
            "category": ["STEM"],
            "tags": [],
        },
        {
            "name": "Women in Computer Science",
            "description": "WiCS",
            "category": ["STEM", "Women Community"],
            "tags": [],
        },
        {
            "name": "Chess Club",
            "description": "board games",
            "category": ["Recreation"],
            "tags": [],
        },
    ]
    ranked = rank_clubs(clubs, expand_search_terms("computer science"), limit=10)
    names = [c["name"] for c in ranked]
    assert "USACS" in names
    assert "Women in Computer Science" in names
    assert "Chess Club" not in names


def test_extract_instagram_from_html():
    html = '<p>Follow us <a href="https://www.instagram.com/rutgersusacs/">here</a></p>'
    links = extract_social_links(html)
    assert links.get("instagram") == "https://www.instagram.com/rutgersusacs/"


def test_get_instagram_link_from_links_json():
    club = {"links": {"instagram": "https://www.instagram.com/rutgersusacs/"}}
    assert get_instagram_link(club) == "https://www.instagram.com/rutgersusacs/"
