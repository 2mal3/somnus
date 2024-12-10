# somnus

Discord bot to remotely control and manage multiple Minecraft servers.

## Features

- start and stop server via discord
- automatic server shutdown due to inactivity possible
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

#### From Source

1. [install Rye](https://rye.astral.sh/guide/installation/)
2. clone repository
3. install Python dependencies with `rye sync`
4. start bot with `python3 -m somnus.__main__` or `rye run dev`!

#### With Docker

1. install Docker
2. pull image
3. run image with the required environment variables

### Environment Variables (fill in .env with .env.example)

| Env Var                     | Type    | Required | Default | Description                                                                                                           |
| --------------------------- | ------- | -------- | ------- | --------------------------------------------------------------------------------------------------------------------- |
| DISCORD_TOKEN               | string  | yes      |         | your discord bot token                                                                                                |
| HOST_SERVER_HOST            | string  | yes      |         | ip adress of your host server on which the Minecraft server process should be started                                 |
| HOST_SERVER_USER            | string  | yes      |         | username on host server                                                                                               |
| HOST_SERVER_PASSWORD        | string  | yes      |         | password for the user on host server                                                                                  |
| HOST_SERVER_MAC             | string  | yes      |         | mac adress of host server (only necessary if Wake On Lan is activated)                                                |
| MC_SERVER_START_CMD         | string  | yes      |         | start command for minecraft server (use absolute path if possible)                                                    |
| MC_SERVER_ADDRESS           | string  | yes      |         | minecraft server adress WITH PORT                                                                                     |
| DISCORD_SUPER_USER_ID       | integer | yes      |         | discord user id's separated with “;” from discord users who should have access to superuser commands                  |
| MC_SERVER_START_CMD_SUDO    | boolean | no       | false   | f the minecraft server should start with sudo rights                                                                  |
| LANGUAGE                    | string  | no       | en      | display language for the discord bot ("en" -> english, "de" -> deutsch/german are included)                           |
| HOST_SERVER_SSH_PORT        | integer | no       | 22      | sh port of the host server                                                                                            |
| INACTIVITY_SHUTDOWN_MINUTES | integer | no       | none    | time after which the server shuts down if nobody is online. Use "" so that the server doesn't shut down automatically |
| DISCORD_STATUS_CHANNEL_ID   | integer | no       | none    | discord channel id of the channel in which the automatic inactivity server shutdown message is sent                   |
| DEBUG                       | boolean | no       | false   | debug messages are displayed and server does not shut down if set to “true”                                           |

## Contributors ✨

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/2mal3"><img src="https://avatars.githubusercontent.com/u/56305732?v=4?s=100" width="100px;" alt="2mal3"/><br /><sub><b>2mal3</b></sub></a><br /><a href="https://github.com/2mal3/somnus/commits?author=2mal3" title="Code">💻</a> <a href="https://github.com/2mal3/somnus/commits?author=2mal3" title="Documentation">📖</a> <a href="#ideas-2mal3" title="Ideas, Planning, & Feedback">🤔</a> <a href="#platform-2mal3" title="Packaging/porting to new platform">📦</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/programmer-44"><img src="https://avatars.githubusercontent.com/u/129310925?v=4?s=100" width="100px;" alt="E44"/><br /><sub><b>E44</b></sub></a><br /><a href="https://github.com/2mal3/somnus/issues?q=author%3Aprogrammer-44" title="Bug reports">🐛</a> <a href="https://github.com/2mal3/somnus/commits?author=programmer-44" title="Code">💻</a> <a href="https://github.com/2mal3/somnus/commits?author=programmer-44" title="Documentation">📖</a> <a href="#ideas-programmer-44" title="Ideas, Planning, & Feedback">🤔</a> <a href="#translation-programmer-44" title="Translation">🌍</a> <a href="#userTesting-programmer-44" title="User Testing">📓</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License

[GPL-3.0](/LICENSE.txt)
