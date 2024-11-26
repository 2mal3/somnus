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
- `/change_world`: Creates a drop-down menu in which the world to be switched to can be selected. The next time the server is started (with `/start`), the selected world is started.
- `/show_worlds`: Shows all available worlds. (Super users are shown all worlds, including those not currently visible, and are also shown whether the respective world is visible)
- `/ping`: Replies with "Pong"

### Commands for the Super User

- `/add_world`: Creates a new reference to an installed Minecraft installation with the new display_name, start_cmd and the Booleans sudo_start_cmd (whether the start command should be executed with sudo rights) and visible (whether the world should be visible and selectable by normal users)
- `/edit_world`: Edits and shows a reference to an installed Minecraft installation. The (old) display_name of the world reference has to be specified. Optionally, a new display_name, start_cmd, sudo_start_cmd or visble can be specified. All values updated after the possible change are then returned. This means that even without specifying the optional new parameters, only the currently saved status of the world can be displayed.
- `/delete_world`: Deletes a reference to an installed Minecraft installation after renewed approval.
- `/stop_without_shutdown`: Stops the Minecraft server, but doesn't shut it off

## Setup

1. [install Rye](https://rye.astral.sh/guide/installation/)
2. install Python dependencies with `rye sync`
3. start bot with `python3 -m somnus.__main__` or `rye run dev`!

## License

[GPL-3.0](/LICENSE.txt)
