import asyncio

from asyncer import asyncify
from ping3 import ping
from wakeonlan import send_magic_packet
from pexpect import pxssh

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.logic.utils import ServerState, get_server_state, ssh_login, UserInputError, send_possible_sudo_command, \
    exit_screen


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
        await exit_screen(ssh)
        await send_possible_sudo_command(ssh, config, "screen -X -S mc-server-control quit")
        ssh.prompt()
        ssh.logout()
        raise RuntimeError(f"Could not start MC server | {e}")

    log.debug("Logging out ...")
    await exit_screen(ssh)
    ssh.prompt()
    ssh.logout()


async def _start_host_server(config: Config):
    speed = 5

    for _ in range(5):
        send_magic_packet(config.HOST_SERVER_MAC)
        await asyncio.sleep(speed)
    yield

    for _ in range(5):
        await asyncio.sleep(300 // speed)

        if await asyncify(ping)(config.HOST_SERVER_HOST, timeout=speed):
            return
        log.warn("Could not start host server, trying again...")

    raise TimeoutError("Could not start host server")


async def _start_mc_server(config: Config, ssh: pxssh.pxssh):
    log.debug("Starting screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -S mc-server-control")
    yield

    log.debug("Send MC server start command ...")
    ssh.sendline(config.MC_SERVER_START_CMD)
    yield

    log.debug("Waiting for MC server to start ...")
    messages = [
        ["Starting", "running"],
        ["Loading libraries", "Loading"],
        ["Environment", "Preparing"],
        ["Preparing level", "Done"],
        ">"
    ]
    for i, message in enumerate(messages):
        ssh.expect(message)
        yield


async def main():
    async for _ in start_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
