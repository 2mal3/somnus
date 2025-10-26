import asyncio

from pexpect import pxssh

from somnus.config import Config, CONFIG
from somnus.logger import log
from somnus.logic.world_selector import get_current_world


async def ssh_login(config: Config) -> pxssh.pxssh:
    """
    Raises:
        TimeoutError: Could not establish a SSH connection to the server
    """

    attempts = 2 if config.DEBUG else 10
    seconds_between_attempts = 1 if config.DEBUG else 5
    ssh = pxssh.pxssh()

    for tries in range(attempts):
        try:
            ssh = pxssh.pxssh()
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
        await asyncio.sleep(seconds_between_attempts)

    return ssh


async def send_possible_sudo_command(ssh: pxssh.pxssh, config: Config, command: str) -> None:
    if not (await get_current_world()).start_cmd_sudo:
        ssh.sendline(command)
    else:
        await send_sudo_command(ssh, config, command)


async def send_sudo_command(ssh: pxssh.pxssh, config: Config, command: str) -> None:
    ssh.sendline(f"sudo {command}")
    choice = ssh.expect(["sudo", "@"])
    if choice == 0:
        ssh.sendline(config.HOST_SERVER_PASSWORD)


async def detach_screen_session(ssh: pxssh.pxssh) -> None:
    log.debug("Detaching screen session ...")
    ssh.sendcontrol("a")
    await asyncio.sleep(0.1)
    ssh.sendcontrol("d")


async def kill_screen(ssh: pxssh.pxssh, config: Config = CONFIG) -> None:
    log.debug("Killing screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -X -S mc-server-control quit")


async def create_screen(ssh: pxssh.pxssh, config: Config) -> None:
    log.debug("Starting screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -S mc-server-control")


async def attach_screen(ssh: pxssh.pxssh, config: Config) -> None:
    log.debug("Connecting to screen session ...")
    await send_possible_sudo_command(ssh, config, "screen -r mc-server-control")


def screen_is_installed(ssh: pxssh.pxssh) -> bool:
    ssh.sendline("command -v screen")
    ssh.prompt()
    ssh.sendline("echo $?")
    ssh.prompt()

    before_output = ssh.before
    if before_output is None:
        return False
    exit_status = int(before_output.splitlines()[-2])
    return exit_status == 0
