from pexpect import pxssh
from somnus.config import Config
from somnus.logger import log
from somnus.actions.ssh import send_sudo_command


class HostServerStopError(Exception):
    pass


async def stop_host_server(ssh: pxssh.pxssh, config: Config) -> None:
    """
    Raises:
        HostServerStopError: If host server could not be stopped.
    """

    try:
        log.debug("Stopping host server ...")
        await send_sudo_command(ssh, config, "shutdown -h now")
    except Exception as e:
        raise HostServerStopError from e
