import discord
from discord import app_commands, Status

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.language_handler import language_setup, t
from somnus.logic import start, stop, utils, world_selector

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

isBusy = False

guild_id = 910195152490999878


@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name="Booting"))
    try:
        synced = await tree.sync(guild=discord.Object(id=guild_id))
        log.info(f"Successfully synced commands: {[cmd.name for cmd in synced]}")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await _update_bot_presence()



async def _get_world_choices(interaction: discord.Interaction, current: str):
    data = await world_selector.get_world_selector_config()
    return [app_commands.Choice(name=world.display_name, value=world.display_name) for world in data.worlds]


@tree.command(name="ping", description=t("commands.ping.description"))
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message(t("commands.ping.response"))  # type: ignore


@tree.command(name="start", description=t("commands.start.description"))
async def start_server_command(ctx: discord.Interaction):
    start_steps = 20
    message = t("commands.start.msg_above_process_bar")

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, start_steps, message))  # type: ignore
    
    if (await _start_minecraft_server(ctx=ctx, steps=start_steps, message=message)):
        await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
        await ctx.channel.send(t("commands.start.finished_msg"))  # type: ignore


def _generate_progress_bar(value: int, max_value: int, message: str) -> str:
    progress = "█" * value + "░" * (max_value - value)
    return f"{message}\n{progress}"


@tree.command(name="stop", description=t("commands.stop.description"))
async def stop_server_command(ctx: discord.Interaction):
    stop_steps = 10
    message = t("commands.stop.msg_above_process_bar")

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if (await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message, shutdown=True)):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
        await ctx.channel.send(t("commands.stop.finished_msg"))  # type: ignore


def _trim_text_for_discord_subtitle(text: any) -> str:
    return str(text).replace("\n", " ")[:32]


@tree.command(name="add_world", description=t("commands.add_world.description"))
async def add_world_command(
    ctx: discord.Interaction, display_name: str, start_cmd: str, start_cmd_sudo: bool, visible: bool
):
    # only allow super users
    if not await _is_super_user(ctx):
        return

    try:
        await world_selector.create_new_world(display_name, start_cmd, start_cmd_sudo, visible)
        await ctx.response.send_message(t("commands.add_world.success", display_name=display_name), ephemeral=True)
    except Exception as e:
        log.debug(f"Could not create world | {e}")
        await ctx.response.send_message(t("commands.add_world.error", display_name=display_name, e=e), ephemeral=True)


@tree.command(
    name="edit_world", description=t("commands.edit_world.description"))
async def edit_world_command(   # noqa: PLR0913
    ctx: discord.Interaction,
    editing_world_name: str,
    new_display_name: str = None,
    start_cmd: str = None,
    sudo_start_cmd: bool = None,
    visible: bool = None,
):
    # only super users
    if not await _is_super_user(ctx):
        return

    try:
        world = await world_selector.edit_new_world(
            editing_world_name, new_display_name, start_cmd, sudo_start_cmd, visible
        )
        await ctx.response.send_message(t("commands.edit_world.success", editing_world_name=editing_world_name, values=await _get_formatted_world_info_string(world))
            ,
            ephemeral=True,
        )
    except Exception as e:
        await ctx.response.send_message(t("commands.edit_world.error", editing_world_name=editing_world_name, e=e), ephemeral=True)
        log.warning(f"Couldn't edit world '{editing_world_name}' | {e}", exc_info=e)

edit_world_command.autocomplete("editing_world_name")(_get_world_choices)


@tree.command(
    name="delete_world", description=t("commands.delete_world.description")
)
async def delete_world_command(ctx: discord.Interaction, display_name: str):
    # only allow super user to delete
    if not await _is_super_user(ctx):
        return

    world_selector_config = await world_selector.get_world_selector_config()

    # prevent deletion of the current world
    if display_name == world_selector_config.current_world:
        await ctx.response.send_message(t("commands.delete_world.error.current_world"), ephemeral=True
        )
        return

    # prevent deletion of non existing worlds
    try:
        world = await world_selector.get_world_by_name(display_name, world_selector_config)
    except utils.UserInputError:
        await ctx.response.send_message(t("commands.delete_world.error.not_found", display_name=display_name), ephemeral=True)
        return

    confirm_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)
    used = False

    async def confirm_callback(interaction: discord.Interaction):
        nonlocal used

        if used:
            await interaction.response.send_message(t("commands.delete_world.error.button_inactive"), ephemeral=True)
            return

        try:
            await world_selector.try_delete_world(display_name)
        except Exception:
            await interaction.response.send_message(
                t("commands.delete_world.success"), ephemeral=True
            )
            return

        used = True

    async def cancel_callback(interaction: discord.Interaction):
        nonlocal used

        if used:
            await interaction.response.send_message(t("commands.delete_world.error.button_inactive"), ephemeral=True)
            return

        await interaction.response.send_message(t("commands.delete_world.canceled"), ephemeral=True)
        used = True

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(
        t("commands.delete_world.verification", display_name=display_name, values=await _get_formatted_world_info_string(world)),
        view=view,
        ephemeral=True,
    )

delete_world_command.autocomplete("display_name")(_get_world_choices)


@tree.command(name="change_world", description=t("commands.change_world.description"))
async def change_world_command(ctx: discord.Interaction):
    world_selector_config = await world_selector.get_world_selector_config()
    index = 0
    options = []

    for world in world_selector_config.worlds:
        if world.visible:
            if world.display_name == world_selector_config.current_world:
                index = len(options)
            options.append(discord.SelectOption(label=world.display_name, value=world.display_name))

    select = discord.ui.Select(
        placeholder=t("commands.change_world.placeholder"), min_values=1, max_values=1, options=options
    )
    select.options[index].default = True

    async def select_callback(select_interaction: discord.Interaction):
        if ctx.user.id != select_interaction.user.id:
            await select_interaction.response.send_message(
                t("commands.change_world.error.wrong_user"),
                ephemeral=True,
            )
            return

        selected_value = select.values[0]
        select.disabled = True
        await select_interaction.message.edit(view=view)
        try:
            await world_selector.select_new_world(selected_value)
            await _update_bot_presence()
            if await utils.get_server_state(CONFIG) == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
                await utils.get_mcstatus(CONFIG)
                return
                
            
            else:
                await select_interaction.response.send_message(t("commands.change_world.success"))
        except Exception as e:
            await select_interaction.response.send_message(
                t("commands.change_world.error.wrong_user", selected_value=selected_value, e=e), ephemeral=True
            )

    select.callback = select_callback

    view = discord.ui.View()
    view.add_item(select)

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message(t("commands.change_world.response"), view=view)


@tree.command(name="show_worlds", description=t("commands.show_worlds.description"))
async def show_worlds_command(ctx: discord.Interaction):
    sudo = await _is_super_user(ctx, False)
    world_selector_config = await world_selector.get_world_selector_config()

    max_name_length = len(world_selector_config.worlds[0].display_name)
    for world in world_selector_config.worlds:
        if (world.visible or sudo) and len(world.display_name) > max_name_length:
            max_name_length = len(world.display_name)

    string = t("commands.show_worlds.format.title")
    for world in world_selector_config.worlds:
        if world.visible or sudo:
            if world.display_name == world_selector_config.current_world:
                string += t("commands.show_worlds.format.selected_world")
            else:
                string += t("commands.show_worlds.format.not_selecetd_world")

            string += world.display_name

            if sudo:
                string += (3 + max_name_length - len(world.display_name)) * " " + str(world.visible)

    await ctx.response.send_message(string + t("commands.show_worlds.format.end"), ephemeral=sudo)

@tree.command(name="stop_without_shutdown", description=t("commands.stop_without_shutdown.description"))
async def stop_without_shutdown_server_command(ctx: discord.Interaction):
    stop_steps = 10
    message = t("commands.stop_without_shutdown.msg_above_process_bar")

    log.info("Received stop command without shutdown ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if (await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message, shutdown=False)):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
        await ctx.channel.send(t("commands.stop_without_shutdown.finished_msg"))  # type: ignore


@tree.command(name="restart", description=t("commands.restart.description"))
async def restart_command(ctx: discord.Interaction):
    await _restart_minecraft_server(ctx)


@tree.command(name="reset_busy", description=t("commands.reset_busy.description"))
async def reset_busy_command(ctx: discord.Interaction):
    global isBusy
    if not isBusy:
        await ctx.response.send_message(t("commands.reset_busy.error"), ephemeral=True)  # type: ignore
        return False


    confirm_button = discord.ui.Button(label="Reset", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)

    async def confirm_callback(interaction: discord.Interaction):
        await _no_longer_busy()
        confirm_button.disabled = True  # Deactivate button
        cancel_button.disabled = True  # Deactivate button
        await interaction.response.edit_message(
            content=t("commands.reset_busy.success"),
            view=view
        )

    async def cancel_callback(interaction: discord.Interaction):
        confirm_button.disabled = True  # Deactivate button
        cancel_button.disabled = True  # Deactivate button
        await interaction.response.edit_message(
            content=t("commands.reset_busy.canceled"),
            view=view
        )

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(
        t("commands.reset_busy.verification"),
        view=view
    )


async def _start_minecraft_server(ctx: discord.Interaction, steps: int, message:str) -> bool:
    if not await _check_if_busy(ctx):
        return
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
    await _update_bot_presence()
    log.info("Bot presence updated!")
    await _no_longer_busy()
    return True


async def _stop_minecraft_server(ctx: discord.Interaction, steps: int, message:str, shutdown: bool) -> bool:
    if not await _check_if_busy(ctx):
        return
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
            await _no_longer_busy()
            return False
        log.error(f"Could not stop server | {e}")
        await ctx.edit_original_response(content=f"Could not stop server\n-# ERROR: {_trim_text_for_discord_subtitle(e)}")
        await _update_bot_presence()
        await _no_longer_busy()
        return False

    log.debug("Change current world in JSON file to selected world (if necessary)")
    await world_selector.change_world()
    await _update_bot_presence()
    log.info("Bot presence updated!")
    await _no_longer_busy()
    return True

async def _restart_minecraft_server(ctx: discord.Interaction):
    if (await utils.get_server_state(CONFIG))[1] == utils.ServerState.STOPPED:
        await ctx.response.send_message("The Server is stopped. Use /start to start the server")  # type: ignore
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


async def _update_bot_presence(status: Status | None = None, text: str = ""):
    world_selector_config = await world_selector.get_world_selector_config()
    server_status = await utils.get_server_state(CONFIG)

    if not text:
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            text = f"'{world_selector_config.current_world}'"
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            text = f"World '{world_selector_config.current_world}'"
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            text = f"/start to play '{world_selector_config.current_world}'. /change_world to change to another world."
    else:
        text += f", current World: '{world_selector_config.current_world}'"

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
        print("HALLO")
        await ctx.edit_original_response(content="Please wait until the current operation is complete!")  # type: ignore
        return False
    else:
        isBusy = True
        return True

async def _no_longer_busy():
    global isBusy
    isBusy = False

async def _is_super_user(ctx: discord.Interaction, message: bool = True):
    if ctx.user.id in CONFIG.DISCORD_SUPER_USER_ID:
        return True
    else:
        if message:
            await ctx.response.send_message(
                "You are not authorized to use this command. Ask your system administrator for changes.", ephemeral=True)
        return False



def main(config: Config = CONFIG):
    language_setup(config.LANGUAGE)

    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
