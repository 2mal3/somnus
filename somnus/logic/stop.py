import asyncio

from pexpect import pxssh

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.language_handler import LH
from somnus.logic.utils import (
    ServerState,
    get_server_state,
    ssh_login,
    UserInputError,
    send_possible_sudo_command,
    send_sudo_command,
    detach_screen_session,
    kill_screen,
)


async def stop_server(shutdown: ServerState, config: Config = CONFIG):
    ssh = await ssh_login(config)
    server_state = await get_server_state(config)
    log.debug(
        f"Host server running: {server_state.host_server_running} | MC server running: {server_state.mc_server_running}"
    )

    if not (server_state.host_server_running or server_state.mc_server_running):
        raise UserInputError(LH.t("commands.stop.error.already_stopped"))
    elif not shutdown and not server_state.mc_server_running:
        raise UserInputError(LH.t("commands.stop.error.mc_already_stopped"))

    yield

    # Stop MC server
    if server_state.mc_server_running:
        async for _ in _stop_mc_server(ssh, config):
            yield
    else:
        for _ in range(5):
            yield
    yield

    # Stop host server
    if server_state.host_server_running and shutdown and not config.DEBUG:
        try:
            await send_sudo_command(ssh, config, "shutdown -h now")
        except Exception as e:
            raise RuntimeError(f"Could not stop host server | {e}")
    yield

    ssh.sendline("exit")
    ssh.logout()
    yield


async def _try_stop_mc_server(ssh: pxssh.pxssh, config: Config):
    await send_possible_sudo_command(ssh, config, "screen -r mc-server-control")
    yield

    try:
        async for _ in _stop_mc_server(ssh, config):
            yield
    except Exception as e:
        raise RuntimeError(f"Could not stop MC server | {e}")
    finally:
        log.debug("Exiting screen session ...")
        await detach_screen_session(ssh)
        await kill_screen(ssh, config)


async def _stop_mc_server(ssh: pxssh.pxssh, config: Config):
    server_shutdown_maximum_time = 600
    log.debug("Connecting to screen session ...")

    await send_possible_sudo_command(ssh, config, "screen -r mc-server-control")
    yield

    log.debug("Sending stop command ...")

    ssh.sendline("stop")

    messages = ["overworld", "nether", "end", "@"]
    for i, message in enumerate(messages):
        found_element_index = ssh.expect(["@", message], timeout=server_shutdown_maximum_time)
        log.debug(f"Stage '{message}' completed")

        if found_element_index == 0:
            for _ in range(i, len(messages)):
                yield
            return
        yield


async def main():
    async for _ in stop_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
