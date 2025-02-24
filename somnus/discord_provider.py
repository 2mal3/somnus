import asyncio
from typing import Union

import discord
from discord import Status, app_commands
from discord.ext import tasks
from mcstatus.status_response import JavaStatusResponse

from somnus.config import CONFIG, Config
from somnus.logger import log
from somnus.logic import start, stop, utils, world_selector
from somnus.language_handler import LH


PROGRESS_BAR_STEPS = 20

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

is_busy = False  # noqa: PLW0603
inactvity_seconds = 0  # noqa: PLW0603


@bot.event
async def on_ready():
    global inactvity_seconds  # noqa: PLW0603

    if not bot.user:
        log.fatal("Bot user not found!")
        raise RuntimeError("Bot user not found!")

    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name="Booting"))
    try:
        synced = await tree.sync()
        log.debug(f"Successfully synced commands: {[cmd.name for cmd in synced]}")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

    if (await utils.get_server_state(CONFIG)).mc_server_running:
        if CONFIG.INACTIVITY_SHUTDOWN_MINUTES:
            inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
        update_players_online_status.start()
        log.info("Status Updater started!")

    log.debug("Updating bot presence ...")
    await _update_bot_presence()
    log.debug("Initial bot presence updated!")


@tree.command(name="ping", description=LH("commands.ping.description"))
async def ping_command(ctx: discord.Interaction):
    await ctx.response.send_message(LH("commands.ping.response"))  # type: ignore


@tree.command(name="start", description=LH("commands.start.description"))
async def start_server_command(ctx: discord.Interaction):
    message = LH("commands.start.msg_above_process_bar")

    log.info("Received start command ...")
    await ctx.response.send_message(_generate_progress_bar(1, message))  # type: ignore

    if await _try_start_minecraft_server(ctx=ctx, message=message):
        await ctx.edit_original_response(content=_generate_progress_bar(PROGRESS_BAR_STEPS, ""))
        await ctx.channel.send(LH("commands.start.finished_msg"))  # type: ignore
        log.info("Server started!")

    await _update_bot_presence()


async def _try_start_minecraft_server(ctx: discord.Interaction, message: str):
    global inactvity_seconds  # noqa: PLW0603

    if not await _check_if_busy(ctx):
        return False

    world_config = await world_selector.get_world_selector_config()

    activity = await _get_discord_activity(
        "starting", LH("status.text.starting", args={"world_name": world_config.current_world})
    )
    await bot.change_presence(status=Status.idle, activity=activity)  # type: ignore

    i = 0
    try:
        async for wol_failed in start.start_server():
            if wol_failed:
                original_message = await ctx.original_response()
                await original_message.reply(LH("commands.start.error.wol_failed"))
                i = 2
            else:
                i += 1
            await ctx.edit_original_response(content=_generate_progress_bar(i, message))

        inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
        update_players_online_status.start()
        log.info("Status Updater started!")
        await _no_longer_busy()
        return True

        # The user has done something wrong
    except utils.UserInputError as e:
        await ctx.edit_original_response(content=str(e))

    # Something went wrong with our code
    except Exception as e:
        log.error("Could not start server", exc_info=e)
        await ctx.edit_original_response(
            content=LH("commands.start.error.general", args={"e": _trim_text_for_discord_subtitle(str(e))})
        )
        await _ping_user_after_error(ctx)

    return False


def _generate_progress_bar(value: int, message: str) -> str:
    progress = "█" * value + "░" * (PROGRESS_BAR_STEPS - value)
    return f"{message}\n{progress}"


@tree.command(name="stop", description=LH("commands.stop.description"))
async def stop_server_command(ctx: discord.Interaction):
    message = LH("commands.stop.msg_above_process_bar")

    log.info("Received stop command ...")
    await ctx.response.send_message(_generate_progress_bar(1, message))  # type: ignore

    if await _stop_minecraft_server(ctx=ctx, message=message, shutdown=True):
        await ctx.edit_original_response(content=_generate_progress_bar(PROGRESS_BAR_STEPS, ""))
        await ctx.channel.send(LH("commands.stop.finished_msg"))  # type: ignore


def _trim_text_for_discord_subtitle(text: str) -> str:
    return str(text).replace("\n", " ")


@tree.command(name="add_world", description=LH("commands.add_world.description"))
async def add_world_command(
    ctx: discord.Interaction, display_name: str, start_cmd: str, start_cmd_sudo: bool, visible: bool
):
    # only allow super users
    if not await _is_super_user(ctx):
        return

    try:
        await world_selector.create_new_world(display_name, start_cmd, start_cmd_sudo, visible)
        await ctx.response.send_message(
            LH("commands.add_world.success", args={"display_name": display_name}), ephemeral=True
        )
    except Exception as e:
        log.debug(f"Could not create world | {e}")
        await ctx.response.send_message(
            LH("commands.add_world.error", args={"display_name": display_name, "e": e}),
            ephemeral=True,
        )


@tree.command(name="edit_world", description=LH("commands.edit_world.description"))
async def edit_world_command(  # noqa: PLR0913
    ctx: discord.Interaction,
    editing_world_name: str,
    new_display_name: str | None = None,
    start_cmd: str | None = None,
    sudo_start_cmd: bool | None = None,
    visible: bool | None = None,
):
    # only super users
    if not await _is_super_user(ctx):
        return

    try:
        world = await world_selector.edit_new_world(
            editing_world_name, new_display_name, start_cmd, sudo_start_cmd, visible
        )
        await ctx.response.send_message(
            LH(
                "commands.edit_world.success",
                args={
                    "editing_world_name": editing_world_name,
                    "values": await _get_formatted_world_info_string(world),
                },
            ),
            ephemeral=True,
        )
    except Exception as e:
        await ctx.response.send_message(
            LH("commands.edit_world.error", args={"editing_world_name": editing_world_name, "e": e}), ephemeral=True
        )
        log.warning(f"Couldn't edit world '{editing_world_name}' | {e}", exc_info=e)


@edit_world_command.autocomplete("editing_world_name")
async def _edit_world_command_autocomplete(interaction: discord.Interaction, current: str):
    return await _get_world_choices()


@tree.command(name="delete_world", description=LH("commands.delete_world.description"))
async def delete_world_command(ctx: discord.Interaction, display_name: str):
    if not await _is_super_user(ctx):
        return

    world_selector_config = await world_selector.get_world_selector_config()

    # prevent deletion of the current world
    if display_name in {world_selector_config.current_world, world_selector_config.new_selected_world}:
        await ctx.response.send_message(LH("commands.delete_world.error.current_world"), ephemeral=True)
        return

    # prevent deletion of non existing worlds
    if display_name not in [world.display_name for world in world_selector_config.worlds]:
        await ctx.response.send_message(
            LH("commands.delete_world.error.not_found", args={"display_name": display_name}), ephemeral=True
        )
        return

    world = await world_selector.get_world_by_name(display_name, world_selector_config)

    confirm_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.green)

    async def confirm_callback(interaction: discord.Interaction):
        try:
            await world_selector.try_delete_world(display_name)
            await ctx.edit_original_response(
                view=None, content=LH("commands.delete_world.success", args={"display_name": display_name})
            )
        except Exception as e:
            log.error(f"Could not delete world '{display_name}'", exc_info=e)
            await ctx.edit_original_response(
                view=None, content=LH("commands.delete_world.error", args={"display_name": display_name, "e": e})
            )
            return

    async def cancel_callback(interaction: discord.Interaction):
        await ctx.edit_original_response(view=None, content=LH("commands.delete_world.canceled"))

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(
        LH(
            "commands.delete_world.verification",
            args={
                "display_name": display_name,
                "values": await _get_formatted_world_info_string(world),
            },
        ),
        view=view,
        ephemeral=True,
    )


@delete_world_command.autocomplete("display_name")
async def _delete_world_command_autocomplete(interaction: discord.Interaction, current: str):
    return await _get_world_choices()


async def _get_world_choices() -> list[app_commands.Choice]:
    data = await world_selector.get_world_selector_config()
    return [app_commands.Choice(name=world.display_name, value=world.display_name) for world in data.worlds]


@tree.command(name="change_world", description=LH("commands.change_world.description"))
async def change_world_command(ctx: discord.Interaction):
    world_selector_config = await world_selector.get_world_selector_config()
    index = None
    options = []

    for world in world_selector_config.worlds:
        if not world.visible:
            continue
        options.append(discord.SelectOption(label=world.display_name, value=world.display_name))

    select = discord.ui.Select(
        placeholder=LH("commands.change_world.placeholder"), min_values=1, max_values=1, options=options
    )
    if index:
        select.options[index].default = True

    async def select_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.edit_original_response(content=LH("commands.change_world.wrong_user_error"), view=None)
            return

        selected_value = select.values[0]
        current_world_is_selected = await world_selector.select_new_world(selected_value)

        await ctx.edit_original_response(
            content=LH("commands.change_world.success_offline", args={"selected_value": selected_value}), view=None
        )
        await interaction.response.defer()

        if not ((await utils.get_server_state(CONFIG)).mc_server_running):
            await world_selector.change_world()
            await _update_bot_presence()
        elif not current_world_is_selected:
            await _change_world_now_message(ctx, selected_value)
            

    select.callback = select_callback

    select_view = discord.ui.View()
    select_view.add_item(select)

    if world_selector_config.new_selected_world:
        selected_world = world_selector_config.new_selected_world
    else:
        selected_world = world_selector_config.current_world

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message(LH("commands.change_world.response", args={"current_selected_world": selected_world}), view=select_view)


@tree.command(name="show_worlds", description=LH("commands.show_worlds.description"))
async def show_worlds_command(ctx: discord.Interaction):
    sudo = await _is_super_user(ctx, False)
    world_selector_config = await world_selector.get_world_selector_config()

    max_name_length = len(world_selector_config.worlds[0].display_name)
    for world in world_selector_config.worlds:
        if (world.visible or sudo) and len(world.display_name) > max_name_length:
            max_name_length = len(world.display_name)

    string = LH("formatting.show_worlds.title")
    for world in world_selector_config.worlds:
        if world.visible or sudo:
            if world.display_name == world_selector_config.current_world:
                string += LH("formatting.show_worlds.current_world")
            elif world.display_name == world_selector_config.new_selected_world:
                string += LH("formatting.show_worlds.new_selected_world")
            else:
                string += LH("formatting.show_worlds.not_selecetd_world")

            string += world.display_name

            if sudo:
                string += (3 + max_name_length - len(world.display_name)) * " " + str(world.visible)

    await ctx.response.send_message(string + LH("formatting.show_worlds.end"), ephemeral=sudo)


@tree.command(name="stop_without_shutdown", description=LH("commands.stop_without_shutdown.description"))
async def stop_without_shutdown_server_command(ctx: discord.Interaction):
    if not await _is_super_user(ctx):
        return
    message = LH("commands.stop_without_shutdown.msg_above_process_bar")

    log.info("Received stop command without shutdown ...")
    await ctx.response.send_message(_generate_progress_bar(1, message))  # type: ignore

    if await _stop_minecraft_server(ctx=ctx, message=message, shutdown=False):
        await ctx.edit_original_response(content=_generate_progress_bar(PROGRESS_BAR_STEPS, ""))
        await ctx.channel.send(LH("commands.stop_without_shutdown.finished_msg"))  # type: ignore


@tree.command(name="help", description=LH("commands.help.description"))
async def help_command(ctx: discord.Interaction):
    sudo = await _is_super_user(ctx, False)
    user_commands = [
        "start",
        "stop",
        "change_world",
        "restart",
        "show_worlds",
        "ping",
        "reset_busy",
        "get_players",
        "help",
    ]
    embed = discord.Embed(title=LH("commands.help.title"), color=discord.Color.blue())
    if sudo:
        embed.add_field(
            name=LH("formatting.help.subtitle", args={"subtitle": LH("commands.help.user_subtitle")}),
            value="",
            inline=False,
        )
    for user_command in user_commands:
        embed.add_field(
            name=LH("formatting.help.command", args={"command_name": user_command}),
            value=LH(
                "formatting.help.command_description", args={"description": LH(f"commands.{user_command}.description")}
            ),
            inline=False,
        )
    if sudo:
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name=LH("formatting.help.subtitle", args={"subtitle": LH("commands.help.admin_subtitle")}),
            value="",
            inline=False,
        )
        admin_commands = ["add_world", "edit_world", "delete_world", "stop_without_shutdown"]
        for admin_command in admin_commands:
            description = LH(f"commands.{admin_command}.description").replace(
                LH("formatting.help.admin_prefix_to_remove"), ""
            )
            embed.add_field(
                name=LH("formatting.help.command", args={"command_name": admin_command}),
                value=LH("formatting.help.command_description", args={"description": description}),
                inline=False,
            )
    await ctx.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="restart", description=LH("commands.restart.description"))
async def restart_command(ctx: discord.Interaction):
    message = LH("commands.restart.above_process_bar.msg")
    await ctx.response.send_message(message)
    await _restart_minecraft_server(ctx, message)


@tree.command(name="reset_busy", description=LH("commands.reset_busy.description"))
async def reset_busy_command(ctx: discord.Interaction):
    if not is_busy:
        await ctx.response.send_message(LH("commands.reset_busy.error.general"), ephemeral=True)  # type: ignore
        return False

    confirm_button = discord.ui.Button(label=LH("commands.reset_busy.reset"), style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label=LH("commands.reset_busy.cancel"), style=discord.ButtonStyle.green)

    async def confirm_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.reset_busy.error.wrong_user"),
                ephemeral=True,
            )
            return
        await _no_longer_busy()
        confirm_button.disabled = True
        cancel_button.disabled = True
        await interaction.response.edit_message(content=LH("commands.reset_busy.success"), view=view)

    async def cancel_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.reset_busy.error.wrong_user"),
                ephemeral=True,
            )
            return
        confirm_button.disabled = True
        cancel_button.disabled = True
        await interaction.response.edit_message(content=LH("commands.reset_busy.canceled"), view=view)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(LH("commands.reset_busy.verification"), view=view)


@tree.command(name="get_players", description=LH("commands.get_players.description"))
async def get_players_command(ctx: discord.Interaction):
    if CONFIG.GET_PLAYERS_COMMAND_ENABLED:
        mc_status = await utils.get_mcstatus(CONFIG)
        if mc_status is not None:
            if mc_status.players.online == 0:
                content = LH("commands.get_players.error.no_one_online")
            elif mc_status.players.sample:
                if mc_status.players.online == 1:
                    player_name = LH(
                        "formatting.get_players.player_name_line",
                        args={"player_name": mc_status.players.sample[0].name},
                    )
                    content = LH("commands.get_players.response_singular", args={"player_name": player_name})
                else:
                    player_names = ""
                    for player in mc_status.players.sample:
                        player_names += "\n" + LH(
                            "formatting.get_players.player_name_line", args={"player_name": player.name}
                        )

                    content = LH(
                        "commands.get_players.response_plural",
                        args={
                            "player_count": mc_status.players.online,
                            "player_names": player_names,
                        },
                    )

            else:
                content = LH("commands.get_players.error.disabled")
        else:
            content = LH("commands.get_players.error.offline")
    else:
        content = LH("commands.get_players.error.disabled")

    await ctx.response.send_message(content)


async def _stop_minecraft_server(ctx: discord.Interaction, message: str, shutdown: bool) -> bool:
    if not await _check_if_busy(ctx):
        return False

    mc_status = await utils.get_mcstatus(CONFIG)
    if mc_status and mc_status.players.online:
        if not await _players_online_verification(ctx, message, mc_status):
            return False

        if not await _check_if_busy(ctx):
            return False

    world_config = await world_selector.get_world_selector_config()

    update_players_online_status.stop()
    log.info("Status Updater stopped!")
    activity = await _get_discord_activity(
        "stopping", LH("status.text.stopping", args={"world_name": world_config.current_world})
    )
    await bot.change_presence(status=Status.idle, activity=activity)  # type: ignore

    i = 0
    try:
        async for _ in stop.stop_server(shutdown):
            i += 2
            await ctx.edit_original_response(content=_generate_progress_bar(i, message))
    except Exception as e:
        if isinstance(e, utils.UserInputError):
            await ctx.edit_original_response(content=str(e))
            await _update_bot_presence()
            await _no_longer_busy()
            return False
        log.error(f"Could not stop server | {e}")
        await ctx.edit_original_response(
            content=LH("commands.stop.error.general", args={"e": _trim_text_for_discord_subtitle(str(e))})
        )
        await _ping_user_after_error(ctx)
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
    if not (await utils.get_server_state(CONFIG)).mc_server_running:
        await ctx.edit_original_response(content=LH("commands.restart.error"))  # type: ignore
        return False

    log.info("Received restart command ...")
    await ctx.edit_original_response(content=_generate_progress_bar(1, message))  # type: ignore

    if await _stop_minecraft_server(
        ctx=ctx,
        message=message + LH("commands.restart.above_process_bar.stopping_addon"),
        shutdown=False,
    ):
        await ctx.edit_original_response(content=_generate_progress_bar(PROGRESS_BAR_STEPS, message))
        if await _try_start_minecraft_server(
            ctx=ctx, message=message + LH("commands.restart.above_process_bar.starting_addon")
        ):
            await ctx.edit_original_response(content=_generate_progress_bar(PROGRESS_BAR_STEPS, ""))
            await ctx.channel.send(LH("commands.restart.finished_msg"))  # type: ignore
            return True
    return False


async def _players_online_verification(ctx: discord.Interaction, message: str, mcstatus: JavaStatusResponse):
    await _no_longer_busy()
    result_future = asyncio.Future()

    confirm_button = discord.ui.Button(
        label=LH("commands.stop.error.players_online.stop_anyway"), style=discord.ButtonStyle.red
    )
    cancel_button = discord.ui.Button(
        label=LH("commands.stop.error.players_online.cancel"), style=discord.ButtonStyle.green
    )

    async def confirm_callback(interaction: discord.Interaction):
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.stop.error.players_online.wrong_user"),
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
                LH("commands.stop.error.players_online.wrong_user"),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        confirm_button.disabled = True
        cancel_button.disabled = True
        await ctx.edit_original_response(content=LH("commands.stop.error.players_online.canceled"), view=view)
        result_future.set_result(False)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    if mcstatus.players.online == 1:
        player_name = ""
        if mcstatus.players.sample:
            player_name = LH(
                "formatting.get_players.player_name_line", args={"player_name": mcstatus.players.sample[0].name}
            )
        content = (
            message
            + "\n\n"
            + LH("commands.stop.error.players_online.question_singular", args={"player_name": player_name})
        )
    else:
        player_names = ""
        if mcstatus.players.sample:
            for player in mcstatus.players.sample:
                player_names += "\n" + LH("formatting.get_players.player_name_line", args={"player_name": player.name})

        content = (
            message
            + "\n\n"
            + LH(
                "commands.stop.error.players_online.question_plural",
                args={"player_count": mcstatus.players.online, "player_names": player_names},
            )
        )
    await ctx.edit_original_response(content=content, view=view)

    result = await result_future
    return result


async def _change_world_now_message(select_interaction: discord.Interaction, selected_value: str):
    confirm_button = discord.ui.Button(label=LH("commands.change_world.restart_now"), style=discord.ButtonStyle.green)
    cancel_button = discord.ui.Button(label=LH("commands.change_world.cancel"), style=discord.ButtonStyle.gray)

    async def confirm_callback(interaction: discord.Interaction):
        if select_interaction.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.change_world.error.wrong_user"),
                ephemeral=True,
            )
            return
        button_view.remove_item(confirm_button)
        button_view.remove_item(cancel_button)
        message = (
            LH("commands.change_world.success_offline", args={"selected_value": selected_value})
            + "\n"
            + LH("commands.restart.above_process_bar.msg")
        )
        await interaction.response.edit_message(content=message, view=button_view)
        await _restart_minecraft_server(interaction, message)

    async def cancel_callback(interaction: discord.Interaction):
        if select_interaction.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.change_world.error.wrong_user"),
                ephemeral=True,
            )
            return
        button_view.remove_item(confirm_button)
        button_view.remove_item(cancel_button)
        await interaction.response.edit_message(
            content=LH("commands.change_world.success_offline", args={"selected_value": selected_value}),
            view=button_view,
        )

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    button_view = discord.ui.View()
    button_view.add_item(confirm_button)
    button_view.add_item(cancel_button)
    
    await select_interaction.edit_original_response(
        content=LH("commands.change_world.success_online", args={"selected_value": selected_value}), view=button_view
    )


async def _update_bot_presence():
    world_selector_config = await world_selector.get_world_selector_config()
    server_status = await utils.get_server_state(CONFIG)

    if server_status.mc_server_running:
        mc_status = await utils.get_mcstatus(CONFIG)
        if mc_status is None:
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
            if await _check_for_inactivity_shutdown(mc_status.players.online):
                return
        activity = await _get_discord_activity("online", text)
    elif server_status.host_server_running:
        text = LH("status.text.only_host_online", args={"world_name": world_selector_config.current_world})
        activity = await _get_discord_activity("only_host_online", text)
    else:
        text = LH("status.text.offline", args={"world_name": world_selector_config.current_world})
        activity = await _get_discord_activity("offline", text)

    status = _map_server_status_to_discord_activity(server_status)

    await bot.change_presence(status=status, activity=activity)


def _map_server_status_to_discord_activity(server_status: utils.ServerState) -> discord.Status:
    if not server_status.host_server_running:
        return discord.Status.dnd
    # After here the host server is running
    elif not server_status.mc_server_running:
        return discord.Status.idle
    else:
        return discord.Status.online


async def _get_discord_activity(
    server_status_str: str, text: str
) -> Union[discord.Game, discord.Streaming, discord.Activity, discord.BaseActivity]:
    activity_str = LH("status.activity." + server_status_str)
    if activity_str == "Game":
        return discord.Game(name=text)
    elif activity_str == "Streaming":
        return discord.Streaming(name=text, url="")
    elif activity_str == "Listening":
        return discord.Activity(type=discord.ActivityType.listening, name=text)
    elif activity_str == "Watching":
        return discord.Activity(type=discord.ActivityType.watching, name=text)
    else:
        raise TypeError(
            f"Wrong Discord Activity choosen. Use 'Game', 'Streaming', 'Listening' or 'Watching'. Not '{activity_str}'"
        )


async def _check_for_inactivity_shutdown(players_online: int):
    global inactvity_seconds  # noqa: PLW0603

    if CONFIG.INACTIVITY_SHUTDOWN_MINUTES:
        if players_online == 0:
            if inactvity_seconds >= 0:
                if inactvity_seconds == 0:
                    await _stop_inactivity()
                    return True
                inactvity_seconds -= 10
        else:
            inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
    return False


async def _stop_inactivity():
    global inactvity_seconds  # noqa: PLW0603

    if not CONFIG.DISCORD_STATUS_CHANNEL_ID:
        log.error("DISCORD_STATUS_CHANNEL_ID in .env not correct. Automatic shutdown due to inactivity not possible!")
        return False
    channel = bot.get_channel(CONFIG.DISCORD_STATUS_CHANNEL_ID)
    if not channel or not isinstance(channel, discord.TextChannel):
        raise TypeError("Could not get channel from Discord!")

    log.info("Send information message for shutdown due to inactivity ...")
    message, player_confirmed_stop = await _inactivity_shutdown_verification(channel)
    if player_confirmed_stop:
        log.info("Stopping due to inactivity ...")
        if not await _check_if_busy():
            inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
            await message.edit(content=LH("other.inactivity_shutdown.error.is_busy"))
            return
        mcstatus = await utils.get_mcstatus(CONFIG)
        if mcstatus is None:
            await _no_longer_busy()
            inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
            await message.edit(content=LH("other.inactivity_shutdown.error.offline"))
            return
        if mcstatus.players.online != 0:
            await _no_longer_busy()
            inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
            await message.edit(content=LH("other.inactivity_shutdown.error.players_online"))
            return

        inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60

        world_config = await world_selector.get_world_selector_config()
        update_players_online_status.stop()
        log.info("Status Updater stopped!")

        activity = await _get_discord_activity(
            "stopping", LH("status.text.stopping", args={"world_name": world_config.current_world})
        )
        await bot.change_presence(status=Status.idle, activity=activity)

        async for _ in stop.stop_server(True):
            pass
        await _update_bot_presence()
        await message.edit(content=LH("other.inactivity_shutdown.finished_msg"))  # type: ignore
        await _no_longer_busy()


async def _inactivity_shutdown_verification(channel: discord.TextChannel) -> tuple[discord.Message, bool]:
    result_future = asyncio.Future()

    cancel_button = discord.ui.Button(label=LH("other.inactivity_shutdown.cancel"), style=discord.ButtonStyle.green)

    async def cancel_callback(interaction: discord.Interaction):
        global inactvity_seconds  # noqa: PLW0603

        await interaction.response.defer()
        cancel_button.disabled = True
        inactvity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60
        await message.edit(
            content=LH(
                "other.inactivity_shutdown.canceled",
                args={"inactivity_shutdown_minutes": CONFIG.INACTIVITY_SHUTDOWN_MINUTES},
            ),
            view=view,
        )
        result_future.set_result(False)
        view.stop()

    cancel_button.callback = cancel_callback

    view = discord.ui.View()
    view.add_item(cancel_button)

    message = await channel.send(
        content=LH(
            "other.inactivity_shutdown.verification",
            args={"inactivity_shutdown_minutes": CONFIG.INACTIVITY_SHUTDOWN_MINUTES},
        ),
        view=view,
    )

    try:
        await asyncio.wait_for(view.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        if not result_future.done():
            result_future.set_result(True)
            cancel_button.disabled = True
            await message.edit(content=LH("other.inactivity_shutdown.stopping"), view=view)
    finally:
        result = await result_future
        if result:
            return message, True
        else:
            return message, False


async def _get_formatted_world_info_string(world: world_selector.WorldSelectorWorld):
    string = LH("formatting.sudo_world_info.start")

    attributes = ["display_name", "start_cmd", "start_cmd_sudo", "visible"]
    for attr in attributes:
        string += LH(
            "formatting.sudo_world_info.line",
            args={"attr": attr, "value": str(getattr(world, attr)), "gap_filler": ((15 - len(attr)) * " ")},
        )
    return string + LH("formatting.sudo_world_info.end")


async def _ping_user_after_error(ctx: discord.Interaction):
    user_mention = ctx.user.mention
    await ctx.followup.send(content=f"{user_mention}", ephemeral=False)


async def _check_if_busy(ctx: discord.Interaction | None = None) -> bool:
    global is_busy  # noqa: PLW0603

    if is_busy:
        if ctx is not None:
            await ctx.edit_original_response(content=LH("other.busy"))  # type: ignore
        return False
    else:
        is_busy = True
        return True


async def _no_longer_busy():
    global is_busy  # noqa: PLW0603

    is_busy = False


async def _is_super_user(ctx: discord.Interaction, message: bool = True):
    super_users = [user.strip() for user in CONFIG.DISCORD_SUPER_USER_ID.split(";") if user.strip()]
    for super_user in super_users:
        if ctx.user.id == int(super_user):
            return True

    if message:
        await ctx.response.send_message(LH("other.sudo"), ephemeral=True)
    return False


@tasks.loop(seconds=10)
async def update_players_online_status():
    await _update_bot_presence()


def main(config: Config = CONFIG):
    log.info("Starting bot ...")
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
