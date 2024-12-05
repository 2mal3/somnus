import discord
from discord import app_commands, Status
from discord.ext import tasks
from typing import Union
import asyncio

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.language_handler import LH
from somnus.logic import start, stop, utils, world_selector

LH.language_setup(CONFIG.LANGUAGE)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

is_busy = False  # noqa: PLW0603


@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name="Booting"))
    try:
        synced = await tree.sync()
        log.debug(f"Successfully synced commands: {[cmd.name for cmd in synced]}")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    if await utils.get_server_state(CONFIG) == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
        update_players_online_status.start()
    await _update_bot_presence()


async def _get_world_choices(interaction: discord.Interaction, current: str):
    data = await world_selector.get_world_selector_config()
    return [app_commands.Choice(name=world.display_name, value=world.display_name) for world in data.worlds]


@tree.command(name="ping", description=LH.t("commands.ping.description"))
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message(LH.t("commands.ping.response"))  # type: ignore


@tree.command(name="start", description=LH.t("commands.start.description"))
async def start_server_command(ctx: discord.Interaction):
    start_steps = 20
    message = LH.t("commands.start.msg_above_process_bar")

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, start_steps, message))  # type: ignore

    if await _start_minecraft_server(ctx=ctx, steps=start_steps, message=message):
        await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
        await ctx.channel.send(LH.t("commands.start.finished_msg"))  # type: ignore


def _generate_progress_bar(value: int, max_value: int, message: str) -> str:
    progress = "█" * value + "░" * (max_value - value)
    return f"{message}\n{progress}"


@tree.command(name="stop", description=LH.t("commands.stop.description"))
async def stop_server_command(ctx: discord.Interaction):
    stop_steps = 20
    message = LH.t("commands.stop.msg_above_process_bar")

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message, shutdown=True):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
        await ctx.channel.send(LH.t("commands.stop.finished_msg"))  # type: ignore


def _trim_text_for_discord_subtitle(text: any) -> str:
    return str(text).replace("\n", " ")[:32]


@tree.command(name="add_world", description=LH.t("commands.add_world.description"))
async def add_world_command(
    ctx: discord.Interaction, display_name: str, start_cmd: str, start_cmd_sudo: bool, visible: bool
):
    # only allow super users
    if not await _is_super_user(ctx):
        return

    try:
        await world_selector.create_new_world(display_name, start_cmd, start_cmd_sudo, visible)
        await ctx.response.send_message(LH.t("commands.add_world.success", display_name=display_name), ephemeral=True)
    except Exception as e:
        log.debug(f"Could not create world | {e}")
        await ctx.response.send_message(
            LH.t("commands.add_world.error", display_name=display_name, e=e), ephemeral=True
        )


@tree.command(name="edit_world", description=LH.t("commands.edit_world.description"))
async def edit_world_command(  # noqa: PLR0913
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
        await ctx.response.send_message(
            LH.t(
                "commands.edit_world.success",
                editing_world_name=editing_world_name,
                values=await _get_formatted_world_info_string(world),
            ),
            ephemeral=True,
        )
    except Exception as e:
        await ctx.response.send_message(
            LH.t("commands.edit_world.error", editing_world_name=editing_world_name, e=e), ephemeral=True
        )
        log.warning(f"Couldn't edit world '{editing_world_name}' | {e}", exc_info=e)


edit_world_command.autocomplete("editing_world_name")(_get_world_choices)


@tree.command(name="delete_world", description=LH.t("commands.delete_world.description"))
async def delete_world_command(ctx: discord.Interaction, display_name: str):
    # only allow super user to delete
    if not await _is_super_user(ctx):
        return
    world_selector_config = await world_selector.get_world_selector_config()

    # prevent deletion of the current world
    if display_name in {world_selector_config.current_world, world_selector.new_selected_world}:
        await ctx.response.send_message(LH.t("commands.delete_world.error.current_world"), ephemeral=True)
        return

    # prevent deletion of non existing worlds
    try:
        world = await world_selector.get_world_by_name(display_name, world_selector_config)
    except utils.UserInputError:
        await ctx.response.send_message(
            LH.t("commands.delete_world.error.not_found", display_name=display_name), ephemeral=True
        )
        return

    confirm_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)
    used = False

    async def confirm_callback(interaction: discord.Interaction):
        nonlocal used

        if used:
            await interaction.response.send_message(LH.t("commands.delete_world.error.button_inactive"), ephemeral=True)
            return

        try:
            await world_selector.try_delete_world(display_name)
        except Exception:
            await interaction.response.send_message(LH.t("commands.delete_world.success"), ephemeral=True)
            return

        used = True

    async def cancel_callback(interaction: discord.Interaction):
        nonlocal used

        if used:
            await interaction.response.send_message(LH.t("commands.delete_world.error.button_inactive"), ephemeral=True)
            return

        await interaction.response.send_message(LH.t("commands.delete_world.canceled"), ephemeral=True)
        used = True

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(
        LH.t(
            "commands.delete_world.verification",
            display_name=display_name,
            values=await _get_formatted_world_info_string(world),
        ),
        view=view,
        ephemeral=True,
    )


delete_world_command.autocomplete("display_name")(_get_world_choices)


@tree.command(name="change_world", description=LH.t("commands.change_world.description"))
async def change_world_command(ctx: discord.Interaction):
    world_selector_config = await world_selector.get_world_selector_config()
    index = 0
    options = []

    for world in world_selector_config.worlds:
        if world.visible:
            if world_selector_config.new_selected_world != "":
                if world_selector_config.new_selected_world == world.display_name:
                    index = len(options)
            elif world_selector_config.current_world == world.display_name:
                index = len(options)
            options.append(discord.SelectOption(label=world.display_name, value=world.display_name))

    select = discord.ui.Select(
        placeholder=LH.t("commands.change_world.placeholder"), min_values=1, max_values=1, options=options
    )
    select.options[index].default = True

    async def select_callback(select_interaction: discord.Interaction):
        if ctx.user.id != select_interaction.user.id:
            await select_interaction.response.send_message(
                LH.t("commands.change_world.wrong_user_error"),
                ephemeral=True,
            )
            return

        selected_value = select.values[0]
        select.disabled = True
        await select_interaction.message.edit(view=select_view)
        current_world_is_selected = await world_selector.select_new_world(selected_value)
        mc_server_online = await utils.get_mc_server_state(CONFIG)
        await select_interaction.response.send_message(
            LH.t("commands.change_world.success_offline", selected_value=selected_value)
        )

        if mc_server_online == utils.ServerState.STOPPED:
            await world_selector.change_world()
            await _update_bot_presence()
        elif not current_world_is_selected:
            await _change_world_now_message(select_interaction, selected_value)

    select.callback = select_callback

    select_view = discord.ui.View()
    select_view.add_item(select)

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message(LH.t("commands.change_world.response"), view=select_view)


@tree.command(name="show_worlds", description=LH.t("commands.show_worlds.description"))
async def show_worlds_command(ctx: discord.Interaction):
    sudo = await _is_super_user(ctx, False)
    world_selector_config = await world_selector.get_world_selector_config()

    max_name_length = len(world_selector_config.worlds[0].display_name)
    for world in world_selector_config.worlds:
        if (world.visible or sudo) and len(world.display_name) > max_name_length:
            max_name_length = len(world.display_name)

    string = LH.t("formatting.show_worlds.title")
    for world in world_selector_config.worlds:
        if world.visible or sudo:
            if world.display_name == world_selector_config.current_world:
                string += LH.t("formatting.show_worlds.selected_world")
            else:
                string += LH.t("formatting.show_worlds.not_selecetd_world")

            string += world.display_name

            if sudo:
                string += (3 + max_name_length - len(world.display_name)) * " " + str(world.visible)

    await ctx.response.send_message(string + LH.t("formatting.show_worlds.end"), ephemeral=sudo)


@tree.command(name="stop_without_shutdown", description=LH.t("commands.stop_without_shutdown.description"))
async def stop_without_shutdown_server_command(ctx: discord.Interaction):
    if not await _is_super_user(ctx):
        return
    stop_steps = 20
    message = LH.t("commands.stop_without_shutdown.msg_above_process_bar")

    log.info("Received stop command without shutdown ...")
    await ctx.response.send_message(_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if await _stop_minecraft_server(ctx=ctx, steps=stop_steps, message=message, shutdown=False):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, ""))
        await ctx.channel.send(LH.t("commands.stop_without_shutdown.finished_msg"))  # type: ignore


@tree.command(name="help", description=LH.t("commands.help.description"))
async def help_command(ctx: discord.Interaction):
    sudo = await _is_super_user(ctx, False)
    user_commands = ["start", "stop", "change_world", "restart", "show_worlds", "ping", "reset_busy", "help"]
    embed = discord.Embed(title=LH.t("commands.help.title"), color=discord.Color.blue())
    if sudo:
        embed.add_field(
            name=LH.t("formatting.help.subtitle", subtitle=LH.t("commands.help.user_subtitle")), value="", inline=False
        )
    for user_command in user_commands:
        embed.add_field(
            name=LH.t("formatting.help.command", command_name=user_command),
            value=LH.t("formatting.help.command_description", description=LH.t(f"commands.{user_command}.description")),
            inline=False,
        )
    if sudo:
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name=LH.t("formatting.help.subtitle", subtitle=LH.t("commands.help.admin_subtitle")), value="", inline=False
        )
        admin_commands = ["add_world", "edit_world", "delete_world", "stop_without_shutdown"]
        for admin_command in admin_commands:
            description = LH.t(f"commands.{admin_command}.description").replace(
                LH.t("formatting.help.admin_prefix_to_remove"), ""
            )
            embed.add_field(
                name=LH.t("formatting.help.command", command_name=admin_command),
                value=LH.t("formatting.help.command_description", description=description),
                inline=False,
            )
    await ctx.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="restart", description=LH.t("commands.restart.description"))
async def restart_command(ctx: discord.Interaction):
    message = LH.t("commands.restart.above_process_bar.msg")
    await ctx.response.send_message(message)
    await _restart_minecraft_server(ctx, message)


@tree.command(name="reset_busy", description=LH.t("commands.reset_busy.description"))
async def reset_busy_command(ctx: discord.Interaction):
    if not is_busy:
        await ctx.response.send_message(LH.t("commands.reset_busy.error.general"), ephemeral=True)  # type: ignore
        return False

    confirm_button = discord.ui.Button(label=LH.t("commands.reset_busy.reset"), style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label=LH.t("commands.reset_busy.cancel"), style=discord.ButtonStyle.green)

    async def confirm_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH.t("commands.reset_busy.error.wrong_user"),
                ephemeral=True,
            )
            return
        await _no_longer_busy()
        confirm_button.disabled = True
        cancel_button.disabled = True
        await interaction.response.edit_message(content=LH.t("commands.reset_busy.success"), view=view)

    async def cancel_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH.t("commands.reset_busy.error.wrong_user"),
                ephemeral=True,
            )
            return
        confirm_button.disabled = True
        cancel_button.disabled = True
        await interaction.response.edit_message(content=LH.t("commands.reset_busy.canceled"), view=view)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(LH.t("commands.reset_busy.verification"), view=view)


async def _start_minecraft_server(ctx: discord.Interaction, steps: int, message: str) -> bool:
    if not await _check_if_busy(ctx):
        return
    world_config = await world_selector.get_world_selector_config()
    await _update_bot_presence(
        Status.idle,
        await _get_discord_activity("starting", LH.t("status.text.starting", world_name=world_config.current_world)),
    )
    i = 0
    try:
        async for _ in start.start_server():
            i += 1
            await ctx.edit_original_response(content=_generate_progress_bar(i, steps, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await _update_bot_presence()
            await _no_longer_busy()
            return False
        log.error("Could not start server", exc_info=e)
        await ctx.edit_original_response(
            content=LH.t("commands.start.error", e=_trim_text_for_discord_subtitle(e)),
        )
        await _update_bot_presence()
        await _no_longer_busy()
        return False

    log.info("Server started!")
    # await _update_bot_presence()
    update_players_online_status.start()
    log.info("Bot presence updated!")
    await _no_longer_busy()
    return True


async def _stop_minecraft_server(ctx: discord.Interaction, steps: int, message: str, shutdown: bool) -> bool:
    if not await _check_if_busy(ctx):
        return False

    mc_status = await utils.get_mcstatus(CONFIG)
    if mc_status is not None and mc_status.players.online != 0:
        if not await _players_online_verification(ctx, message, mc_status):
            return

        if not await _check_if_busy(ctx):
            return False

    world_config = await world_selector.get_world_selector_config()
    update_players_online_status.stop()
    await _update_bot_presence(
        discord.Status.idle,
        await _get_discord_activity("stopping", LH.t("status.text.stopping", world_name=world_config.current_world)),
    )

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
        await ctx.edit_original_response(
            content=LH.t("commands.stop.error.general", e=_trim_text_for_discord_subtitle(e))
        )
        await _update_bot_presence()
        await _no_longer_busy()
        return False

    log.debug("Change current world in JSON file to selected world (if necessary)")
    await world_selector.change_world()
    await _update_bot_presence()
    log.info("Bot presence updated!")
    await _no_longer_busy()
    return True


async def _restart_minecraft_server(ctx: discord.Interaction, message: str):
    if (await utils.get_mc_server_state(CONFIG)) == utils.ServerState.STOPPED:
        await ctx.edit_original_response(content=LH.t("commands.restart.error"))  # type: ignore
        return
    stop_steps = 20
    start_steps = 20

    log.info("Received restart command ...")
    await ctx.edit_original_response(content=_generate_progress_bar(1, stop_steps, message))  # type: ignore

    if await _stop_minecraft_server(
        ctx=ctx,
        steps=stop_steps,
        message=message + LH.t("commands.restart.above_process_bar.stopping_addon"),
        shutdown=False,
    ):
        await ctx.edit_original_response(content=_generate_progress_bar(stop_steps, stop_steps, message))
        if await _start_minecraft_server(
            ctx=ctx, steps=start_steps, message=message + LH.t("commands.restart.above_process_bar.starting_addon")
        ):
            await ctx.edit_original_response(content=_generate_progress_bar(start_steps, start_steps, ""))
            await ctx.channel.send(LH.t("commands.restart.finished_msg"))  # type: ignore


async def _players_online_verification(ctx: discord.Interaction, message: str, mcstatus: utils.JavaServer.status):
    await _no_longer_busy()

    result_future = asyncio.Future()

    confirm_button = discord.ui.Button(
        label=LH.t("commands.stop.error.players_online.stop_anyway"), style=discord.ButtonStyle.red
    )
    cancel_button = discord.ui.Button(
        label=LH.t("commands.stop.error.players_online.cancel"), style=discord.ButtonStyle.green
    )

    async def confirm_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH.t("commands.stop.error.players_online.wrong_user"),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        view.remove_item(confirm_button)
        view.remove_item(cancel_button)
        await ctx.edit_original_response(content=message, view=view)
        result_future.set_result(True)

    async def cancel_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH.t("commands.stop.error.players_online.wrong_user"),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        confirm_button.disabled = True
        cancel_button.disabled = True
        await ctx.edit_original_response(content=LH.t("commands.stop.error.players_online.canceled"), view=view)
        result_future.set_result(False)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    if mcstatus.players.online == 1:
        player_name = LH.t(
            "commands.stop.error.players_online.player_name_line", player_name=mcstatus.players.sample[0].name
        )
        content = (
            message + "\n\n" + LH.t("commands.stop.error.players_online.question_singular", player_name=player_name)
        )
    else:
        player_names = ""
        for player in mcstatus.players.sample:
            player_names += "\n" + LH.t("commands.stop.error.players_online.player_name_line", player_name=player.name)

        content = (
            message
            + "\n\n"
            + LH.t(
                "commands.stop.error.players_online.question_plural",
                player_count=mcstatus.players.online,
                player_names=player_names,
            )
        )

    await ctx.edit_original_response(content=content, view=view)

    result = await result_future
    return result


async def _change_world_now_message(select_interaction: discord.Interaction, selected_value: str):
    confirm_button = discord.ui.Button(label=LH.t("commands.change_world.restart_now"), style=discord.ButtonStyle.green)
    cancel_button = discord.ui.Button(label=LH.t("commands.change_world.cancel"), style=discord.ButtonStyle.gray)

    async def confirm_callback(interaction: discord.Interaction):
        if select_interaction.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH.t("commands.change_world.error.wrong_user"),
                ephemeral=True,
            )
            return
        button_view.remove_item(confirm_button)
        button_view.remove_item(cancel_button)
        message = (
            LH.t("commands.change_world.success_offline", selected_value=selected_value)
            + "\n"
            + LH.t("commands.restart.above_process_bar.msg")
        )
        await interaction.response.edit_message(content=message, view=button_view)
        await _restart_minecraft_server(interaction, message)

    async def cancel_callback(interaction: discord.Interaction):
        if select_interaction.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH.t("commands.change_world.error.wrong_user"),
                ephemeral=True,
            )
            return
        button_view.remove_item(confirm_button)
        button_view.remove_item(cancel_button)
        await interaction.response.edit_message(
            content=LH.t("commands.change_world.success_offline", selected_value=selected_value), view=button_view
        )

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    button_view = discord.ui.View()
    button_view.add_item(confirm_button)
    button_view.add_item(cancel_button)

    await select_interaction.edit_original_response(
        content=LH.t("commands.change_world.success_online", selected_value=selected_value), view=button_view
    )


async def _update_bot_presence(
    status: Status | None = None,
    activity: Union[discord.Game, discord.Streaming, discord.Activity, discord.BaseActivity] | None = None,
):
    world_selector_config = await world_selector.get_world_selector_config()
    server_status = await utils.get_server_state(CONFIG)
    if not activity:
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            mc_status = await utils.get_mcstatus(CONFIG)
            if mc_status is None:
                text = LH.t(
                    "status.text.online",
                    world_name=world_selector_config.current_world,
                    players_online="X",
                    max_players="Y",
                )
            else:
                text = LH.t(
                    "status.text.online",
                    world_name=world_selector_config.current_world,
                    players_online=mc_status.players.online,
                    max_players=mc_status.players.max,
                )
            activity = await _get_discord_activity("online", text)
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            text = LH.t("status.text.only_host_online", world_name=world_selector_config.current_world)
            activity = await _get_discord_activity("only_host_online", text)
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            text = LH.t("status.text.offline", world_name=world_selector_config.current_world)
            activity = await _get_discord_activity("offline", text)
    if not status:
        if server_status == (utils.ServerState.RUNNING, utils.ServerState.RUNNING):
            status = Status.online
        elif server_status == (utils.ServerState.RUNNING, utils.ServerState.STOPPED):
            status = Status.idle
        elif server_status == (utils.ServerState.STOPPED, utils.ServerState.STOPPED):
            status = Status.dnd

    await bot.change_presence(status=status, activity=activity)


async def _get_discord_activity(
    server_status_str: str, text: str
) -> Union[discord.Game, discord.Streaming, discord.Activity, discord.BaseActivity]:
    activity_str = LH.t("status.activity." + server_status_str)
    if activity_str == "Game":
        return discord.Game(name=text)
    elif activity_str == "Streaming":
        return discord.Streaming(name=text)
    elif activity_str == "Listening":
        return discord.Activity(type=discord.ActivityType.listening, name=text)
    elif activity_str == "Watching":
        return discord.Activity(type=discord.ActivityType.watching, name=text)
    else:
        raise TypeError(
            f"Wrong Discord Activity choosen. Use 'Game', 'Streaming', 'Listening' or 'Watching'. Not '{activity_str}'"
        )


async def _get_formatted_world_info_string(world: world_selector.WorldSelectorWorld):
    string = LH.t("formatting.sudo_world_info.start")

    attributes = ["display_name", "start_cmd", "start_cmd_sudo", "visible"]
    for attr in attributes:
        string += LH.t(
            "formatting.sudo_world_info.line",
            attr=attr,
            gap_filler=((15 - len(attr)) * " "),
            value=str(getattr(world, attr)),
        )
    return string + LH.t("formatting.sudo_world_info.end")


async def _check_if_busy(ctx: discord.Interaction) -> bool:
    global is_busy  # noqa: PLW0603
    if is_busy:
        await ctx.edit_original_response(content=LH.t("permission.busy"))  # type: ignore
        return False
    else:
        is_busy = True
        return True


async def _no_longer_busy():
    global is_busy  # noqa: PLW0603
    is_busy = False


async def _is_super_user(ctx: discord.Interaction, message: bool = True):
    super_users = CONFIG.DISCORD_SUPER_USER_ID.split(";")
    for super_user in super_users:
        if ctx.user.id == int(super_user):
            return True

    if message:
        await ctx.response.send_message(LH.t("permission.sudo"), ephemeral=True)
    return False


@tasks.loop(seconds=10)
async def update_players_online_status():
    await _update_bot_presence()


def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
