import discord

from somnus.actions import stats


def edit_error_for_discord_subtitle(err: Exception) -> str:
    msg = (str(err) or "").strip()
    if msg:
        return str(msg).replace("\n", "\n-# ")
    else:
        return f"No error message. Error type: '{type(err).__name__}'"


def generate_progress_bar(value: int, max_value: int, message: str = "") -> str:
    if value < 0:
        raise ValueError("value must be larger than 0")
    progress = "█" * value + "░" * (max_value - value)
    if message:
        return f"{message}\n{progress}"
    return progress


async def ping_user_after_error(ctx: discord.Interaction) -> None:
    user_mention = ctx.user.mention
    await ctx.followup.send(content=f"{user_mention}", ephemeral=False)
