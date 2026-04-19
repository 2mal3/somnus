import asyncio

import discord

from somnus.actions import stats
from somnus.config import CONFIG
from somnus.discord_provider.action_warpper import ActionWrapperProperties, action_wrapper
from somnus.discord_provider.bot import bot
from somnus.discord_provider.busy_provider import busy_provider
from somnus.language_handler import LH
from somnus.logger import log
from somnus.logic import stop, world_selector


class InactivityProvider:
    def __init__(self) -> None:
        self.inactivity_seconds = 0


inactivity_provider = InactivityProvider()


async def check_and_shutdown_for_inactivity() -> None:
    server_status = await stats.get_server_state(CONFIG)

    if not server_status.mc_server_running:
        return

    mc_status = await stats.get_mcstatus(CONFIG)
    if not mc_status:
        log.warning("Could not get mcstatus for inactivity shutdown check!")
        return

    if mc_status.players.online == 0:
        if inactivity_provider.inactivity_seconds >= 0:
            if inactivity_provider.inactivity_seconds == 0:
                await _stop_inactivity()
            inactivity_provider.inactivity_seconds -= 10
    else:
        inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60


async def _inactivity_shutdown_verification(channel: discord.TextChannel) -> bool:
    result_future = asyncio.Future()

    cancel_button = discord.ui.Button(label=LH("other.inactivity_shutdown.cancel"), style=discord.ButtonStyle.green)

    async def cancel_callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        cancel_button.disabled = True
        inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
        await message.edit(
            content=LH(
                "other.inactivity_shutdown.canceled",
                args={"inactivity_shutdown_minutes": CONFIG.INACTIVITY_SHUTDOWN_MINUTES},
            ),
            view=view,
        )
        result_future.set_result(False)
        view.stop()

    cancel_button.callback = cancel_callback  # ty: ignore

    view = discord.ui.View()
    view.add_item(cancel_button)

    message = await channel.send(
        content=LH(
            "other.inactivity_shutdown.verification",
            args={"inactivity_shutdown_minutes": CONFIG.INACTIVITY_SHUTDOWN_MINUTES},
        ),
        view=view,
    )

    try:
        await asyncio.wait_for(view.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        if not result_future.done():
            result_future.set_result(True)
            cancel_button.disabled = True
            await message.edit(content=LH("other.inactivity_shutdown.stopping"), view=view)
    finally:
        result = await result_future
        await message.delete()
        return result


async def _stop_inactivity() -> None:
    if not CONFIG.DISCORD_STATUS_CHANNEL_ID:
        log.error(
            "DISCORD_STATUS_CHANNEL_ID in .env.test not correct. Automatic shutdown due to inactivity not possible!"
        )
        return
    channel = bot.get_channel(CONFIG.DISCORD_STATUS_CHANNEL_ID)
    if not channel or not isinstance(channel, discord.TextChannel):
        raise TypeError("Could not get channel from Discord!")

    log.info("Send information message for shutdown due to inactivity ...")
    player_confirmed_stop = await _inactivity_shutdown_verification(channel)
    if not player_confirmed_stop:
        inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
        return
    log.info("Stopping due to inactivity ...")

    # Just stop doing anything when the server should not be stopped, doesnt print any message to reduce clutter
    mcstatus = await stats.get_mcstatus(CONFIG)
    if mcstatus is None:
        log.debug("Could not get mcstatus for inactivity shutdown check, skipping shutdown!")
        return
    if mcstatus.players.online != 0:
        log.debug("Players came online during inactivity shutdown verification, skipping shutdown!")
        return

    world_config = await world_selector.get_world_selector_config()
    activity = discord.Game(name=LH("status.text.stopping", args={"world_name": world_config.current_world}))
    await bot.change_presence(status=discord.Status.idle, activity=activity)

    message = await channel.send(content=LH("other.inactivity_shutdown.stopping"))

    busy_provider.make_busy()
    try:
        async for _ in stop.stop_server(True, CONFIG):
            pass
    except Exception as e:
        log.error("Failed to stop server during inactivity shutdown", exc_info=e)
        inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
        await message.edit(content=LH("commands.stop.error.general", args={"e": e}))
    else:
        await message.edit(content=LH("other.inactivity_shutdown.finished_msg"))
    finally:
        busy_provider.make_available()
