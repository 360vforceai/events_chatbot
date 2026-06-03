"""Discord thread + slash handlers for coach sessions."""

from __future__ import annotations

import logging

import discord

from app.services.coach_agent import run_coach_turn, start_coach_session
from app.services.coach_session_service import (
    attach_thread,
    end_session,
    get_session,
    get_session_by_thread,
    session_status_text,
    start_session,
)
from discord_bot.utils.message_utils import split_message

logger = logging.getLogger("discord_bot")


async def handle_find(
    interaction: discord.Interaction,
    user_id: str,
    username: str,
    goal: str,
):
    session = start_session(user_id=user_id, username=username, goal=goal)

    thread_name = f"find-{username}"[:90]
    try:
        thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=60,
            reason="S.E.E.R. coach session",
        )
    except discord.HTTPException as e:
        logger.error("Could not create coach thread: %s", e)
        await interaction.followup.send(
            "Could not create a thread here. Use `/continue` in this channel instead, "
            "or run `/find` in a text channel that allows threads.",
            ephemeral=True,
        )
        return

    attach_thread(user_id, thread.id, interaction.channel_id)
    await interaction.edit_original_response(
        content=f"**Coach session started** — continue in {thread.mention}\n_Goal:_ {goal}"
    )

    thinking = await thread.send("_Thinking…_")
    reply = await start_coach_session(session)
    chunks = split_message(reply)
    await thinking.edit(content=chunks[0])
    for chunk in chunks[1:]:
        await thread.send(chunk)
    logger.info("Coach session started userId=%s thread=%s", user_id, thread.id)


async def handle_continue(
    interaction: discord.Interaction,
    user_id: str,
    message: str,
):
    session = get_session(user_id)
    if not session:
        await interaction.followup.send(
            "No active session. Start one with `/find <goal>` — e.g. "
            "`/find cheap concert this weekend under $40`",
            ephemeral=True,
        )
        return

    reply = await run_coach_turn(session, message)
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
            content="No active coach session. Use `/find <goal>` to start one."
        )
        return
    await interaction.edit_original_response(content=session_status_text(session))


async def handle_end_session(interaction: discord.Interaction, user_id: str):
    session = end_session(user_id)
    if not session:
        await interaction.edit_original_response(content="No active session to end.")
        return
    await interaction.edit_original_response(
        content=f"Session ended. Goal was: _{session.goal}_\nStart again anytime with `/find`."
    )
    logger.info("Coach session ended userId=%s", user_id)


async def handle_coach_thread_message(message: discord.Message) -> bool:
    """Returns True if the message was handled as a coach turn."""
    if message.author.bot or not isinstance(message.channel, discord.Thread):
        return False

    session = get_session_by_thread(message.channel.id)
    if not session:
        return False
    if str(message.author.id) != session.user_id:
        return False
    if not message.content or not message.content.strip():
        return False

    async with message.channel.typing():
        reply = await run_coach_turn(session, message.content.strip())

    for chunk in split_message(reply):
        await message.reply(chunk, mention_author=False)
    return True
