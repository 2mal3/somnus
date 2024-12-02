# somnus

Discord bot to remotely control and manage multiple Minecraft servers.

## Features

- start and stop server via discord
- switch between different servers on the fly
- well-thought-out user interface
- advanced error handling
- easy to self-host

## Commands

### Commands for All Users

- `/start`: Starts the Minecraft server (and if necessary the server via Wake On Lan before)
- `/stop`: Stops the Minecraft server and then shuts down the server (unless debug=“true” is set in the .env)
- `/change_world`: Creates a drop-down menu in which the world to be switched to can be selected. The next time the server is started (with `/start` or `/restart`), the selected world is started.
- `/restart`: Restarts the Minecraft server process, not the hole server.
- `/show_worlds`: Shows all available worlds. (Super users are shown all worlds, including those not currently visible, and are also shown whether the respective world is visible)
- `/ping`: Replies with "Pong"
- `/reset_busy`: If the message that the bot is busy is sent by mistake, this command can reset the incorrect busy state.
- `/help`: Displays all relevant commands from this bot with an explanation.

### Commands for the Super User

- `/add_world`: Creates a new reference to an installed Minecraft installation with the new display_name, start_cmd and the Booleans sudo_start_cmd (whether the start command should be executed with sudo rights) and visible (whether the world should be visible and selectable by normal users)
- `/edit_world`: Edits and shows a reference to an installed Minecraft installation. The (old) display_name of the world reference has to be specified. Optionally, a new display_name, start_cmd, sudo_start_cmd or visble can be specified. All values updated after the possible change are then returned. This means that even without specifying the optional new parameters, only the currently saved status of the world can be displayed.
- `/delete_world`: Deletes a reference to an installed Minecraft installation after renewed approval.
- `/stop_without_shutdown`: Stops the Minecraft server, but doesn't shut it off

## Setup
### Installation
1. [install Rye](https://rye.astral.sh/guide/installation/)
2. install Python dependencies with `rye sync`
3. start bot with `python3 -m somnus.__main__` or `rye run dev`!

### Fill in .env (with .env.example)
- DISCORD_TOKEN: your discord bot token
- HOST_SERVER_HOST: ip adress of your host server on which the Minecraft server process should be started
- HOST_SERVER_SSH_PORT: ssh port of the host server (standard = "22")
- HOST_SERVER_USER: username on host server
- HOST_SERVER_PASSWORD: password for the user on host server
- HOST_SERVER_MAC: mac adress of host server (only necessary if Wake On Lan is activated)
- MC_SERVER_START_CMD: start command for minecraft server (use absolute path if possible)
- MC_SERVER_START_CMD_SUDO: bool ("true"/"false") if the minecraft server should start with sudo rights
- MC_SERVER_ADDRESS: minecraft server adress WITH PORT
- LANGUAGE: display language for the discord bot ("en" -> english, "de" -> deutsch/german are included)
- DISCORD_SUPER_USER_ID: discord user id's separated with “;” from discord users who should have access to superuser commands
- DEBUG; bool ("true"/"false"): standard = "false"; debug messages are displayed and server does not shut down if set to “true”

## License

[GPL-3.0](/LICENSE.txt)
