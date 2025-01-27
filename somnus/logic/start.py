import asyncio

from pexpect import pxssh
from wakeonlan import send_magic_packet

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.language_handler import LH
from somnus.logic.utils import (
    get_server_state,
    ssh_login,
    UserInputError,
    send_possible_sudo_command,
    detach_screen_session,
    kill_screen,
)
from somnus.logic.world_selector import get_current_world


async def start_server(config: Config = CONFIG):
    server_state = await get_server_state(config)
    log.info(
        f"Host server running: {server_state.host_server_running} | MC server running: {server_state.mc_server_running}"
    )

    if server_state.host_server_running and server_state.mc_server_running:
        raise UserInputError(LH.t("commands.start.error.already_running"))
    yield

    # Start host server
    if not server_state.host_server_running:
        log.debug("Starting host server ...")

        try:
            async for _ in _start_host_server(config):
                yield

        except Exception as e:
            raise RuntimeError(f"Could not start host server | {e}")
    else:
        for _ in range(9):
            yield
    yield

    # Start MC server
    async for _ in _try_start_mc_server_with_ssh(config):
        yield


async def _try_start_mc_server_with_ssh(config: Config):
    ssh = await ssh_login(config)

    log.debug("Starting screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -S mc-server-control")
    yield

    try:
        async for _ in _start_mc_server(ssh):
            yield

        # Exit peacefully
        log.debug("Logging out ...")
        await detach_screen_session(ssh)
        ssh.prompt()
        ssh.logout()
        yield

    # Exit in error, kill screen
    except Exception as e:
        await detach_screen_session(ssh)
        await kill_screen(ssh, config)
        ssh.prompt()
        ssh.logout()
        raise RuntimeError(f"Could not start MC server | {e}")


async def _start_host_server(config: Config):
    ping_speed = 30
    ping_timeout = 300

    await _send_wol_packet(config)
    yield

    for i in range(ping_speed):
        await asyncio.sleep((ping_timeout * 2) // ping_speed)

        if (await get_server_state(config)).host_server_running:
            for j in range(i, ping_speed):
                if j % 4:
                    yield
            return
        if i == ping_speed // 2:
            # an discord_provider.py geben, dass Server ggf. nicht gestartet wurde und Start erneut versucht wird
            yield True
            await _send_wol_packet(config)

        if i % 4:
            yield
        log.warning("Could not connect to host server, trying again...")

    raise TimeoutError("Could not start host server")


async def _send_wol_packet(config: Config):
    wol_send_delay_seconds = 5
    wol_packed_amount = 10

    if config.HOST_SERVER_MAC != "":
        for _ in range(wol_packed_amount):
            send_magic_packet(config.HOST_SERVER_MAC)
            await asyncio.sleep(wol_send_delay_seconds)


async def _start_mc_server(ssh: pxssh.pxssh):
    log.debug("Send MC server start command ...")
    ssh.sendline((await get_current_world()).start_cmd)
    yield

    log.debug("Waiting for MC server to start ...")
    messages = [
        ["Starting", "running"],
        ["Loading libraries", "Loading"],
        ["Environment", "Preparing"],
        ["Preparing level", ">"],
        [],
    ]
    for i, message in enumerate(messages):
        try:
            found_element_index = ssh.expect(["Done"] + message, timeout=150)
            log.debug(f"Stage '{message}' completed")

            if found_element_index == 0:  # if finished earlier, animate the progress bar to its end
                for _ in range(i, len(messages)):
                    yield
                return
            yield
        except TimeoutError as e:
            raise TimeoutError(f"Minecraft-Server could not be startet. Timeout in starting keyword expecting {e}")


async def main():
    async for _ in start_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
