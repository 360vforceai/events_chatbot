"""Discord thread + slash handlers for coach sessions."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import discord

from app.services.coach_agent import run_coach_turn, start_coach_session
from app.config import settings
from app.services.coach_session_service import (
    attach_thread,
    end_session,
    get_session,
    get_session_by_thread,
    resume_session,
    session_status_text,
    start_session,
)
from discord_bot.mention_utils import goal_from_mention, strip_bot_mention, thread_name_for
from discord_bot.utils.message_utils import split_message
from discord_bot.utils.rate_limiter import get_remaining_seconds, is_rate_limited, record_request

logger = logging.getLogger("discord_bot")


async def _post_coach_reply(thread: discord.Thread, reply: str, *, thinking_msg: discord.Message | None = None):
    chunks = split_message(reply)
    if not chunks:
        return
    if thinking_msg:
        await thinking_msg.edit(content=chunks[0])
        for chunk in chunks[1:]:
            await thread.send(chunk)
    else:
        for chunk in chunks:
            await thread.send(chunk)


async def _run_first_turn_in_thread(
    thread: discord.Thread,
    session,
    *,
    first_user_message: str | None = None,
):
    thinking = await thread.send("_Thinking…_")
    if first_user_message:
        reply = await run_coach_turn(session, first_user_message)
    else:
        reply = await start_coach_session(session)
    await _post_coach_reply(thread, reply, thinking_msg=thinking)


async def open_coach_thread(
    *,
    channel: discord.abc.Messageable,
    user_id: str,
    username: str,
    goal: str,
    thread_name: str,
    create_thread: Callable[[], Awaitable[discord.Thread]],
) -> discord.Thread | None:
    """Start session + thread. `create_thread` is async () -> Thread."""
    session = start_session(user_id=user_id, username=username, goal=goal)
    try:
        thread = await create_thread()
    except discord.HTTPException as e:
        logger.error("Could not create coach thread: %s", e)
        end_session(user_id, reason="replaced")
        return None

    attach_thread(user_id, thread.id, getattr(channel, "id", None))
    await thread.send(
        f"**Coach session** — chat here without tagging me again.\n"
        f"_Goal:_ {goal}\n"
        f"_Memory saved · auto-pauses after {settings.coach_session_idle_minutes} min idle · "
        f"`/end_session` to close · `/session` for status_"
    )
    await _run_first_turn_in_thread(thread, session, first_user_message=goal)
    logger.info("Coach thread opened userId=%s thread=%s", user_id, thread.id)
    return thread


async def handle_find(
    interaction: discord.Interaction,
    user_id: str,
    username: str,
    goal: str,
):
    async def _create():
        return await interaction.channel.create_thread(
            name=thread_name_for(username, goal),
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440,
            reason="S.E.E.R. coach session",
        )

    thread = await open_coach_thread(
        channel=interaction.channel,
        user_id=user_id,
        username=username,
        goal=goal,
        thread_name=thread_name_for(username, goal),
        create_thread=_create,
    )
    if not thread:
        await interaction.followup.send(
            "Could not create a thread here. Use `/continue` or @mention me in a channel with threads enabled.",
            ephemeral=True,
        )
        return

    await interaction.edit_original_response(
        content=f"**Coach session started** — continue in {thread.mention}\n_Goal:_ {goal}"
    )


async def handle_continue(
    interaction: discord.Interaction,
    user_id: str,
    message: str,
):
    session = get_session(user_id)
    resumed = False
    if not session:
        session = resume_session(user_id)
        resumed = session is not None
    if not session:
        await interaction.followup.send(
            "No active session. @mention me in a channel, or use `/find <goal>`.",
            ephemeral=True,
        )
        return

    reply = await run_coach_turn(session, message)
    if resumed:
        reply = (
            f"_Resumed your saved session (goal: {session.goal}). "
            f"Auto-ends after {settings.coach_session_idle_minutes} min idle._\n\n{reply}"
        )
    await interaction.edit_original_response(content=reply[:2000])
    for chunk in split_message(reply)[1:]:
        await interaction.followup.send(chunk)

    if session.thread_id:
        thread = interaction.client.get_channel(session.thread_id)
        if thread:
            try:
                await thread.send(f"**You:** {message[:500]}\n\n{reply[:1900]}")
            except Exception as e:
                logger.warning("Could not mirror to coach thread: %s", e)

    logger.info("Coach continue userId=%s turns=%s", user_id, session.turn_count)


async def handle_session_status(interaction: discord.Interaction, user_id: str):
    session = get_session(user_id)
    if not session:
        await interaction.edit_original_response(
            content="No active coach session. @mention me in a channel or use `/find <goal>`."
        )
        return
    await interaction.edit_original_response(content=session_status_text(session))


async def handle_end_session(interaction: discord.Interaction, user_id: str):
    session = end_session(user_id)
    if not session:
        await interaction.edit_original_response(content="No active session to end.")
        return
    await interaction.edit_original_response(
        content=f"Session ended. Goal was: _{session.goal}_\n@mention me or `/find` to start again."
    )
    logger.info("Coach session ended userId=%s", user_id)


async def notify_session_idle_ended(session, client: discord.Client):
    if not session.thread_id:
        return
    channel = client.get_channel(session.thread_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(session.thread_id)
        except Exception:
            return
    try:
        mins = settings.coach_session_idle_minutes
        await channel.send(
            f"⏱️ Session paused after **{mins} minutes** with no messages. "
            f"Your chat is saved — reply here, use `/continue`, or @mention me to start fresh."
        )
    except Exception as e:
        logger.warning("Idle session notify failed: %s", e)


def _user_text(message: discord.Message, bot_user: discord.ClientUser | None) -> str:
    text = (message.content or "").strip()
    if bot_user:
        text = strip_bot_mention(text, bot_user.id)
    return text


async def handle_mention_in_channel(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    """
    @mention in a public channel → create a thread on that message and start coaching.
    Keeps the main channel clean; chat continues in the thread without re-tagging.
    """
    if bot_user not in message.mentions:
        return False
    if isinstance(message.channel, discord.Thread):
        return False
    if not isinstance(message.channel, discord.TextChannel):
        return False

    user_id = str(message.author.id)
    if is_rate_limited(user_id):
        remaining = get_remaining_seconds(user_id)
        await message.reply(
            f"Please wait {remaining}s before starting another session.",
            mention_author=False,
        )
        return True

    existing = get_session(user_id) or resume_session(user_id)
    if existing and existing.thread_id:
        thread = message.guild.get_channel(existing.thread_id) if message.guild else None
        if thread is None:
            try:
                thread = await message.client.fetch_channel(existing.thread_id)
            except Exception:
                thread = None
        if thread:
            await message.reply(
                f"You already have an active session in {thread.mention}. "
                "Keep chatting there (no need to tag me), or `/end_session` first.",
                mention_author=False,
            )
            return True

    goal = goal_from_mention(message.content or "", bot_user.id)
    record_request(user_id)

    async def _create():
        return await message.create_thread(
            name=thread_name_for(message.author.name, goal),
            auto_archive_duration=1440,
            reason="S.E.E.R. mention → coach thread",
        )

    thread = await open_coach_thread(
        channel=message.channel,
        user_id=user_id,
        username=message.author.name,
        goal=goal,
        thread_name=thread_name_for(message.author.name, goal),
        create_thread=_create,
    )
    if not thread:
        await message.reply(
            "I couldn't open a thread here — enable **threads** on this channel or use `/find`.",
            mention_author=False,
        )
        return True

    await message.add_reaction("✅")
    return True


async def handle_coach_thread_message(
    message: discord.Message,
    bot_user: discord.ClientUser | None = None,
) -> bool:
    """Reply to messages in an active coach thread (no @mention needed)."""
    if message.author.bot or not isinstance(message.channel, discord.Thread):
        return False

    session = get_session_by_thread(message.channel.id)
    if not session:
        session = resume_session(str(message.author.id))
        if not session or session.thread_id != message.channel.id:
            return False

    if str(message.author.id) != session.user_id:
        await message.reply(
            f"This thread is **{session.username}**'s session. "
            f"@mention me in the main channel to start your own thread.",
            mention_author=False,
        )
        return True

    text = _user_text(message, bot_user)
    if not text:
        return False

    if is_rate_limited(str(message.author.id)):
        return True
    record_request(str(message.author.id))

    async with message.channel.typing():
        reply = await run_coach_turn(session, text)

    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)
    return True


async def handle_channel_message(message: discord.Message, bot_user: discord.ClientUser):
    """Route channel @mentions → new thread; existing coach threads → continue chat."""
    if await handle_mention_in_channel(message, bot_user):
        return
    await handle_coach_thread_message(message, bot_user)
