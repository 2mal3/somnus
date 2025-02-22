import asyncio

import podman
from podman.domain.containers import Container

from somnus.logic import start
from somnus.environment import Config


def test_main():
    with podman.PodmanClient() as client:
        if not client.ping():
            raise Exception("Podman service is not running")

        container: Container = client.containers.run(
            "somnus-test", detach=True, ports={"22/tcp": 25566, "25565/tcp": 25565}
        )
        container.wait(condition="running")

        asyncio.run(run_server())

        container.stop()
        container.remove()


async def run_server():
    async for _ in start.start_server(
        Config(
            DISCORD_TOKEN="",
            HOST_SERVER_HOST="localhost",
            HOST_SERVER_SSH_PORT=25566,
            HOST_SERVER_USER="root",
            HOST_SERVER_PASSWORD="root",
            MC_SERVER_START_CMD="./start.sh",
            MC_SERVER_ADDRESS="25565",
            DISCORD_SUPER_USER_ID="",
            DEBUG="true",
        )
    ):
        pass
