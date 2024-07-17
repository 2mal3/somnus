import discord
from discord.ext import commands

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.logic import start, stop, utils

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    if bot.user is None:
        return
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="ping", description="Replies with Pong!")
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message("Pong!")  # type: ignore


@bot.tree.command(name="start", description="Starts the server")
async def start_server_command(ctx: discord.Interaction):
    start_steps = 10
    message = "Starting Server ..."

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, start_steps, message))  # type: ignore

    i = 0
    try:
        async for _ in start.start_server():
            i += 1
            await ctx.edit_original_response(content=_generate_progress_bar(i, start_steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            return
        log.error(f"Could not start server | {e}")
        await ctx.edit_original_response(content=f"Could not start server\n-# ERROR: {e}", )
        return

    log.info("Server started!")
    await ctx.edit_original_response(content="Server started!")


def _generate_progress_bar(value: int, max_value: int, message: str) -> str:
    progress = "█" * value + "░" * (max_value - value)
    return f"{message}\n{progress}"


@bot.tree.command(name="stop", description="Stops the server")
async def stop_server_command(ctx: discord.Interaction):
    stop_steps = 10
    message = "Stopping Server ..."

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    i = 0
    try:
        async for _ in stop.stop_server():
            i += 1
            await ctx.edit_original_response(content=_generate_progress_bar(i, stop_steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            return
        log.error(f"Could not stop server | {e}")
        await ctx.edit_original_response(content=f"Could not stop server\n-# ERROR: {e}")
        return

    log.info("Server stopped!")
    await ctx.edit_original_response(content="Server stopped!")


def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
