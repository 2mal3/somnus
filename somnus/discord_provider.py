import discord
from discord.ext import commands

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.logic import start, stop, utils
from somnus.logic.world_selecter import check_world_selecter_json, get_current_world, create_new_world, edit_new_world, delete_world, get_all_data

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    if bot.user is None:
        return
    await check_world_selecter_json()
    await bot.change_presence(status=discord.Status.dnd)
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="ping", description="Replies with Pong!")
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message("Pong!")  # type: ignore


@bot.tree.command(name="start", description="Starts the server")
async def start_server_command(ctx: discord.Interaction):
    start_steps = 20
    message = "Starting Server ..."

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, start_steps, message))  # type: ignore
    old_presence = bot.status
    log.info(bot.status)
    await bot.change_presence(status=discord.Status.idle)

    i = 0
    try:
        async for _ in start.start_server():
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, start_steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await bot.change_presence(status=old_presence)
            return
        log.error(f"Could not start server | {e}")
        await ctx.edit_original_response(content=f"Could not start server\n-# ERROR: {e}", )
        await bot.change_presence(status=old_presence)
        return

    log.info("Server started!")
    await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
    await ctx.channel.send("Server started!")  # type: ignore
    await bot.change_presence(status=discord.Status.online)
    log.info("Server started Messages sent!")


def _generate_progress_bar(value: int, max_value: int, message: str) -> str:
    progress = "█" * value + "░" * (max_value - value)
    return f"{message}\n{progress}"


@bot.tree.command(name="stop", description="Stops the server")
async def stop_server_command(ctx: discord.Interaction):
    stop_steps = 10
    message = "Stopping Server ..."

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore
    old_presence = bot.status
    await bot.change_presence(status=discord.Status.idle)

    i = 0
    try:
        async for _ in stop.stop_server():
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, stop_steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await bot.change_presence(status=old_presence)
            return
        log.error(f"Could not stop server | {e}")
        await ctx.edit_original_response(content=f"Could not stop server\n-# ERROR: {e}")
        await bot.change_presence(status=old_presence)
        return

    log.info("Server stopped!")
    #await ctx.edit_original_response(content="Server stopped!")
    await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
    await ctx.channel.send("Server stopped!")  # type: ignore
    await bot.change_presence(status=discord.Status.dnd)
    log.info("Server stopped Messages sent!")


@bot.tree.command(name="create_world", description="SUPER-USER-ONLY: Creates a new reference to an installed Minecraft installation")
#@app_commands.describe(display_name="Name that can be selected for all to see in Discord", start_cmd="Command that starts the Minecraft server on the server", sudo_start_cmd="True/False, whether the start command should be executed with sudo rights", visible="True/False, whether other people can select this world")
async def create_world_command(ctx: discord.Interaction, display_name: str, start_cmd: str, sudo_start_cmd: bool, visible: bool):
    if ctx.user.id != Config.DISCORD_SUPER_USER_ID:
        await ctx.response.send_message("Nein", ephemeral=True)
        return
    
    # Erstelle ein Dropdown-Menü
    options = [
        discord.SelectOption(label="1", value="1"),
        discord.SelectOption(label="2", value="2"),
        discord.SelectOption(label="3", value="3")
    ]

    select = discord.ui.Select(placeholder="Wähle eine Zahl...", options=options)

    async def select_callback(select_interaction: discord.Interaction):
        selected_value = select.values[0]
        await ctx.response.send_message(f"Du hast {selected_value} ausgewählt.")
        # Führe hier deine Methode basierend auf der Auswahl aus
        log.debug(f"Dropdown: {selected_value}")
        #await execute_based_on_selection(selected_value)

    select.callback = select_callback

    view = discord.ui.View()
    view.add_item(select)

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message("Bitte wähle eine Zahl:", view=view)




def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
