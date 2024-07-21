import asyncio

from pexpect import pxssh

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.logic.utils import ServerState, get_server_state, ssh_login, UserInputError, send_possible_sudo_command, exit_screen


async def stop_server(config: Config = CONFIG):
    host_server_state, mc_server_state = await get_server_state(config)
    log.debug(f"Host server state: {host_server_state.value} | MC server state: {mc_server_state.value}")

    if ServerState.RUNNING not in (host_server_state, mc_server_state):
        raise UserInputError("Server already stopped")
    yield

    ssh = await ssh_login(config)
    yield

    try:
        if mc_server_state == ServerState.RUNNING:
            async for _ in _stop_mc_server(ssh, config):
                yield
        yield
    except Exception as e:
        await exit_screen(ssh)
        await send_possible_sudo_command(ssh, config, "screen -X -S mc-server-control quit")
        ssh.prompt()
        ssh.logout()
        raise RuntimeError(f"Could not stop MC server | {e}")

    log.debug("Exiting screen session ...")
    ssh.sendline("exit")
    ssh.prompt()
    ssh.logout()


async def _stop_mc_server(ssh: pxssh.pxssh, config: Config):
    log.debug("Connecting to screen session ...")

    await send_possible_sudo_command(ssh, config, "screen -r mc-server-control")
    yield

    log.debug("Sending stop command ...")
    ssh.sendline("stop")
    messages = ["overworld", "the_end", "nether"]
    for message in messages:
        ssh.expect(message, timeout=120)
        yield
    ssh.prompt(timeout=120)


async def main():
    async for _ in stop_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
