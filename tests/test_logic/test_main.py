import asyncio

import podman
import pytest
from podman.domain.containers import Container

from somnus.logic import start, stop
from somnus.config import Config


@pytest.fixture(scope="session", autouse=True)
def podman_setup():
    client = podman.PodmanClient()

    container: Container = client.containers.run(
        "somnus-test", detach=True, ports={"22/tcp": 25566, "25565/tcp": 25565}
    )   # type: ignore
    if not client.ping():
        raise Exception("Podman service is not running")
    container.wait(condition="running")

    yield

    #container.stop()
    #container.remove()

    client.close()


def test_main():
    config = Config(
        DISCORD_TOKEN="",
        HOST_SERVER_HOST="localhost",
        HOST_SERVER_SSH_PORT=25566,
        HOST_SERVER_USER="root",
        HOST_SERVER_PASSWORD="root",
        MC_SERVER_START_CMD="./start.sh",
        MC_SERVER_ADDRESS="25565",
        DISCORD_SUPER_USER_ID="",
        DEBUG=True,
    )

    asyncio.run(start_server(config))
    asyncio.run(stop_server(config))


async def start_server(config: Config):
    async for _ in start.start_server(config):
        pass


async def stop_server(config: Config):
    async for _ in stop.stop_server(True, config):
        pass
