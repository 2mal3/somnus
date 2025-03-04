import asyncio
from typing import AsyncGenerator

from pexpect import pxssh
from wakeonlan import send_magic_packet

from somnus.config import Config, CONFIG
from somnus.logger import log
from somnus.logic.utils import (
    get_server_state,
    ssh_login,
    UserInputError,
    send_possible_sudo_command,
    detach_screen_session,
    kill_screen,
)
from somnus.language_handler import LH
from somnus.logic.world_selector import get_current_world


async def start_server(config: Config = CONFIG) -> AsyncGenerator:
    server_state = await get_server_state(config)
    log.info(
        f"Host server running: {server_state.host_server_running} | MC server running: {server_state.mc_server_running}"
    )

    if server_state.host_server_running and server_state.mc_server_running:
        raise UserInputError(LH("commands.start.error.already_running"))
    yield

    # Start host server
    if not server_state.host_server_running:
        log.debug("Starting host server ...")

        try:
            async for _ in _start_host_server(config):
                yield

        except Exception:
            log.warning("Could not connect to host server. Send WOL packages again and retry.")
            yield True
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


async def _try_start_mc_server_with_ssh(config: Config) -> AsyncGenerator:
    ssh = await ssh_login(config)

    log.debug("Starting screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -S mc-server-control")
    yield

    try:
        async for _ in _start_mc_server(ssh):
            yield

        # Exit peacefully
        log.debug("Detaching screen ...")
        await detach_screen_session(ssh)
        ssh.prompt()
        log.debug("Logging out ...")
        ssh.logout()
        yield

    # Exit in error, kill screen
    except Exception as exception1:
        try:
            log.debug("Problem occurred, try to gracefully exit ...", exc_info=exception1)
            await detach_screen_session(ssh)
            ssh.prompt()
            await kill_screen(ssh, config)
            ssh.prompt()
            ssh.close()
            raise RuntimeError(f"Could not start MC server | {exception1}")

        except Exception as exception2:
            log.error("Could not gracefully exit", exc_info=exception2)
            ssh.close()
            raise RuntimeError(f"Could not start MC server and exit gracefully | E1: {exception1} | E2: {exception2}")


async def _start_host_server(config: Config) -> AsyncGenerator:
    ping_count = 2 if config.DEBUG else 15
    ping_timeout_seconds = 5 if config.DEBUG else 300

    await _send_wol_packet(config)
    yield

    for i in range(ping_count):
        await asyncio.sleep(ping_timeout_seconds // ping_count)

        if (await get_server_state(config)).host_server_running:
            for j in range(i, ping_count):
                if j % 2:
                    yield
            return

        if i % 2:
            yield

        log.warning("Could not connect to host server, trying again...")

    raise TimeoutError("Could not start host server")


async def _send_wol_packet(config: Config) -> None:
    wol_send_delay_seconds = 5
    wol_packed_amount = 10

    if config.HOST_SERVER_MAC != "":
        for _ in range(wol_packed_amount):
            send_magic_packet(config.HOST_SERVER_MAC)
            await asyncio.sleep(wol_send_delay_seconds)


async def _start_mc_server(ssh: pxssh.pxssh) -> AsyncGenerator:
    log_search_timeout_seconds = 150

    log.debug("Send MC server start command ...")
    ssh.sendline((await get_current_world()).start_cmd)
    yield

    log.debug("Waiting for MC server to start ...")
    messages = [
        ["Starting", "running"],
        ["Loading libraries", "Loading"],
        ["Environment", "Preparing"],
        ["Preparing level"],
        [],
    ]
    for i, message in enumerate(messages):
        try:
            found_element_index = ssh.expect(["Done"] + message, timeout=log_search_timeout_seconds)
            log.debug(f"Stage '{message}' completed")

            if found_element_index == 0:  # if finished earlier, animate the progress bar to its end
                for _ in range(i, len(messages)):
                    yield
                return
            yield
        except TimeoutError as e:
            raise TimeoutError(f"Minecraft-Server could not be startet. Timeout in starting keyword expecting {e}")


async def main() -> None:
    async for _ in start_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
