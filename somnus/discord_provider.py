import discord
#from discord.ext import commands
from discord import app_commands

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.logic import start, stop, utils, world_selecter

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
guild_id = 910195152490999878

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="booting"))
    await tree.sync(guild=discord.Object(id=guild_id))  # Sync the command tree with Discord
    await bot.change_presence(status=discord.Status.dnd)
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await world_selecter.check_world_selecter_json()
    await _updateStatus()


@tree.command(name="ping", description="Replies with Pong!")
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message("Pong!")  # type: ignore


@tree.command(name="start", description="Starts the server")
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


@tree.command(name="stop", description="Stops the server")
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


#@app_commands.describe(display_name="Name that can be selected for all to see in Discord", start_cmd="Command that starts the Minecraft server on the server", sudo_start_cmd="True/False, whether the start command should be executed with sudo rights", visible="True/False, whether other people can select this world")



# @tree.command(name="pinging", description="Replies with Pong!", guild=discord.Object(id=guild_id))
# async def pinging_command(ctx: discord.Interaction):
#     await ctx.response.send_message("Pong!")  # type: ignore


@tree.command(name="createworld", description="SUPER-USER-ONLY: Creates a new reference to an installed Minecraft installation", guild=discord.Object(id=910195152490999878))
async def create_world_command(ctx: discord.Interaction, display_name: str, start_cmd: str, sudo_start_cmd: bool, visible: bool):
    log.debug(f"Createworld von User {ctx.user.id}. SUDO ist {CONFIG.DISCORD_SUPER_USER_ID}")
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message("Nein", ephemeral=True)
        return
    
    if await world_selecter.create_new_world(display_name, start_cmd, sudo_start_cmd, visible):
        await ctx.response.send_message(f"The world '{display_name}' was created succesfully!", ephemeral=True)
    else:
        await ctx.response.send_message(f"Couldn't create the world '{display_name}'", ephemeral=True)
    

@tree.command(name="changeworld", description="Changes the current world into another visible world", guild=discord.Object(id=910195152490999878))
async def create_world_command(ctx: discord.Interaction):
    data = await world_selecter.get_all_data()
    index = 0
    options = []
    for world in data["worlds"]:
        if world["visible"] == True:
            if world["display_name"] == data["current_world"]:
                index = len(options)
            options.append(discord.SelectOption(label=world["display_name"], value=world["display_name"]))

    select = discord.ui.Select(placeholder="Choose the world you want to play", min_values=1, max_values=1, options=options)
    select.options[index].default = True

    async def select_callback(select_interaction: discord.Interaction):
        selected_value = select.values[0]
        await world_selecter.change_world(selected_value)
        await select_interaction.channel.send(f"'{selected_value}' was selected succusfully!")

    select.callback = select_callback

    view = discord.ui.View()
    view.add_item(select)

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message("Choose the world you want to play:", view=view)


async def _updateStatus(string = ""):
    if string != "":
        current_world_name = (await world_selecter.get_current_world())["display_name"]
        server_status = await utils.get_server_state(CONFIG)

        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            string = f"{current_world_name}"

        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            string = f"Starting/Stopping, current World: '{current_world_name}'"

        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            string = f"/start to play Minecraft in '{current_world_name}'. /changeworld to change to another world."

    await bot.change_presence(activity=discord.Game(name=string))





def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN,) #log_handler=None)


if __name__ == "__main__":
    main()
