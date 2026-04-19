import asyncio
from typing import AsyncGenerator

import aiofiles
import discord
import toml
from discord import app_commands
from discord.ext import tasks
from mcstatus.status_response import JavaStatusResponse

from somnus.actions import ssh, start_mc, stats, stop_mc
from somnus.config import CONFIG
from somnus.discord_provider.action_warpper import ActionWrapperProperties, action_wrapper
from somnus.discord_provider.bot import bot
from somnus.discord_provider.busy_provider import busy_provider
from somnus.discord_provider.inactivity_shutdown import check_and_shutdown_for_inactivity, inactivity_provider
from somnus.discord_provider.update_bot_presence import update_bot_presence
from somnus.language_handler import LH
from somnus.logger import log
from somnus.logic import start, stop, world_selector

tree = app_commands.CommandTree(bot)


@bot.event
async def on_ready() -> None:
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

    if CONFIG.INACTIVITY_SHUTDOWN_MINUTES:
        inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60

    await hartbeat.start()


@tree.command(name="ping", description=LH("commands.ping.description"))
async def ping_command(ctx: discord.Interaction) -> None:
    version = ""
    async with aiofiles.open("pyproject.toml", "r") as file:
        toml_data = await file.read()
        data = toml.loads(toml_data)
        version = "v" + data["project"]["version"]

    await ctx.response.send_message(LH("commands.ping.response", args={"version": version}))


@tree.command(name="start", description=LH("commands.start.description"))
async def start_server_command(ctx: discord.Interaction) -> None:
    world_config = await world_selector.get_world_selector_config()

    action_props = ActionWrapperProperties(
        func=lambda: start.start_server(CONFIG),
        ctx=ctx,
        activity=LH("status.text.starting", args={"world_name": world_config.current_world}),
        progress_message=LH("commands.start.msg_above_process_bar"),
        finish_message=LH("commands.start.finished_msg"),
    )

    try:
        await action_wrapper(action_props)
    except Exception:
        pass
    else:
        if CONFIG.INACTIVITY_SHUTDOWN_MINUTES:
            inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60


@tree.command(name="stop", description=LH("commands.stop.description"))
async def stop_server_command(ctx: discord.Interaction) -> None:
    await _stop_server(ctx, prevent_host_shutdown=False)


@tree.command(name="stop_without_shutdown", description=LH("commands.stop_without_shutdown.description"))
async def stop_without_shutdown_command(ctx: discord.Interaction) -> None:
    if not await _is_super_user(ctx):
        return
    await _stop_server(ctx, prevent_host_shutdown=True)


async def _stop_server(ctx: discord.Interaction, prevent_host_shutdown: bool) -> None:
    message = LH("commands.stop.msg_above_process_bar")

    mc_status = await stats.get_mcstatus(CONFIG)
    if (
        mc_status
        and mc_status.players.online
        and not await _players_online_verification_for_stop(ctx, message, mc_status)
    ):
        return

    world_config = await world_selector.get_world_selector_config()

    props = ActionWrapperProperties(
        func=lambda: stop.stop_server(prevent_host_shutdown, CONFIG),
        ctx=ctx,
        activity=LH("status.text.stopping", args={"world_name": world_config.current_world}),
        progress_message=message,
        finish_message=LH("commands.stop.finished_msg"),
    )

    try:
        await action_wrapper(props)
    except Exception:
        pass
    finally:
        # Its now safe to change the world if it was requested
        await world_selector.change_world()


@tree.command(name="add_world", description=LH("commands.add_world.description"))
async def add_world_command(ctx: discord.Interaction, display_name: str, start_cmd: str, visible: bool) -> None:
    # only allow super users
    if not await _is_super_user(ctx):
        return

    try:
        await world_selector.create_new_world(display_name, start_cmd, visible)
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
async def edit_world_command(
    ctx: discord.Interaction,
    editing_world_name: str,
    new_display_name: str | None = None,
    start_cmd: str | None = None,
    visible: bool | None = None,
) -> None:
    # only super users
    if not await _is_super_user(ctx):
        return

    try:
        world = await world_selector.edit_new_world(editing_world_name, new_display_name, start_cmd, visible)
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
async def _edit_world_command_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
    return await _get_world_choices()


@tree.command(name="delete_world", description=LH("commands.delete_world.description"))
async def delete_world_command(ctx: discord.Interaction, display_name: str) -> None:
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

    async def confirm_callback(interaction: discord.Interaction) -> None:
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

    async def cancel_callback(interaction: discord.Interaction) -> None:
        await ctx.edit_original_response(view=None, content=LH("commands.delete_world.canceled"))

    confirm_button.callback = confirm_callback  # ty: ignore
    cancel_button.callback = cancel_callback  # ty: ignore

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
async def _delete_world_command_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice]:
    return await _get_world_choices()


async def _get_world_choices() -> list[app_commands.Choice]:
    data = await world_selector.get_world_selector_config()
    return [app_commands.Choice(name=world.display_name, value=world.display_name) for world in data.worlds]


@tree.command(name="change_world", description=LH("commands.change_world.description"))
async def change_world_command(ctx: discord.Interaction) -> None:
    world_selector_config = await world_selector.get_world_selector_config()
    options = []

    for world in world_selector_config.worlds:
        if not world.visible:
            continue
        options.append(discord.SelectOption(label=world.display_name, value=world.display_name))

    select = discord.ui.Select(
        placeholder=LH("commands.change_world.placeholder"), min_values=1, max_values=1, options=options
    )

    async def select_callback(interaction: discord.Interaction) -> None:
        if ctx.user.id != interaction.user.id:
            await interaction.edit_original_response(content=LH("commands.change_world.wrong_user_error"), view=None)
            return

        selected_value = select.values[0]
        await world_selector.select_new_world(selected_value)

        await ctx.edit_original_response(
            content=LH("commands.change_world.success_offline", args={"selected_value": selected_value}), view=None
        )
        await interaction.response.defer()

        if not (await stats.get_server_state(CONFIG)).mc_server_running:
            await world_selector.change_world()
            await update_bot_presence()

    select.callback = select_callback  # ty: ignore

    select_view = discord.ui.View()
    select_view.add_item(select)

    selected_world = world_selector_config.new_selected_world or world_selector_config.current_world

    # Sende die Nachricht mit dem Dropdown-Menü
    await ctx.response.send_message(
        LH("commands.change_world.response", args={"current_selected_world": selected_world}), view=select_view
    )


@tree.command(name="show_worlds", description=LH("commands.show_worlds.description"))
async def show_worlds_command(ctx: discord.Interaction) -> None:
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


@tree.command(name="help", description=LH("commands.help.description"))
async def help_command(ctx: discord.Interaction) -> None:
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


@tree.command(name="reset_busy", description=LH("commands.reset_busy.description"))
async def reset_busy_command(ctx: discord.Interaction) -> bool | None:
    if not busy_provider.is_busy():
        await ctx.response.send_message(LH("commands.reset_busy.error.general"), ephemeral=True)
        return False

    confirm_button = discord.ui.Button(label=LH("commands.reset_busy.reset"), style=discord.ButtonStyle.red)
    cancel_button = discord.ui.Button(label=LH("commands.reset_busy.cancel"), style=discord.ButtonStyle.green)

    async def confirm_callback(interaction: discord.Interaction) -> None:
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.reset_busy.error.wrong_user"),
                ephemeral=True,
            )
            return
        busy_provider.make_available()
        confirm_button.disabled = True
        cancel_button.disabled = True
        await interaction.response.edit_message(content=LH("commands.reset_busy.success"), view=view)

    async def cancel_callback(interaction: discord.Interaction) -> None:
        if ctx.user.id != interaction.user.id:
            await interaction.response.send_message(
                LH("commands.reset_busy.error.wrong_user"),
                ephemeral=True,
            )
            return
        confirm_button.disabled = True
        cancel_button.disabled = True
        await interaction.response.edit_message(content=LH("commands.reset_busy.canceled"), view=view)

    confirm_button.callback = confirm_callback  # ty: ignore
    cancel_button.callback = cancel_callback  # ty: ignore

    view = discord.ui.View()
    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.response.send_message(LH("commands.reset_busy.verification"), view=view)


@tree.command(name="get_players", description=LH("commands.get_players.description"))
async def get_players_command(ctx: discord.Interaction) -> None:
    if CONFIG.GET_PLAYERS_COMMAND_ENABLED:
        mc_status = await stats.get_mcstatus(CONFIG)
        if mc_status:
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


@tree.command(name="restart", description=LH("commands.restart.description"))
async def restart_command(ctx: discord.Interaction) -> None:
    if not (await stats.get_server_state(CONFIG)).mc_server_running:
        await ctx.response.send_message(content=LH("commands.restart.error"))
        return

    message = LH("commands.restart.above_process_bar.msg")

    mc_status = await stats.get_mcstatus(CONFIG)
    if (
        mc_status
        and mc_status.players.online
        and not await _players_online_verification_for_stop(ctx, message, mc_status)
    ):
        return

    props = ActionWrapperProperties(
        func=_restart,
        ctx=ctx,
        activity=LH("status.text.restarting"),
        progress_message=message,
        finish_message=LH("commands.restart.finished_msg"),
    )

    try:
        await action_wrapper(props)
    except Exception:
        pass
    else:
        if CONFIG.INACTIVITY_SHUTDOWN_MINUTES:
            inactivity_provider.inactivity_seconds = CONFIG.INACTIVITY_SHUTDOWN_MINUTES * 60


async def _restart() -> AsyncGenerator:
    ssh_client = await ssh.ssh_login(CONFIG)
    async for _ in stop_mc.stop_mc_server(ssh_client, CONFIG):
        yield
        yield
    await world_selector.change_world()
    async for _ in start_mc.start_mc_server(CONFIG):
        yield
    ssh_client.close()


async def _players_online_verification_for_stop(
    ctx: discord.Interaction, message: str, mcstatus: JavaStatusResponse
) -> None:
    result_future = asyncio.Future()

    confirm_button = discord.ui.Button(
        label=LH("commands.stop.error.players_online.stop_anyway"), style=discord.ButtonStyle.red
    )
    cancel_button = discord.ui.Button(
        label=LH("commands.stop.error.players_online.cancel"), style=discord.ButtonStyle.green
    )

    async def confirm_callback(interaction: discord.Interaction) -> None:
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

    async def cancel_callback(interaction: discord.Interaction) -> None:
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

    confirm_button.callback = confirm_callback  # ty: ignore
    cancel_button.callback = cancel_callback  # ty: ignore

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
    await ctx.response.send_message(content=content, view=view)

    result = await result_future
    return result


async def _get_formatted_world_info_string(world: world_selector.WorldSelectorWorld) -> str:
    string = LH("formatting.sudo_world_info.start")

    attributes = ["display_name", "start_cmd", "start_cmd_sudo", "visible"]
    for attr in attributes:
        string += LH(
            "formatting.sudo_world_info.line",
            args={"attr": attr, "value": str(getattr(world, attr)), "gap_filler": ((15 - len(attr)) * " ")},
        )
    return string + LH("formatting.sudo_world_info.end")


async def _is_super_user(ctx: discord.Interaction, message: bool = True) -> bool:
    super_users = [user.strip() for user in CONFIG.DISCORD_SUPER_USER_ID.split(";") if user.strip()]
    for super_user in super_users:
        if ctx.user.id == int(super_user):
            return True

    if message:
        await ctx.response.send_message(LH("other.sudo"), ephemeral=True)
    return False


@tasks.loop(seconds=10)
async def hartbeat() -> None:
    try:
        await update_bot_presence()
        if CONFIG.INACTIVITY_SHUTDOWN_MINUTES:
            await check_and_shutdown_for_inactivity()
    except Exception as e:
        log.error("Failed to update bot presence and inactivity", exc_info=e)


def main() -> None:
    log.info("Starting bot ...")
    bot.run(CONFIG.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
