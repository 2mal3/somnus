import asyncio
from enum import Enum

from asyncer import asyncify
from mcstatus import JavaServer

from pexpect import pxssh
from ping3 import ping

from somuns.environment import Config
from somuns.logger import log


class ServerState(Enum):
    RUNNING = "running"
    STOPPED = "stopped"


class UserInputError(Exception):
    pass


async def ssh_login(config: Config) -> pxssh.pxssh:
    ssh = pxssh.pxssh()

    attempts = 3
    for tries in range(attempts):
        try:
            ssh.login(
                config.HOST_SERVER_HOST,
                config.HOST_SERVER_USER,
                config.HOST_SERVER_PASSWORD,
                login_timeout=5,
            )
            break
        except Exception as e:
            log.warning(f"Could not connect to host server | '{e}'")

        if tries == (attempts - 1):
            raise TimeoutError("Could not establish SSH connection to host server")
        await asyncio.sleep(5)

    return ssh


async def get_server_state(config: Config) -> tuple[ServerState, ServerState]:
    # Host server not running
    host_server_running = await asyncify(ping)(config.HOST_SERVER_HOST)
    if not host_server_running:
        return ServerState.STOPPED, ServerState.STOPPED

    # Host server running, but MC server not running
    try:
        server = await JavaServer.async_lookup(config.MC_SERVER_ADDRESS, timeout=5)
        await server.async_status()
    except OSError:
        return ServerState.RUNNING, ServerState.STOPPED

    # Host server and MC server running
    return ServerState.RUNNING, ServerState.RUNNING
