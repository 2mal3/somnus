import asyncio

from ping3 import ping
from wakeonlan import send_magic_packet
from pexpect import pxssh
from pexpect.exceptions import TIMEOUT

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.logic.world_selecter import get_current_world
from somnus.logic.utils import (
    ServerState,
    get_server_state,
    ssh_login,
    UserInputError,
    send_possible_sudo_command,
    get_host_sever_state,
)


async def start_server(config: Config = CONFIG):
    host_server_state, mc_server_state = await get_server_state(config)
    log.debug(f"Host server state: {host_server_state.value} | MC server state: {mc_server_state.value}")

    if ServerState.STOPPED not in (host_server_state, mc_server_state):
        raise UserInputError("Server is already running")
    yield

    # Start host server
    if host_server_state == ServerState.STOPPED:
        log.debug("Starting host server ...")

        try:
            async for _ in _start_host_server(config):
                yield

        except Exception as e:
            raise RuntimeError(f"Could not start host server | {e}")
    yield

    # Start MC server
    log.debug("Starting MC server ...")
    ssh = await ssh_login(config)
    yield

    try:
        async for _ in _start_mc_server(config, ssh):
            yield
    # Cancel screen session if MC server could not be started so we don't open useless screens
    except Exception as e:
        ssh.sendline("exit")
        await send_possible_sudo_command(ssh, config, "screen -X -S mc-server-control quit")  # close screen
        ssh.expect("@")
        ssh.logout()
        raise RuntimeError(f"Could not start MC server | {e}")

    log.debug("Logging out ...")
    # Exit screen session
    await _detach_screen_session(ssh)
    ssh.prompt()

    ssh.logout()


async def _start_host_server(config: Config):
    wol_speed = 5
    ping_speed = 15

    for _ in range(5):
        send_magic_packet(config.HOST_SERVER_MAC)
        await asyncio.sleep(wol_speed)
    yield

    for _ in range(ping_speed):
        await asyncio.sleep(300 // ping_speed)

        host_server_state = get_host_sever_state(config)
        if host_server_state == ServerState.RUNNING:
            return

        log.warning("Could not connect to host server, trying again...")

    raise TimeoutError("Could not start host server")


async def _start_mc_server(config: Config, ssh: pxssh.pxssh):
    log.debug("Starting screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -S mc-server-control")
    yield

    log.debug("Send MC server start command ...")
    # OLD: ssh.sendline(config.MC_SERVER_START_CMD)
    ssh.sendline((await get_current_world())["start_cmd"]) # NEW
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
        index = ssh.expect(["Done"] + message)
        if index == 0:
            for j in range(i, len(messages)):
                yield
            return
        yield


async def _detach_screen_session(ssh: pxssh.pxssh):
    ssh.sendcontrol("a")
    await asyncio.sleep(0.1)
    ssh.sendcontrol("d")


async def main():
    async for _ in start_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
