from somnus.logic.utils import ssh_login
from somnus.environment import Config, CONFIG
import asyncio


async def test():
    ssh = await ssh_login(CONFIG)

    print ("jo")
    ssh.sendline("screen -S name")
    await asyncio.sleep(2)
    ssh.sendline("echo hi")
    await asyncio.sleep(2)
    ssh.sendline("exit")
    #await asyncio.sleep(2)
    #ssh.sendline("echo hi")
    print(ssh.expect("@", timeout=10))
    #print(ssh.prompt(timeout=5))
    print("\n\n")
    print(str(ssh.before()))


asyncio.run(test())