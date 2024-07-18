import asyncio

from pexpect import pxssh

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.logic.utils import ServerState, get_server_state, ssh_login, UserInputError


async def stop_server(config: Config = CONFIG):
    host_server_state, mc_server_state = await get_server_state(config)
    log.debug(f"Host server state: {host_server_state.value} | MC server state: {mc_server_state.value}")

    if ServerState.RUNNING not in (host_server_state, mc_server_state):
        raise UserInputError("Server already stopped")

    ssh = await ssh_login(config)
    yield

    try:
        if mc_server_state == ServerState.RUNNING:
            async for _ in _stop_mc_server(ssh, config):
                yield
        yield
    except Exception as e:
        raise RuntimeError(f"Could not stop MC server | {e}")

    ssh.logout()


async def _stop_mc_server(ssh: pxssh.pxssh, config: Config):
    log.debug("Connecting to screen session ...")
    if config.MC_SERVER_START_CMD_SUDO != "true":
        ssh.sendline("screen -r mc-server-control")
    else:
        log.debug("Using sudo screen session ...")
        ssh.sendline("sudo screen -r mc-server-control")
        ssh.expect("sudo")
        ssh.sendline(config.HOST_SERVER_PASSWORD)
    yield

    log.debug("Sending stop command ...")
    ssh.sendline("stop")
    ssh.prompt()
    yield

    log.debug("Exiting screen session ...")
    ssh.sendline("exit")
    ssh.prompt()


async def main():
    async for _ in stop_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
