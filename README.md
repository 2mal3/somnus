# somnus

![Python](https://img.shields.io/badge/python-3670A0?style=flat&logo=python&logoColor=ffdd54)
[![CodeQL](https://github.com/2mal3/somnus/actions/workflows/codeql.yml/badge.svg)](https://github.com/2mal3/somnus/actions/workflows/codeql.yml)
![GitHub last commit](https://img.shields.io/github/last-commit/2mal3/somnus)

A Discord bot to remotely control and manage multiple Minecraft servers.

## 📋 Features

- ▶️ easily start and stop servers via Discord Bot commands
- 🔄 switch between servers with different configurations on the fly
- 📊 optional automatic server shutdown when server is empty to save resources
- 🖥️ well-thought-out user interface
- 🚨 advanced error handling
- 🏡 designed for easy self-hosting

## 📥 Setup

### 1. Get a Discord Bot

1. create an Discord Bot and note down its API key (for example using [this guide](https://www.xda-developers.com/how-to-create-discord-bot/))

### 2. Make Host Server Ready (the server that should run the Minecraft server)

1. get at least one server running Linux

2. make sure that the [Special Host System Requirements](#-special-host-system-requirements) are installed and enabled

3. if the control programm runs on another server, get the IP-Address of the server

4. if the control programm runs on another server and you want to be able to shutdown the whole host server, get the MAC-Address of the server

5. setup a Minecraft server, with an option to start it via terminal commands

### 3. Install Control Program (also possible on separate Server)

#### With Docker

1. install Docker
2. pull image `ghcr.io/2mal3/somnus:latest`
3. run the image with the required [Environment Variables](#environment-variables) you got in step 1 and 2

#### From Source

1. [install Rye](https://rye.astral.sh/guide/installation/)
2. clone the somnus repository onto your server
3. install Python dependencies with `rye sync`
4. fill the `.env` file with the required [Environment Variables](#environment-variables) you got in step 1 and 2 (you can use the `.env.example` file for reference)
5. start Discord bot with `rye run prod`

## Reference

### ▶️ Commands

| Command                  | Description                                                                                                                                                                                                                                                                                                                                                                                                                      | Requires Super User |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| `/start`                 | Starts the Minecraft server (and if necessary the server via Wake On Lan before)                                                                                                                                                                                                                                                                                                                                                 | no                  |
| `/stop`                  | Stops the Minecraft server and then shuts down the server                                                                                                                                                                                                                                                                                                                                                                        | no                  |
| `/change_world`          | Creates a drop-down menu in which the world to be switched to can be selected. The next time the server is started (with `/start` or `/restart`), the selected world is started.                                                                                                                                                                                                                                                 | no                  |
| `/restart`               | Restarts the Minecraft server process, not the hole server.                                                                                                                                                                                                                                                                                                                                                                      | no                  |
| `/show_worlds`           | Shows all available worlds. (Super users are shown all worlds, including those not currently visible, and are also shown whether the respective world is visible)                                                                                                                                                                                                                                                                | no                  |
| `/ping`                  | Replies with "Pong"                                                                                                                                                                                                                                                                                                                                                                                                              | no                  |
| `/reset_busy`            | If the message that the bot is busy is sent by mistake, this command can reset the incorrect busy state.                                                                                                                                                                                                                                                                                                                         | no                  |
| `/get_players`           | Shows all players who are online on the server.                                                                                                                                                                                                                                                                                                                                                                                  | no                  |
| `/help`                  | Displays all relevant commands from this bot with an explanation.                                                                                                                                                                                                                                                                                                                                                                | no                  |
| `/add_world`             | Creates a new reference to an installed Minecraft installation with the new display_name, start_cmd and the Booleans sudo_start_cmd (whether the start command should be executed with sudo rights) and visible (whether the world should be visible and selectable by normal users)                                                                                                                                             | yes                 |
| `/edit_world`            | Edits and shows a reference to an installed Minecraft installation. The (old) display_name of the world reference has to be specified. Optionally, a new display_name, start_cmd, sudo_start_cmd or visble can be specified. All values updated after the possible change are then returned. This means that even without specifying the optional new parameters, only the currently saved status of the world can be displayed. | yes                 |
| `/delete_world`          | Deletes a reference to an installed Minecraft installation after renewed approval.                                                                                                                                                                                                                                                                                                                                               | yes                 |
| `/stop_without_shutdown` | stops the Minecraft server, but doesn't shut it off                                                                                                                                                                                                                                                                                                                                                                              | yes                 |

### ⚙️ Environment Variables

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
| GET_PLAYERS_COMMAND_ENABLED | boolean | no       | true    | if the "/get_players" command is enabled (returns all player names of players who are online)                         |
| MC_SERVER_START_CMD_SUDO    | boolean | no       | false   | if the minecraft server should start with sudo rights                                                                 |
| LANGUAGE                    | string  | no       | en      | display language for the discord bot ("en" -> english, "de" -> deutsch/german are included)                           |
| HOST_SERVER_SSH_PORT        | integer | no       | 22      | ssh port of the host server                                                                                           |
| INACTIVITY_SHUTDOWN_MINUTES | integer | no       | none    | time after which the server shuts down if nobody is online. Use "" so that the server doesn't shut down automatically |
| DISCORD_STATUS_CHANNEL_ID   | integer | no       | none    | discord channel id of the channel in which the automatic inactivity server shutdown message is sent                   |
| DEBUG                       | boolean | no       | false   | server does not shut down and faster timeouts if set to “true”                                                        |
| DEBUG_LOGGING               | boolean | no       | false   | debug messages are displayed                                                                                          |

### 🧩 Special Host System Requirements

- `bash` as default shell

- `ssh`

- `screen`

## ✨ Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/2mal3"><img src="https://avatars.githubusercontent.com/u/56305732?v=4?s=100" width="100px;" alt="2mal3"/><br /><sub><b>2mal3</b></sub></a><br /><a href="https://github.com/2mal3/somnus/commits?author=2mal3" title="Code">💻</a> <a href="https://github.com/2mal3/somnus/commits?author=2mal3" title="Documentation">📖</a> <a href="#ideas-2mal3" title="Ideas, Planning, & Feedback">🤔</a> <a href="#platform-2mal3" title="Packaging/porting to new platform">📦</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/programmer-44"><img src="https://avatars.githubusercontent.com/u/129310925?v=4?s=100" width="100px;" alt="E44"/><br /><sub><b>E44</b></sub></a><br /><a href="https://github.com/2mal3/somnus/issues?q=author%3Aprogrammer-44" title="Bug reports">🐛</a> <a href="https://github.com/2mal3/somnus/commits?author=programmer-44" title="Code">💻</a> <a href="https://github.com/2mal3/somnus/commits?author=programmer-44" title="Documentation">📖</a> <a href="#ideas-programmer-44" title="Ideas, Planning, & Feedback">🤔</a> <a href="#translation-programmer-44" title="Translation">🌍</a> <a href="#userTesting-programmer-44" title="User Testing">📓</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/MCsharerGIT"><img src="https://avatars.githubusercontent.com/u/98043315?v=4?s=100" width="100px;" alt="MCsharerGIT"/><br /><sub><b>MCsharerGIT</b></sub></a><br /><a href="https://github.com/2mal3/somnus/issues?q=author%3AMCsharerGIT" title="Bug reports">🐛</a> <a href="#ideas-MCsharerGIT" title="Ideas, Planning, & Feedback">🤔</a> <a href="#infra-MCsharerGIT" title="Infrastructure (Hosting, Build-Tools, etc)">🚇</a> <a href="#userTesting-MCsharerGIT" title="User Testing">📓</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

---

License - [LGPL-3.0](/LICENSE.txt)
