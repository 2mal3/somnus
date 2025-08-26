from typing import AsyncGenerator

from pexpect import pxssh

from somnus.config import Config
from somnus.logger import log
from somnus.actions.ssh import ssh_login, detach_screen_session, kill_screen, create_screen
from somnus.logic.world_selector import get_current_world


class MCServerStartError(Exception):
    pass


async def start_mc_server(config: Config) -> AsyncGenerator:
    ssh = await ssh_login(config)

    await create_screen(ssh, config)
    yield

    try:
        async for _ in _try_start_mc_server(ssh):
            yield

        # Exit peacefully
        log.debug("Detaching screen ...")
        await detach_screen_session(ssh)
        ssh.prompt()
        log.debug("Logging out ...")
        ssh.logout()
        yield

    # Exit in error, kill screen
    except Exception as exception1:
        try:
            log.debug("Problem occurred, try to gracefully exit ...", exc_info=exception1)
            await detach_screen_session(ssh)
            ssh.prompt()
            await kill_screen(ssh, config)
            ssh.prompt()
            ssh.close()
        except Exception as exception2:
            log.error("Could not gracefully exit", exc_info=exception2)
            ssh.close()
            raise MCServerStartError("Problem occured, try to gracefully exit failed. Problem01 (initial problem):\n" + str(exception1) + "\n\nProblem02 (fail to exit gracefully): " + str(exception2)) from exception2
        else:
            raise MCServerStartError("Problem occurred (gracefully exit successfully done):\n" + str(exception1)) from exception1


async def _try_start_mc_server(ssh: pxssh.pxssh) -> AsyncGenerator:
    log_search_timeout_seconds = 150

    log.debug("Send MC server start command ...")
    ssh.sendline((await get_current_world()).start_cmd)
    yield

    log.debug("Waiting for MC server to start ...")
    messages = [
        ["Starting", "running"],
        ["Loading libraries", "Loading"],
        ["Environment", "Preparing"],
        ["Preparing level"],
        [],
    ]
    for i, message in enumerate(messages):
        try:
            found_element_index = ssh.expect(["Done"] + message, timeout=log_search_timeout_seconds)
            log.debug(f"Stage '{message}' completed")

            if found_element_index == 0:  # if finished earlier, animate the progress bar to its end
                for _ in range(i, len(messages)):
                    yield
                return
            yield
        except TimeoutError as e:
            raise TimeoutError(f"Minecraft-Server could not be startet. Timeout in starting keyword expecting {e}")
