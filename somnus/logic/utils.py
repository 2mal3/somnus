import asyncio

from mcstatus import JavaServer
from pexpect import pxssh
from ping3 import ping
from pydantic import BaseModel

from somnus.environment import CONFIG, Config
from somnus.logger import log
from somnus.logic.world_selector import get_current_world


class ServerState(BaseModel):
    host_server_running: bool
    mc_server_running: bool


class UserInputError(Exception):
    pass


async def get_mcstatus(config: Config) -> JavaServer.status:
    try:
        server = await JavaServer.async_lookup(config.MC_SERVER_ADDRESS)
        return server.status()
    except Exception as e:
        if (not isinstance(e, OSError)) and (not isinstance(e, TimeoutError)):
            log.error(f"Couldn't get mcstatus: {e}")
        return None


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
                port=config.HOST_SERVER_SSH_PORT,
                login_timeout=5,
            )
            break
        except Exception as e:
            log.warning(f"Could not connect to host server | '{e}'")

        if tries == (attempts - 1):
            raise TimeoutError("Could not establish SSH connection to host server")
        await asyncio.sleep(5)

    if not _screen_is_installed(ssh):
        log.fatal("Screen is not installed on host server")

    return ssh


def _screen_is_installed(ssh: pxssh.pxssh) -> ServerState:
    ssh.sendline("command -v screen")
    ssh.prompt()
    ssh.sendline("echo $?")
    ssh.prompt()

    exit_status = int(ssh.before.splitlines()[-2])
    return exit_status == 0


async def send_possible_sudo_command(ssh: pxssh.pxssh, config: Config, command: str):
    if not (await get_current_world()).start_cmd_sudo:
        ssh.sendline(command)
    else:
        await send_sudo_command(ssh, config, command)


async def send_sudo_command(ssh: pxssh.pxssh, config: Config, command: str):
    ssh.sendline(f"sudo {command}")
    choice = ssh.expect(["sudo", "@"])
    if choice == 0:
        ssh.sendline(config.HOST_SERVER_PASSWORD)


async def get_server_state(config: Config) -> ServerState:
    host_server_running = await _is_host_server_running(config)
    if not host_server_running:
        return ServerState(host_server_running=False, mc_server_running=False)

    mc_server_running = await _is_mc_server_running(config)

    return ServerState(host_server_running=host_server_running, mc_server_running=mc_server_running)


async def _is_mc_server_running(config: Config) -> bool:
    try:
        server = await JavaServer.async_lookup(config.MC_SERVER_ADDRESS, timeout=5)
        await server.async_status()
    except (OSError, TimeoutError):
        return False

    return True


async def _is_host_server_running(config: Config) -> bool:
    host_server_running = ping(config.HOST_SERVER_HOST)

    if not host_server_running:
        return False

    try:
        ssh = await ssh_login(config)
        ssh.logout()
    except TimeoutError:
        return False

    return True


async def detach_screen_session(ssh: pxssh.pxssh):
    ssh.sendcontrol("a")
    await asyncio.sleep(0.1)
    ssh.sendcontrol("d")


async def kill_screen(ssh: pxssh.pxssh, config: Config = CONFIG):
    await send_possible_sudo_command(ssh, config, "screen -X -S mc-server-control quit")
