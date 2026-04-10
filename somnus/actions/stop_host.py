from pexpect import pxssh

from somnus.actions.ssh import send_sudo_command
from somnus.config import Config
from somnus.logger import log


class HostServerStopError(Exception):
    pass


async def stop_host_server(ssh: pxssh.pxssh, config: Config) -> None:
    """
    Raises:
        HostServerStopError: If host server could not be stopped.
    """

    try:
        log.debug("Stopping host server ...")
        # Run the command in background using sudos "-b" and the nohup tool
        # so that terminating the ssh session does not stop the shutdown command
        # also throw away the output to prevent nohup from creating any files
        await send_sudo_command(ssh, config, "-b nohup shutdown -h now > /dev/null")
    except Exception as e:
        raise HostServerStopError from e
