import discord
from somnus.actions import stats

def edit_error_for_discord_subtitle(err: Exception) -> str:
    msg = (str(err) or "").strip()
    if msg:
        return str(msg).replace("\n", "\n-# ")
    else:
        return f"No error message. Error type: '{type(err).__name__}'"


def generate_progress_bar(value: int, max_value: int, message: str = "") -> str:
    if value < 0 or value > max_value:
        raise ValueError(f"value must be between 0 and {max_value}, got {value}")
    progress = "█" * value + "░" * (max_value - value)
    if message:
        return f"{message}\n{progress}"
    return progress

def map_server_status_to_discord_activity(server_status: stats.ServerState) -> discord.Status:
    if not server_status.host_server_running:
        return discord.Status.dnd
    # After here the host server is running
    elif not server_status.mc_server_running:
        return discord.Status.idle
    else:
        return discord.Status.online
