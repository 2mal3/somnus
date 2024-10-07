import asyncio

from pexpect import pxssh

from somnus.environment import Config, CONFIG
from somnus.logger import log
from somnus.logic.utils import (
    ServerState,
    get_server_state,
    ssh_login,
    UserInputError,
    send_possible_sudo_command,
    send_sudo_command,
    Test
)


async def stop_server(config: Config = CONFIG):
    host_server_state, mc_server_state = await get_server_state(config)
    log.debug(f"Host server state: {host_server_state.value} | MC server state: {mc_server_state.value}")

    if ServerState.RUNNING not in (host_server_state, mc_server_state):
        raise UserInputError("Server already stopped")
    yield

    ssh = await ssh_login(config)
    yield

    # Stop MC server
    if mc_server_state == ServerState.RUNNING:
        try:
            async for _ in _stop_mc_server(ssh, config):
                yield
        except Exception as e:
            raise RuntimeError(f"Could not stop MC server | {e}")
    yield

    # Exit screen session
    log.debug("Exiting screen session ...")

    # Alt, nicht korrekt funktionierend:
    #ssh.sendline("exit")
    #ssh.prompt() #<- does not work

    # Neu, genau so schlecht funktionierend, Grund: siehe "_stop_mc_server"
    ssh.sendline("export PS1='\\u@\\h:\\w\\$ '")  # Temporär den PS1-String setzen
    ssh.sendline("exit")
    ssh.prompt()
    log.debug("DEBUG-RÜCKGABE: "+str(ssh.before))
    #ssh.expect("@", timeout=120)

    
    yield

    # Stop host server
    if host_server_state == ServerState.RUNNING and config.DEBUG == "0":
        try:
            await send_sudo_command(ssh, config, "shutdown -h now")
            yield
        except Exception as e:
            raise RuntimeError(f"Could not stop host server | {e}")

    ssh.logout()


async def _stop_mc_server(ssh: pxssh.pxssh, config: Config):
    log.debug("Connecting to screen session ...")

    await send_possible_sudo_command(ssh, config, "screen -r mc-server-control")
    yield

    log.debug("Sending stop command ...")
    
    # TODO: Da ssh.prompt immer das Timeout ausreizt (gibt auch False statt True zurück), habe ich etwas rumgetestet, aber nix funktioniert. Problem muss noch gefixt werden!

    ssh.sendline("export PS1='\\u@\\h:\\w\\$ '")  # Temporär den PS1-String setzen
    ssh.sendline('stop')
    ssh.prompt(timeout=120)
    log.debug("DEBUG-RÜCKGABE: "+str(ssh.before))

    # Es folgt: Alt oder nur zum Testen

    #messages = ["overworld", "the_end", "nether"]
    #for message in messages:
    #    ssh.expect(message, timeout=120)
    #    yield
    
    # stop_messages = ["Stopping server", "Saving players", "Saving worlds", "Stopping server"]
    # for message in stop_messages:
    #    ssh.expect(message, timeout=120)



    #ssh.prompt() <- does not work
    #ssh.expect("@", timeout=120)

    

       
    


async def main():
    async for _ in stop_server():
        pass


if __name__ == "__main__":
    asyncio.run(main())
