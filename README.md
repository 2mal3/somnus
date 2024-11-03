# somnus

Start Bot with `python3 -m somnus.__main__`!


## Commands
### Commands for all users
`/start`: Starts the Minecraft server (and if necessary the server via Wake On Lan before)

`/stop`: Stops the Minecraft server and then shuts down the server (unless debug=“1” is set in the .env)

`/change_world`: Creates a drop-down menu in which the world to be switched to can be selected. The next time the server is started (with `/start`), the selected world is started.

`/show_worlds`: Shows all available worlds. (Super users are shown all worlds, including those not currently visible, and are also shown whether the respective world is visible)

`/ping`: Replies with "Pong"

### Commands for the super user
`/add_world`: Creates a new reference to an installed Minecraft installation with the new display_name, start_cmd and the Booleans sudo_start_cmd (whether the start command should be executed with sudo rights) and visible (whether the world should be visible and selectable by normal users)

`/edit_world`: Edits and shows a reference to an installed Minecraft installation. The (old) display_name of the world reference has to be specified. Optionally, a new display_name, start_cmd, sudo_start_cmd or visble can be specified. All values updated after the possible change are then returned. This means that even without specifying the optional new parameters, only the currently saved status of the world can be displayed.

`/delete_world`: Deletes a reference to an installed Minecraft installation after renewed approval.
