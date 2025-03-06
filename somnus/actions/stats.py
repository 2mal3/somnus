from mcstatus import JavaServer
from mcstatus.status_response import JavaStatusResponse
from pexpect import pxssh
from ping3 import ping
from pydantic import BaseModel

from somnus.config import Config
from somnus.logger import log


class ServerState(BaseModel):
    host_server_running: bool
    mc_server_running: bool


async def get_mcstatus(config: Config) -> JavaStatusResponse | None:
    try:
        server = await JavaServer.async_lookup(config.MC_SERVER_ADDRESS)
        return server.status()
    except Exception as e:
        if (not isinstance(e, OSError)) and (not isinstance(e, TimeoutError)):
            log.error(f"Couldn't get mcstatus: {e}")
        return None


async def get_server_state(config: Config) -> ServerState:
    host_server_running = await _is_host_server_running(config)
    if not host_server_running:
        return ServerState(host_server_running=False, mc_server_running=False)

    mc_server_running = await _is_mc_server_running(config)

    return ServerState(host_server_running=host_server_running, mc_server_running=mc_server_running)


async def _is_mc_server_running(config: Config) -> bool:
    return bool(await get_mcstatus(config))


async def _is_host_server_running(config: Config) -> bool:
    if config.DEBUG and config.HOST_SERVER_HOST in ["localhost", "127.0.0.1"]:
        return True

    if config.HOST_SERVER_HOST not in ["localhost", "127.0.0.1"] and not ping(config.HOST_SERVER_HOST):
        return False

    try:
        ssh = pxssh.pxssh()
        ssh.login(
            config.HOST_SERVER_HOST,
            config.HOST_SERVER_USER,
            config.HOST_SERVER_PASSWORD,
            port=config.HOST_SERVER_SSH_PORT,
            login_timeout=5,
        )
        ssh.close()
    except Exception:
        return False

    return True
