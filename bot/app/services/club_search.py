"""Club search helpers — topic expansion, scoring, and social link parsing."""

import re
from typing import Iterable

# Broad topics → extra terms to match categories, tags, names, descriptions
TOPIC_ALIASES: dict[str, list[str]] = {
    "computer science": [
        "computer science",
        "computer",
        "cs",
        "programming",
        "software",
        "informatics",
        "information technology",
        "hackathon",
        "technology",
        "stem",
        "usacs",
        "rumad",
        "colorstack",
        "women in computer",
    ],
    "cs": ["computer science", "computer", "programming", "usacs", "informatics"],
    "engineering": ["engineering", "stem", "technology", "ece", "mechanical"],
    "business": ["business", "finance", "entrepreneurship", "professional"],
}

INSTAGRAM_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?",
    re.IGNORECASE,
)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

CLUB_LIST_LIMIT = 20


def expand_search_terms(keywords: str) -> list[str]:
    """Expand user/router keywords with topic aliases for better recall."""
    raw = [w.strip().lower() for w in re.split(r"[,/\s]+", (keywords or "").lower()) if w.strip()]
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        t = term.strip().lower()
        if t and t not in seen:
            seen.add(t)
            terms.append(t)

    joined = " ".join(raw)
    for topic, aliases in TOPIC_ALIASES.items():
        if topic in joined or any(topic in r or r in topic for r in raw):
            for alias in aliases:
                add(alias)

    for r in raw:
        add(r)
    if joined:
        add(joined)

    return terms or [keywords.strip().lower()] if keywords else []


def _field_text(club: dict) -> str:
    category = club.get("category") or []
    tags = club.get("tags") or []
    if isinstance(category, list):
        cat_str = " ".join(str(c) for c in category)
    else:
        cat_str = str(category)
    if isinstance(tags, list):
        tag_str = " ".join(str(t) for t in tags)
    else:
        tag_str = str(tags)
    return " ".join(
        [
            (club.get("name") or ""),
            (club.get("description") or ""),
            cat_str,
            tag_str,
        ]
    ).lower()


def score_club(club: dict, terms: list[str]) -> int:
    text = _field_text(club)
    name = (club.get("name") or "").lower()
    score = 0
    for term in terms:
        if not term:
            continue
        if term in name:
            score += 10
        if name.startswith(term) or term in name.split():
            score += 5
        if term in text:
            score += 3
        # Category/tag exact phrase (e.g. "computer science" in STEM category names)
        for cat in (club.get("category") or []) + (club.get("tags") or []):
            cat_l = str(cat).lower()
            if term in cat_l:
                score += 6
    return score


def rank_clubs(clubs: Iterable[dict], terms: list[str], limit: int = CLUB_LIST_LIMIT) -> list[dict]:
    scored = [(score_club(c, terms), c) for c in clubs]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda x: (-x[0], (x[1].get("name") or "").lower()))
    if scored:
        return [c for _, c in scored[:limit]]
    # No positive scores — return input clubs capped (e.g. API order)
    return list(clubs)[:limit]


def extract_social_links(html_or_text: str) -> dict[str, str]:
    """Pull Instagram (and generic website) URLs from org HTML descriptions."""
    links: dict[str, str] = {}
    text = html_or_text or ""

    for match in INSTAGRAM_RE.finditer(text):
        handle = match.group(1).rstrip("/")
        if handle and handle not in ("p", "reel", "stories"):
            links["instagram"] = f"https://www.instagram.com/{handle}/"
            break

    for href in HREF_RE.findall(text):
        href_l = href.lower()
        if "instagram.com" in href_l and "instagram" not in links:
            m = INSTAGRAM_RE.search(href)
            if m:
                links["instagram"] = f"https://www.instagram.com/{m.group(1)}/"
        elif href.startswith("http") and "campuslabs.com" not in href_l and "website" not in links:
            if "instagram.com" not in href_l and "facebook.com" not in href_l:
                links["website"] = href

    return links


def normalize_instagram_url(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    v = str(value).strip()
    if v.startswith("http"):
        return v if "instagram.com" in v else None
    handle = v.lstrip("@")
    return f"https://www.instagram.com/{handle}/" if handle else None


def get_instagram_link(club: dict) -> str | None:
    links = club.get("links") or {}
    url = normalize_instagram_url(links.get("instagram"))
    if url:
        return url
    # Fallback: parse description if scraper has not refreshed links yet
    found = extract_social_links(club.get("description") or "")
    return found.get("instagram")
