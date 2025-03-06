from typing import AsyncGenerator

from pexpect import pxssh

from somnus.config import Config
from somnus.logger import log
from somnus.actions.ssh import detach_screen_session, kill_screen, attach_screen


class MCServerStopError(Exception):
    pass


async def stop_mc_server(ssh: pxssh.pxssh, config: Config) -> AsyncGenerator:
    """
    Raises:
        MCServerStopError: If MC server could not be stopped.
    """

    await attach_screen(ssh, config)
    yield

    try:
        async for _ in _try_stop_mc_server(ssh, config):
            yield
    except Exception as e:
        raise MCServerStopError(f"Could not stop MC server | {e}")
    finally:
        log.debug("Exiting screen session ...")
        await detach_screen_session(ssh)
        await kill_screen(ssh, config)


async def _try_stop_mc_server(ssh: pxssh.pxssh, config: Config) -> AsyncGenerator:
    server_shutdown_maximum_time = 600

    log.debug("Sending stop command ...")
    ssh.sendline("stop")

    messages = ["overworld", "nether", "end", "All"]
    for i, message in enumerate(messages):
        found_element_index = ssh.expect(["All", message], timeout=server_shutdown_maximum_time)
        log.debug(f"Stage '{message}' completed")

        if found_element_index == 0:
            for _ in range(i, len(messages)):
                yield
            return
        yield
