import asyncio
from typing import AsyncGenerator

from wakeonlan import send_magic_packet

from somnus.config import Config
from somnus.logger import log
from somnus.actions.stats import get_server_state


class HostServerStartError(Exception):
    pass


async def start_host_server(config: Config) -> AsyncGenerator:
    """
    Raises:
        HostServerStartError: If host server could not be started.
    """

    ping_count = 2 if config.DEBUG else 15
    ping_timeout_seconds = 5 if config.DEBUG else 300

    await _send_wol_packet(config)
    yield

    for i in range(ping_count):
        await asyncio.sleep(ping_timeout_seconds // ping_count)

        if (await get_server_state(config)).host_server_running:
            for j in range(i, ping_count):
                if j % 2:
                    yield
            return

        if i % 2:
            yield

        log.warning("Could not connect to host server, trying again...")

    raise HostServerStartError


async def _send_wol_packet(config: Config) -> None:
    wol_send_delay_seconds = 5
    wol_packed_amount = 10

    if config.HOST_SERVER_MAC != "":
        for _ in range(wol_packed_amount):
            send_magic_packet(config.HOST_SERVER_MAC)
            await asyncio.sleep(wol_send_delay_seconds)
