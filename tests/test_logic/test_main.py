import asyncio
from time import sleep

import podman
import pytest
import mcstatus
from podman.domain.containers import Container

from somnus.logic import start, stop


@pytest.fixture(scope="session", autouse=True)
def podman_setup():
    client = podman.PodmanClient()

    container: Container = client.containers.run(
        "somnus-test", detach=True, ports={"22/tcp": 25566, "25565/tcp": 25565}
    )  # type: ignore
    if not client.ping():
        raise Exception("Podman service is not running")
    container.wait(condition="running")

    yield

    container.stop()
    container.remove()

    client.close()


def test_main():
    server = mcstatus.JavaServer("127.0.0.1", 25565)

    asyncio.run(start_server())

    server.ping()

    asyncio.run(stop_server())
    with pytest.raises(Exception):
        server.ping()


async def start_server():
    async for _ in start.start_server():
        pass



async def stop_server():
    async for _ in stop.stop_server(True):
        pass
