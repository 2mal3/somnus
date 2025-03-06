import asyncio
from typing import AsyncGenerator

from somnus.actions.start_host import start_host_server
from somnus.actions.start_mc import start_mc_server
from somnus.config import Config, CONFIG
from somnus.logger import log
from somnus.actions.stats import get_server_state
from somnus.language_handler import LH
from somnus.logic.errors import UserInputError


async def start_server(config: Config = CONFIG) -> AsyncGenerator[bool | None, None]:
    """
    Raises:
        UserInputError: If the user input is invalid.
        MCServerStartError: If MC server could not be started.
        HostServerStartError: If host server could not be started.
    """

    server_state = await get_server_state(config)
    log.info(
        f"Host server running: {server_state.host_server_running} | MC server running: {server_state.mc_server_running}"
    )

    if server_state.host_server_running and server_state.mc_server_running:
        raise UserInputError(LH("commands.start.error.already_running"))
    yield

    # Start host server
    if not server_state.host_server_running:
        log.debug("Starting host server ...")

        try:
            async for _ in start_host_server(config):
                yield

        except Exception:
            log.warning("Could not connect to host server. Send WOL packages again and retry.")
            yield True
            try:
                async for _ in start_host_server(config):
                    yield

            except Exception as e:
                raise RuntimeError(f"Could not start host server | {e}")

    else:
        for _ in range(9):
            yield
    yield

    # Start MC server
    async for _ in start_mc_server(config):
        yield


async def main() -> None:
    async for _ in start_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
