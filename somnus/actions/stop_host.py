from pexpect import pxssh
from somnus.config import Config
from somnus.actions.ssh import shutdown_host


class HostServerStopError(Exception):
    pass


async def stop_host_server(ssh: pxssh.pxssh, config: Config) -> None:
    """
    Raises:
        HostServerStopError: If host server could not be stopped.
    """

    try:
        await shutdown_host(ssh, config)
    except Exception as e:
        raise HostServerStopError from e
