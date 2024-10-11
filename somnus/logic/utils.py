import asyncio
from enum import Enum

from mcstatus import JavaServer

from pexpect import pxssh
from ping3 import ping

from somnus.environment import Config
from somnus.logger import log


class ServerState(Enum):
    RUNNING = "running"
    STOPPED = "stopped"


class UserInputError(Exception):
    pass


async def ssh_login(config: Config) -> pxssh.pxssh:
    """
    Raises:
        TimeoutError: Could not establish a SSH connection to the server
    """

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


async def send_possible_sudo_command(ssh: pxssh.pxssh, config: Config, command: str):
    if config.MC_SERVER_START_CMD_SUDO != "true":
        ssh.sendline(command)
    else:
        await send_sudo_command(ssh, config, command)


async def send_sudo_command(ssh: pxssh.pxssh, config: Config, command: str):
    ssh.sendline(f"sudo {command}")
    ssh.expect("sudo")
    ssh.sendline(config.HOST_SERVER_PASSWORD)


async def get_server_state(config: Config) -> tuple[ServerState, ServerState]:
    host_server_state = await get_host_sever_state(config)
    if host_server_state == ServerState.STOPPED:
        return ServerState.STOPPED, ServerState.STOPPED

    mc_server_state = await _get_mc_server_state(config)

    return host_server_state, mc_server_state


async def _get_mc_server_state(config: Config) -> ServerState:
    try:
        server = await JavaServer.async_lookup(config.MC_SERVER_ADDRESS, timeout=5)
        await server.async_status()
    except OSError:
        return ServerState.STOPPED

    return ServerState.RUNNING


async def get_host_sever_state(config: Config) -> ServerState:
    host_server_running = ping(config.HOST_SERVER_HOST)
    if not host_server_running:
        return ServerState.STOPPED

    try:
        ssh = await ssh_login(config)
        ssh.logout()
    except TimeoutError:
        return ServerState.STOPPED

    return ServerState.RUNNING
