import discord

from somnus.actions import stats
from somnus.config import CONFIG
from somnus.discord_provider.bot import bot
from somnus.discord_provider.busy_provider import busy_provider
from somnus.language_handler import LH
from somnus.logic import world_selector


async def update_bot_presence() -> None:
    world_selector_config = await world_selector.get_world_selector_config()
    server_status = await stats.get_server_state(CONFIG)

    if busy_provider.is_busy():
        return

    if server_status.mc_server_running:
        # Online
        mc_status = await stats.get_mcstatus(CONFIG)
        if not mc_status:
            text = LH(
                "status.text.online",
                args={"world_name": world_selector_config.current_world, "players_online": "X", "max_players": "Y"},
            )
        else:
            text = LH(
                "status.text.online",
                args={
                    "world_name": world_selector_config.current_world,
                    "players_online": mc_status.players.online,
                    "max_players": mc_status.players.max,
                },
            )
        activity = discord.Game(name=text)

    elif server_status.host_server_running:
        # Only Host online
        text = LH("status.text.only_host_online", args={"world_name": world_selector_config.current_world})
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
    else:
        # Offline
        text = LH("status.text.offline", args={"world_name": world_selector_config.current_world})
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)

    status = _map_server_status_to_discord_activity(server_status)

    await bot.change_presence(status=status, activity=activity)


def _map_server_status_to_discord_activity(server_status: stats.ServerState) -> discord.Status:
    if not server_status.host_server_running:
        return discord.Status.dnd
    # After here the host server is running
    elif not server_status.mc_server_running:
        return discord.Status.idle
    else:
        return discord.Status.online
