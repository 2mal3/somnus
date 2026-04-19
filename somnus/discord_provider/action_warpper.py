from typing import AsyncGenerator, Callable

import discord
from pydantic import BaseModel, ConfigDict

from somnus.discord_provider.bot import TOTAL_PROGRESS_BAR_STEPS, bot
from somnus.discord_provider.busy_provider import busy_provider
from somnus.discord_provider.utils import (
    edit_error_for_discord_subtitle,
    generate_progress_bar,
    ping_user_after_error,
)
from somnus.language_handler import LH
from somnus.logger import log
from somnus.logic import errors


class ActionWrapperProperties(BaseModel):
    func: Callable[..., AsyncGenerator]
    ctx: discord.Interaction
    activity: str
    progress_message: str
    finish_message: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def action_wrapper(props: ActionWrapperProperties) -> None:
    """
    Wraps a long running, server specifc and potientially error prone task.
    Provides busy check, error handling, progress bar and bot presence.
    """

    if busy_provider.is_busy():
        await props.ctx.response.send_message(LH("other.busy"), ephemeral=True)
        return

    log.info(props.progress_message)
    busy_provider.make_busy()

    await bot.change_presence(status=discord.Status.idle, activity=discord.Game(name=props.activity))

    i = 0
    message_content = generate_progress_bar(i, TOTAL_PROGRESS_BAR_STEPS, props.progress_message)

    if props.ctx.response.is_done():
        await props.ctx.edit_original_response(content=message_content)
    else:
        await props.ctx.response.send_message(content=message_content)

    try:
        async for _ in props.func():
            i += 1
            await props.ctx.edit_original_response(
                content=generate_progress_bar(i, TOTAL_PROGRESS_BAR_STEPS, props.progress_message)
            )
    except errors.UserInputError as e:
        await props.ctx.edit_original_response(content=str(e))
        raise RuntimeError

    except Exception as e:
        log.error("Failed to run action", exc_info=e)
        await props.ctx.edit_original_response(
            content=LH("commands.general_error", args={"e": edit_error_for_discord_subtitle(e)})
        )
        await ping_user_after_error(props.ctx)
        raise RuntimeError("Failed to run action") from e

    else:
        log.info(props.finish_message)
        await props.ctx.edit_original_response(
            content=generate_progress_bar(TOTAL_PROGRESS_BAR_STEPS, TOTAL_PROGRESS_BAR_STEPS, props.progress_message)
        )
        await props.ctx.channel.send(props.finish_message)  # type: ignore

    finally:
        busy_provider.make_available()
