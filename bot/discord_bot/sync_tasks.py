"""Background loops: sync Supabase, refresh live event cache, optional Discord announcements."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import discord
from discord.ext import tasks

from app.config import settings
from app.services import data_sync, live_events_cache
from app.services.coach_session_service import collect_idle_sessions, end_session
from app.scrapers.getinvolved import fetch_upcoming_events
from discord_bot import club_cache
from discord_bot.coach_handler import notify_session_idle_ended

logger = logging.getLogger("discord_bot")

_bot_client: discord.Client | None = None
_known_event_ids: set[str] = set()
_announce_initialized = False


def _sync_interval_minutes() -> int:
    if getattr(settings, "data_sync_interval_minutes", 0) > 0:
        return settings.data_sync_interval_minutes
    return max(15, settings.scrape_interval_hours * 60)


@tasks.loop(minutes=30)
async def periodic_data_sync():
    await _run_sync_and_notify()


@tasks.loop(minutes=10)
async def periodic_live_events_refresh():
    await live_events_cache.refresh()


@tasks.loop(minutes=1)
async def periodic_coach_idle_check():
    if not _bot_client:
        return
    for session in collect_idle_sessions():
        end_session(session.user_id, reason="idle")
        await notify_session_idle_ended(session, _bot_client)
        logger.info("Coach session idle-ended userId=%s", session.user_id)


async def _run_sync_and_notify():
    try:
        stats = await asyncio.to_thread(data_sync.run_full_sync)
        club_cache.invalidate()
        await live_events_cache.refresh()
        await _maybe_announce_new_events()
        return stats
    except Exception as e:
        logger.error("Periodic sync failed: %s", e)


async def _maybe_announce_new_events():
    global _announce_initialized, _known_event_ids

    channel_id = (settings.discord_updates_channel_id or "").strip()
    if not channel_id or not settings.discord_announce_new_events or not _bot_client:
        return

    channel = _bot_client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await _bot_client.fetch_channel(int(channel_id))
        except Exception as e:
            logger.warning("Updates channel %s not found: %s", channel_id, e)
            return

    upcoming = await asyncio.to_thread(fetch_upcoming_events, 40)
    cutoff = date.today()
    horizon = cutoff + timedelta(days=14)
    relevant = []
    for e in upcoming:
        try:
            d = date.fromisoformat(e.get("date", ""))
        except ValueError:
            continue
        if cutoff <= d <= horizon:
            relevant.append(e)

    if not _announce_initialized:
        _known_event_ids = {e["event_id"] for e in relevant if e.get("event_id")}
        _announce_initialized = True
        logger.info("Event announce baseline set (%s ids)", len(_known_event_ids))
        return

    new_events = [e for e in relevant if e.get("event_id") not in _known_event_ids]
    _known_event_ids.update(e.get("event_id") for e in relevant if e.get("event_id"))

    if not new_events:
        return

    for event in new_events[:6]:
        title = event.get("title", "New event")
        when = f"{event.get('date')} {event.get('time', '')}".strip()
        loc = event.get("location", "TBD")
        club = event.get("club_name", "")
        rsvp = event.get("rsvp_link", "")
        desc = f"**When:** {when}\n**Where:** {loc}"
        if club:
            desc += f"\n**Host:** {club}"
        embed = discord.Embed(
            title="📅 New Rutgers event",
            description=desc[:4096],
            color=0xCC0033,
            url=rsvp or None,
        )
        embed.add_field(name=title[:256], value="Just listed on getINVOLVED", inline=False)
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error("Failed to post event announcement: %s", e)


def start_background_tasks(client: discord.Client):
    global _bot_client
    _bot_client = client

    periodic_data_sync.change_interval(minutes=_sync_interval_minutes())
    periodic_live_events_refresh.change_interval(
        minutes=max(5, settings.live_events_cache_minutes)
    )

    if not periodic_data_sync.is_running():
        periodic_data_sync.start()
    if not periodic_live_events_refresh.is_running():
        periodic_live_events_refresh.start()
    if not periodic_coach_idle_check.is_running():
        periodic_coach_idle_check.start()

    logger.info(
        "Background tasks started (sync every %s min, live cache every %s min, coach idle %s min)",
        _sync_interval_minutes(),
        settings.live_events_cache_minutes,
        settings.coach_session_idle_minutes,
    )


async def run_initial_sync():
    await live_events_cache.refresh()
    await _run_sync_and_notify()
