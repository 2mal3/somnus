from pexpect import pxssh

from somuns.environment import Config, CONFIG
from somuns.logger import log
from somuns.logic.utils import ServerState, get_server_state, ssh_login, UserInputError


async def stop_server(config: Config = CONFIG):
    host_server_state, mc_server_state = await get_server_state(config)
    log.debug(f"Host server state: {host_server_state.value} | MC server state: {mc_server_state.value}")

    if ServerState.RUNNING not in (host_server_state, mc_server_state):
        raise UserInputError("Server already stopped")

    ssh = await ssh_login(config)
    yield

    try:
        if mc_server_state == ServerState.RUNNING:
            async for _ in _stop_mc_server(ssh):
                yield
        yield
    except Exception as e:
        raise RuntimeError(f"Could not stop MC server | {e}")

    ssh.logout()


async def _stop_mc_server(ssh: pxssh.pxssh):
    log.debug("Connecting to screen session ...")
    ssh.sendline("screen -r mc-server-control")
    ssh.expect(">")
    yield

    log.debug("Sending stop command ...")
    ssh.sendline("stop")
    ssh.prompt()
    yield

    log.debug("Exiting screen session ...")
    ssh.sendline("exit")
    ssh.prompt()
