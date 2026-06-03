"""Tri-state ticket price comparison — Ticketmaster reference + all marketplace links."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from app.config import settings
from app.services.ticket_service import TRI_STATE_NOTE, build_purchase_links

logger = logging.getLogger("discord_bot")

TM_EVENTS_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

# Tri-state DMA / metro coverage (comedy clubs → major arenas)
TRI_STATE_SEARCH_MARKETS = [
    {"dmaId": "345", "label": "New York City"},  # NYC
    {"dmaId": "358", "label": "Philadelphia"},
    {"dmaId": "409", "label": "Newark / North NJ"},
]

CATEGORY_CLASSIFICATIONS = {
    "sports": "Sports",
    "concert": "Music",
    "comedy": "Arts & Theatre",
    "theater": "Arts & Theatre",
    "festival": "Miscellaneous",
    "all": None,
}

VENDOR_CHEAP_HINTS = {
    "Gametime": "Often lowest for last-minute resale",
    "SeatGeek": "Deal score — compare before buying",
    "StubHub": "Large inventory — sort by price",
    "Vivid Seats": "Frequent undercut on resale",
    "Ticketmaster": "Official face value / primary",
    "TodayTix": "Best for NYC comedy & theater rush",
}


def _parse_price_ranges(item: dict) -> tuple[float | None, float | None]:
    ranges = item.get("priceRanges") or []
    mins, maxs = [], []
    for pr in ranges:
        if pr.get("min") is not None:
            mins.append(float(pr["min"]))
        if pr.get("max") is not None:
            maxs.append(float(pr["max"]))
    return (min(mins) if mins else None, max(maxs) if maxs else None)


def _parse_tm_listing(item: dict, market_label: str) -> dict | None:
    dates = item.get("dates", {}).get("start", {})
    local_date = dates.get("localDate")
    if not local_date:
        return None

    venues = item.get("_embedded", {}).get("venues", [])
    venue = venues[0] if venues else {}
    venue_name = venue.get("name", "TBD")
    city = venue.get("city", {}).get("name", "")
    state = venue.get("state", {}).get("stateCode", "")
    area = ", ".join(p for p in [city, state] if p) or market_label

    price_min, price_max = _parse_price_ranges(item)
    title = item.get("name", "Event")
    segment = (item.get("classifications") or [{}])[0].get("segment", {}).get("name", "Event")

    return {
        "event_id": f"tm-{item.get('id', title)}",
        "title": title,
        "date": local_date,
        "time": dates.get("localTime", "TBD"),
        "venue": venue_name,
        "area": area,
        "category": segment,
        "price_min": price_min,
        "price_max": price_max,
        "tm_url": item.get("url", ""),
        "search_query": f"{title} tickets {city or market_label}",
        "market": market_label,
    }


def search_tri_state_ticket_listings(
    *,
    keyword: str = "",
    category: str = "all",
    size_per_market: int = 15,
) -> list[dict]:
    """
    Search Ticketmaster across tri-state markets.
    Returns listings with price_min when the API provides it (not all events do).
    """
    api_key = (settings.ticketmaster_api_key or "").strip()
    if not api_key:
        return []

    keyword = (keyword or "").strip()
    classification = CATEGORY_CLASSIFICATIONS.get(category, category)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen: set[str] = set()
    listings: list[dict] = []

    for market in TRI_STATE_SEARCH_MARKETS:
        params = {
            "apikey": api_key,
            "dmaId": market["dmaId"],
            "startDateTime": now,
            "sort": "date,asc",
            "size": size_per_market,
            "countryCode": "US",
        }
        if keyword:
            params["keyword"] = keyword
        if classification:
            params["classificationName"] = classification

        try:
            resp = requests.get(TM_EVENTS_URL, params=params, timeout=14)
            resp.raise_for_status()
            for item in resp.json().get("_embedded", {}).get("events", []):
                eid = item.get("id")
                if not eid or eid in seen:
                    continue
                parsed = _parse_tm_listing(item, market["label"])
                if not parsed:
                    continue
                seen.add(eid)
                listings.append(parsed)
        except Exception as e:
            logger.warning("TM price search failed dma=%s: %s", market["dmaId"], e)

    return listings


def _sort_cheapest_first(listings: list[dict]) -> list[dict]:
    def key(row: dict):
        p = row.get("price_min")
        return (p is None, p if p is not None else 999999, row.get("date", ""))

    return sorted(listings, key=key)


def _parse_budget_max(budget: str | None) -> float | None:
    if not budget:
        return None
    import re

    nums = re.findall(r"\d+(?:\.\d+)?", budget.replace(",", ""))
    if not nums:
        return None
    return float(nums[0])


def _format_listing_row(row: dict, rank: int) -> str:
    title = row.get("title", "Event")
    when = f"{row.get('date')} {row.get('time', '')}".strip()
    venue = row.get("venue", "")
    area = row.get("area", "")
    pmin = row.get("price_min")
    pmax = row.get("price_max")

    if pmin is not None:
        price_str = f"**from ${pmin:.0f}**" + (f" – ${pmax:.0f}" if pmax else "") + " _(Ticketmaster listing)_"
    else:
        price_str = "_Price not listed on Ticketmaster — compare resale sites below_"

    tm = row.get("tm_url")
    tm_link = f" · [Ticketmaster]({tm})" if tm else ""
    lines = [
        f"**{rank}. {title}** — {when}",
        f"_{venue} · {area}_ · {row.get('category', 'Event')}",
        f"💰 {price_str}{tm_link}",
    ]

    vendors = build_purchase_links(row.get("search_query") or title)
    cheap_order = ["Gametime", "SeatGeek", "StubHub", "Vivid Seats", "TodayTix", "Ticketmaster"]
    by_label = {v["label"]: v for v in vendors}
    lines.append("**Compare all sellers** _(lowest often on Gametime/SeatGeek for resale)_")
    for label in cheap_order:
        v = by_label.get(label)
        if v:
            hint = VENDOR_CHEAP_HINTS.get(label, v.get("note", ""))
            lines.append(f"• [{label}]({v['url']}) — _{hint}_")
    return "\n".join(lines)


def format_cheapest_tri_state_report(
    *,
    keyword: str = "",
    category: str = "all",
    budget: str | None = None,
    limit: int = 8,
) -> str:
    """Build a student-facing cheapest-first report across tri-state listings."""
    if not (settings.ticketmaster_api_key or "").strip():
        return (
            "**Tri-state price compare**\n"
            "Add `TICKETMASTER_API_KEY` to `bot/.env` to pull live event prices "
            "(free at developer.ticketmaster.com).\n\n"
            "Without it, use `/tickets` for marketplace search links."
        )

    listings = search_tri_state_ticket_listings(keyword=keyword, category=category)
    if not listings:
        return (
            f"**No Ticketmaster listings found** for _{keyword or 'tri-state events'}_ "
            f"({category}). Try a broader search — e.g. `NBA`, `comedy Newark`, `concert NYC`."
        )

    budget_max = _parse_budget_max(budget)
    if budget_max is not None:
        affordable = [
            L
            for L in listings
            if L.get("price_min") is None or L["price_min"] <= budget_max
        ]
        if affordable:
            listings = affordable
        else:
            listings = _sort_cheapest_first(listings)[:limit]
            return (
                f"**Tri-state tickets** — _{TRI_STATE_NOTE}_\n"
                f"No events with listed prices ≤ **${budget_max:.0f}**. "
                f"Cheapest available right now:\n\n"
                + "\n\n".join(_format_listing_row(r, i) for i, r in enumerate(listings[:limit], 1))
                + "\n\n_Check Gametime/SeatGeek — resale can beat listed TM mins._"
            )

    with_price = [L for L in listings if L.get("price_min") is not None]
    without = [L for L in listings if L.get("price_min") is None]
    sorted_list = _sort_cheapest_first(with_price) + _sort_cheapest_first(without)
    top = sorted_list[:limit]

    kw_line = f" · search: _{keyword}_" if keyword else ""
    parts = [
        f"**Cheapest tri-state tickets** — _{category}{kw_line}_",
        f"_{TRI_STATE_NOTE}_",
        f"_Sorted by lowest Ticketmaster-listed price. "
        f"For NBA Finals-scale events, resale on **Gametime** / **SeatGeek** often beats primary — open every link._\n",
    ]
    for i, row in enumerate(top, 1):
        parts.append(_format_listing_row(row, i))

    no_price_count = len(without)
    if no_price_count:
        parts.append(
            f"\n_{no_price_count} more event(s) had no public TM price — use the compare links on those listings._"
        )
    return "\n\n".join(parts)
