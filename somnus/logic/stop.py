from typing import AsyncGenerator

from somnus.actions.stop_mc import stop_mc_server
from somnus.actions.stop_host import stop_host_server
from somnus.config import Config, CONFIG
from somnus.logger import log
from somnus.actions.stats import get_server_state
from somnus.actions.ssh import ssh_login
from somnus.language_handler import LH
from somnus.logic.errors import UserInputError


async def stop_server(shutdown: bool, config: Config = CONFIG) -> AsyncGenerator:
    """
    Raises:
        UserInputError: If the user input is invalid.
        MCServerStartError: If MC server could not be started.
        HostServerStartError: If host server could not be started.
    """

    ssh = await ssh_login(config)
    server_state = await get_server_state(config)
    log.info(
        f"Host server running: {server_state.host_server_running} | MC server running: {server_state.mc_server_running}"
    )

    if not (server_state.host_server_running or server_state.mc_server_running):
        raise UserInputError(LH("commands.stop.error.already_stopped"))
    elif not shutdown and not server_state.mc_server_running:
        raise UserInputError(LH("commands.stop.error.mc_already_stopped"))

    yield

    # Stop MC server
    if server_state.mc_server_running:
        log.debug("Stopping MC server ...")
        async for _ in stop_mc_server(ssh, config):
            yield
    else:
        for _ in range(5):
            yield
    yield

    # Stop host server
    if server_state.host_server_running and shutdown and config.HOST_SERVER_HOST not in ["localhost", "127.0.0.1"]:
        await stop_host_server(ssh, config)
    yield

    ssh.sendline("exit")
    ssh.close()
    yield
