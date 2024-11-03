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
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name="booting"))
    await tree.sync(guild=discord.Object(id=guild_id))  # Sync the command tree with Discord
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await world_selecter.check_world_selecter_json()
    await _updateStatus()


async def _get_world_choices(interaction: discord.Interaction, current: str):
    data = await world_selecter.get_data()
    return [
        app_commands.Choice(name=world["display_name"], value=world["display_name"])
        for world in data["worlds"]
    ]


@tree.command(name="ping", description="Replies with Pong!")
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message("Pong!")  # type: ignore


@tree.command(name="start", description="Starts the server")
async def start_server_command(ctx: discord.Interaction):
    await _updateStatus(discord.Status.idle, "Starting Server")
    start_steps = 20
    message = "Starting Server ..."

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, start_steps, message))  # type: ignore
    old_presence = bot.status
    log.info(bot.status)

    i = 0
    try:
        async for _ in start.start_server():
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, start_steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await _updateStatus(old_presence)
            return
        log.error(f"Could not start server | {e}")
        await ctx.edit_original_response(content=f"Could not start server\n-# ERROR: {e}", )
        await _updateStatus(old_presence)
        return

    log.info("Server started!")
    await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
    await ctx.channel.send("Server started!")  # type: ignore
    await _updateStatus(discord.Status.online)
    log.info("Server started Messages sent!")


def _generate_progress_bar(value: int, max_value: int, message: str) -> str:
    progress = "█" * value + "░" * (max_value - value)
    return f"{message}\n{progress}"


@tree.command(name="stop", description="Stops the server")
async def stop_server_command(ctx: discord.Interaction):
    await _updateStatus(discord.Status.idle, "Stopping Server")
    stop_steps = 10
    message = "Stopping Server ..."

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore
    old_presence = bot.status

    i = 0
    try:
        async for _ in stop.stop_server():
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, stop_steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await _updateStatus(old_presence)
            return
        log.error(f"Could not stop server | {e}")
        await ctx.edit_original_response(content=f"Could not stop server\n-# ERROR: {e}")
        await _updateStatus(old_presence)
        return

    log.info("Server stopped!")
    #await ctx.edit_original_response(content="Server stopped!")
    await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
    await ctx.channel.send("Server stopped!")  # type: ignore
    await _updateStatus(discord.Status.dnd)
    log.info("Server stopped Messages sent!")


@tree.command(name="add_world", description="SUPER-USER-ONLY: Creates a new reference to an installed Minecraft installation", guild=discord.Object(id=910195152490999878))
async def add_world_command(ctx: discord.Interaction, display_name: str, start_cmd: str, sudo_start_cmd: bool, visible: bool):
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message("You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True)
        return
    
    if await world_selecter.create_new_world(display_name, start_cmd, sudo_start_cmd, visible):
        await ctx.response.send_message(f"The world '{display_name}' was created succesfully!", ephemeral=True)
    else:
        await ctx.response.send_message(f"Couldn't create the world '{display_name}'", ephemeral=True)


@tree.command(name="edit_world", description="SUPER-USER-ONLY: Edits a reference to an installed Minecraft installation", guild=discord.Object(id=910195152490999878))
async def edit_world_command(ctx: discord.Interaction, editing_world_name: str, new_display_name: str = None, start_cmd: str = None, sudo_start_cmd: bool = None, visible: bool = None):
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message("You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True)
        return
    
    out = await world_selecter.edit_new_world(editing_world_name, new_display_name, start_cmd, sudo_start_cmd, visible)
    if out != False:
        await ctx.response.send_message(f"The world '{editing_world_name}' was edited succesfully! New values are:{await _get_formatted_world_info_string(out)}", ephemeral=True)
    else:
        await ctx.response.send_message(f"Couldn't edit the world '{editing_world_name}'", ephemeral=True)
edit_world_command.autocomplete("editing_world_name")(_get_world_choices)
    

@tree.command(name="delete_world", description="SUPER-USER-ONLY: Deletes a reference to an installed Minecraft installation", guild=discord.Object(id=910195152490999878))
async def delete_world_command(ctx: discord.Interaction, display_name: str):
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message("You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True)
        return
    
    data = await world_selecter.get_data()
    if display_name == data["current_world"]:
        await ctx.response.send_message("You can't delete the current world. Change the current world with /change_world", ephemeral=True)
        return
    
    world = await world_selecter.search_world(display_name, data)
    if world == False:
        await ctx.response.send_message(f"World '{display_name}' not found.", ephemeral=True)
        return
    
    confirm_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)
    used = False

    async def confirm_callback(interaction: discord.Interaction):
        nonlocal used
        if used:
            await interaction.response.send_message(f"Button inactive, use /delete_world again", ephemeral=True)
        elif await world_selecter.delete_world(display_name):
            await interaction.response.send_message(f"The world '{display_name}' was deleted successfully!", ephemeral=True)
        else:
            await interaction.response.send_message(f"Couldn't delete the world '{display_name}'.", ephemeral=True)
        used = True

    async def cancel_callback(interaction: discord.Interaction):
        nonlocal used
        if used:
            await interaction.response.send_message(f"Button inactive, use /delete_world again", ephemeral=True)
        else:
            used = True
            await interaction.response.send_message("Deletion process canceled", ephemeral=True)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(f"Do you really want to delete the world '{display_name}'?{await _get_formatted_world_info_string(world)}", view=view, ephemeral=True)
delete_world_command.autocomplete("display_name")(_get_world_choices)


@tree.command(name="change_world", description="Changes the current world into another visible world", guild=discord.Object(id=910195152490999878))
async def change_world_command(ctx: discord.Interaction):
    data = await world_selecter.get_data()
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
        if ctx.user.id == select_interaction.user.id:
            selected_value = select.values[0]
            select.disabled = True
            await select_interaction.message.edit(view=view)
            if await world_selecter.change_world(selected_value):
                await select_interaction.response.send_message(f"'{selected_value}' was selected succusfully!")
                await _updateStatus()
            else:
                await select_interaction.response.send_message(f"Couldn't change the world to '{selected_value}'.", ephemeral=True)
        else:
            await select_interaction.response.send_message("You cannot use the menu because it was requested by someone else. Use /change_world to change the world", ephemeral=True)
            

    select.callback = select_callback

    view = discord.ui.View()
    view.add_item(select)

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message("Choose the world you want to play:", view=view)


@tree.command(name="show_worlds", description="Shows all available worlds", guild=discord.Object(id=910195152490999878))
async def show_worlds_command(ctx: discord.Interaction):
    if ctx.user.id == int(CONFIG.DISCORD_SUPER_USER_ID):
        sudo = True
    else:
        sudo = False
    data = await world_selecter.get_data()
    current_world_name = data["current_world"]
    
    max_name_lenght = len(data["worlds"][0]["display_name"])
    for world in data["worlds"]:
        if world["visible"] == True or sudo:
            if len(world["display_name"]) > max_name_lenght:
                max_name_lenght = len(world["display_name"])

    string = "## List of all available worlds \n```"
    for world in data["worlds"]:
        if world["visible"] == True or sudo:
            if world["display_name"] == current_world_name:
                string += f"\n✅ - "
            else:
                string += f"\n⬜ - "

            string += world["display_name"]

            if sudo:
                string += (3+max_name_lenght-len(world["display_name"]))*" " + str(world["visible"])
            
    await ctx.response.send_message(string+"```", ephemeral=sudo)


async def _updateStatus(status = None, string = ""):
    data = await world_selecter.get_data()
    current_world_name = data["current_world"]
    server_status = await utils.get_server_state(CONFIG)
    if string == "":
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            string = f"'{current_world_name}'"
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            string = f"Current World: '{current_world_name}'"
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            string = f"/start to play '{current_world_name}'. /change_world to change to another world."
    else:
        string += f", current World: '{current_world_name}'"
    if status == None:
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            status = discord.Status.online
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            status = discord.Status.idle
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            status = discord.Status.dnd

    await bot.change_presence(status=status, activity=discord.Game(name=string))


async def _get_formatted_world_info_string(world):
    string = "```"
    attributes = ["display_name", "start_cmd", "sudo_start_cmd", "visible"]
    for attr in attributes:
        string += "\n"+attr+":"+((15-len(attr))*" ") + str(world[attr]) 
    return string + "```"



def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN,) #log_handler=None)


if __name__ == "__main__":
    main()
