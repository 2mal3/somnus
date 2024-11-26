import discord
from discord import app_commands, Status

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.logic import start, stop, utils, world_selector

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

current_world_name = ""
isBusy = False


@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name="Booting"))
    await tree.sync()
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await _update_bot_presence()


async def _get_world_choices(interaction: discord.Interaction, current: str):
    data = await world_selector.get_world_selector_config()
    return [app_commands.Choice(name=world["display_name"], value=world["display_name"]) for world in data["worlds"]]


@tree.command(name="ping", description="Replies with Pong!")
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message("Pong!")  # type: ignore


@tree.command(name="start", description="Starts the server")
async def start_server_command(ctx: discord.Interaction):
    if not await _check_if_busy(ctx):
        return
    start_steps = 20
    message = "Starting Server ..."

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, start_steps, message))  # type: ignore
    
    if (await _start_minecraft_server(ctx=ctx, steps=start_steps, message=message)):
        await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
        await ctx.channel.send("Server started!")  # type: ignore


def _generate_progress_bar(value: int, max_value: int, message: str) -> str:
    progress = "█" * value + "░" * (max_value - value)
    return f"{message}\n{progress}"


@tree.command(name="stop", description="Stops the server")
async def stop_server_command(ctx: discord.Interaction):
    if not await _check_if_busy(ctx):
        return
    stop_steps = 10
    message = "Stopping Server ..."

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if (await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message, shutdown=True)):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
        await ctx.channel.send("Server stopped!")  # type: ignore


def _trim_text_for_discord_subtitle(text: any) -> str:
    return str(text).replace("\n", " ")[:32]


@tree.command(name="add_world", description="SUPER-USER-ONLY: Creates a new reference to an installed Minecraft installation")
async def add_world_command(
    ctx: discord.Interaction, display_name: str, start_cmd: str, start_cmd_sudo: bool, visible: bool
):
    # only allow super users
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message(
            "You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True
        )
        return

    try:
        await world_selector.create_new_world(display_name, start_cmd, start_cmd_sudo, visible)
        await ctx.response.send_message(f"The world '{display_name}' was created succesfully!", ephemeral=True)
    except Exception as e:
        log.debug(f"Could not create world | {e}")
        await ctx.response.send_message(f"Couldn't create the world '{display_name}' | {e}", ephemeral=True)


@tree.command(
    name="edit_world", description="SUPER-USER-ONLY: Edits a reference to an installed Minecraft installation")
async def edit_world_command(   # noqa: PLR0913
    ctx: discord.Interaction,
    editing_world_name: str,
    new_display_name: str = None,
    start_cmd: str = None,
    sudo_start_cmd: bool = None,
    visible: bool = None,
):
    # only super users
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message(
            "You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True
        )
        return

    try:
        world = await world_selector.edit_new_world(
            editing_world_name, new_display_name, start_cmd, sudo_start_cmd, visible
        )
        await ctx.response.send_message(
            f"The world '{editing_world_name}' was edited succesfully! New values are:{await _get_formatted_world_info_string(world)}",
            ephemeral=True,
        )
    except Exception as e:
        await ctx.response.send_message(f"Couldn't edit the world '{editing_world_name}'", ephemeral=True)
        log.warning(f"Couldn't edit world '{editing_world_name}'", exc_info=e)

edit_world_command.autocomplete("editing_world_name")(_get_world_choices)


@tree.command(
    name="delete_world", description="SUPER-USER-ONLY: Deletes a reference to an installed Minecraft installation"
)
async def delete_world_command(ctx: discord.Interaction, display_name: str):
    # only allow super user to delete
    if ctx.user.id != int(CONFIG.DISCORD_SUPER_USER_ID):
        await ctx.response.send_message(
            "You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True
        )
        return

    world_selector_config = await world_selector.get_world_selector_config()

    # prevent deletion of the current world
    if display_name == world_selector_config.current_world:
        await ctx.response.send_message(
            "You can't delete the current world. Change the current world with /change_world", ephemeral=True
        )
        return

    # prevent deletion of non existing worlds
    try:
        world = await world_selector.get_world_by_name(display_name, world_selector_config)
    except utils.UserInputError:
        await ctx.response.send_message(f"World '{display_name}' not found.", ephemeral=True)
        return

    confirm_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)
    used = False

    async def confirm_callback(interaction: discord.Interaction):
        nonlocal used

        if used:
            await interaction.response.send_message("Button inactive, use /delete_world again", ephemeral=True)
            return

        try:
            await world_selector.try_delete_world(display_name)
        except Exception:
            await interaction.response.send_message(
                f"The world '{display_name}' was deleted successfully!", ephemeral=True
            )
            return

        used = True

    async def cancel_callback(interaction: discord.Interaction):
        nonlocal used

        if used:
            await interaction.response.send_message("Button inactive, use /delete_world again", ephemeral=True)
            return

        await interaction.response.send_message("Deletion process canceled", ephemeral=True)
        used = True

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(
        f"Do you really want to delete the world '{display_name}'?{await _get_formatted_world_info_string(world)}",
        view=view,
        ephemeral=True,
    )


delete_world_command.autocomplete("display_name")(_get_world_choices)


@tree.command(name="change_world", description="Changes the current world into another visible world")
async def change_world_command(ctx: discord.Interaction):
    global current_world_name
    world_selector_config = await world_selector.get_world_selector_config()
    index = 0
    options = []

    for world in world_selector_config.worlds:
        if world.visible:
            if world.display_name == world_selector_config.current_world:
                index = len(options)
            options.append(discord.SelectOption(label=world.display_name, value=world.display_name))

    select = discord.ui.Select(
        placeholder="Choose the world you want to play", min_values=1, max_values=1, options=options
    )
    select.options[index].default = True

    async def select_callback(select_interaction: discord.Interaction):
        global current_world_name
        if ctx.user.id != select_interaction.user.id:
            await select_interaction.response.send_message(
                "You cannot use the menu because it was requested by someone else. Use /change_world to change the world",
                ephemeral=True,
            )
            return

        selected_value = select.values[0]
        select.disabled = True
        await select_interaction.message.edit(view=view)
        try:
            current_world_name = await world_selector.change_world(selected_value)
            await select_interaction.response.send_message(f"'{selected_value}' was selected succusfully!")
            await _update_bot_presence()
        except Exception:
            await select_interaction.response.send_message(
                f"Couldn't change the world to '{selected_value}'.", ephemeral=True
            )

    select.callback = select_callback

    view = discord.ui.View()
    view.add_item(select)

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message("Choose the world you want to play:", view=view)


@tree.command(name="show_worlds", description="Shows all available worlds")
async def show_worlds_command(ctx: discord.Interaction):
    print(current_world_name)

    sudo = ctx.user.id == int(CONFIG.DISCORD_SUPER_USER_ID)
    world_selector_config = await world_selector.get_world_selector_config()

    max_name_length = len(world_selector_config.worlds[0].display_name)
    for world in world_selector_config.worlds:
        if (world.visible or sudo) and len(world.display_name) > max_name_length:
            max_name_length = len(world.display_name)

    string = "## List of all available worlds \n```"
    for world in world_selector_config.worlds:
        if world.visible or sudo:
            if world.display_name == world_selector_config.current_world:
                string += "\n✅ - "
            else:
                string += "\n⬜ - "

            string += world.display_name

            if sudo:
                string += (3 + max_name_length - len(world.display_name)) * " " + str(world.visible)

    await ctx.response.send_message(string + "```", ephemeral=sudo)

@tree.command(name="stop_without_shutdown", description="SUPER-USER-ONLY: Stops the Minecraft server, but doesn't shut off the host server.")
async def stop_without_shutdown_server_command(ctx: discord.Interaction):
    if not await _check_if_busy(ctx):
        return
    stop_steps = 10
    message = "Stopping Server without shutdown ..."

    log.info("Received stop command without shutdown ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if (await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message, shutdown=False)):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
        await ctx.channel.send("Server stopped without shutdown!")  # type: ignore


@tree.command(name="restart", description="Restarts just the Minecraft server process, not the hole server")
async def restart_command(ctx: discord.Interaction):
    if not await _check_if_busy(ctx):
        return
    stop_steps = 10
    start_steps = 20
    message = "**Restarting Server** ... "

    log.info("Received restart command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if (await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message + "Stopping", shutdown=False)):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, message))
        if (await _start_minecraft_server(ctx=ctx, steps=start_steps, message=message + "Starting")):
            await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
            await ctx.channel.send("Server restarted!")  # type: ignore

@tree.command(
    name="reset_busy_state", description="If the message that the bot is busy is sent by mistake, this command can reset the incorrect busy state.", guild=discord.Object(id=910195152490999881))
async def reset_busy_state_command(ctx: discord.Interaction):
    global isBusy
    if not isBusy:
        ctx.response.send_message("The bot is not busy. Errors cannot be corrected", ephemeral=True)  # type: ignore
        return


    confirm_button = discord.ui.Button(label="Reset", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)

    async def confirm_callback(interaction: discord.Interaction):
        await _no_longer_busy()
        confirm_button.disabled = True  # Deactivate button
        cancel_button.disabled = True  # Deactivate button
        await interaction.response.edit_message(
            content="Reset of Busy state was successfully completed.",
            view=view
        )

    async def cancel_callback(interaction: discord.Interaction):
        confirm_button.disabled = True  # Deactivate button
        cancel_button.disabled = True  # Deactivate button
        await interaction.response.edit_message(
            content="Busy state reset was successfully canceled.",
            view=view
        )

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(
        f"Do you really want to reset the bot's busy state? If so, errors may occur that can cause the bot to crash!",
        view=view
    )


async def _start_minecraft_server(ctx: discord.Interaction, steps: int, message:str, message_on_full_progressbar: bool = False) -> bool:
    await _update_bot_presence(Status.idle, "Starting Server")
    
    i = 0
    try:
        async for _ in start.start_server():
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await _update_bot_presence()
            await _no_longer_busy()
            return False
        log.error("Could not start server", exc_info=e)
        await ctx.edit_original_response(
            content=f"Could not start server\n-# ERROR: {_trim_text_for_discord_subtitle(e)}",
        )
        await _update_bot_presence()
        await _no_longer_busy()
        return False

    log.info("Server started!")
    await ctx.channel.send("Server started!")  # type: ignore
    await _update_bot_presence()
    log.info("Server started Messages sent!")
    await _no_longer_busy()
    return True


async def _stop_minecraft_server(ctx: discord.Interaction, steps: int, message:str, shutdown: bool) -> bool:
    global current_world_name
    await _update_bot_presence(discord.Status.idle, "Stopping Server")

    i = 0
    try:
        async for _ in stop.stop_server(shutdown):
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await _update_bot_presence()
            return False
        log.error(f"Could not stop server | {e}")
        await ctx.edit_original_response(content=f"Could not stop server\n-# ERROR: {_trim_text_for_discord_subtitle(e)}")
        await _update_bot_presence()
        return False

    log.info("Server stopped!")
    await _update_bot_presence()
    log.info("Server stopped Messages sent!")
    current_world_name = ""
    return True


async def _update_bot_presence(status: Status | None = None, text: str = ""):
    world_selector_config = await world_selector.get_world_selector_config()
    global current_world_name
    if current_world_name == "":
        world_name = world_selector_config.current_world
    else:
        world_name = current_world_name
    server_status = await utils.get_server_state(CONFIG)

    if not text:
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            text = f"'{world_name}'"
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            text = f"World '{world_name}'"
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            text = f"/start to play '{world_name}'. /change_world to change to another world."
    else:
        text += f", current World: '{world_name}'"

    if not status:
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            status = Status.online
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            status = Status.idle
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            status = Status.dnd

    await bot.change_presence(status=status, activity=discord.Game(name=text))


async def _get_formatted_world_info_string(world: world_selector.WorldSelectorWorld):
    string = "```"

    attributes = ["display_name", "start_cmd", "start_cmd_sudo", "visible"]
    for attr in attributes:
        string += "\n" + attr + ":" + ((15 - len(attr)) * " ") + str(getattr(world, attr))
    return string + "```"

async def _check_if_busy(ctx: discord.Interaction) -> bool:
    global isBusy
    if isBusy:
        await ctx.response.send_message("Please wait until the current operation is complete!", ephemeral=True)  # type: ignore
        return False
    else:
        isBusy = True
        return True

async def _no_longer_busy():
    global isBusy
    isBusy = False



def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
