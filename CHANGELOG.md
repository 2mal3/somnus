## v3.0.0

### Removed

- MC_SERVER_START_CMD_SUDO config
- DEBUG_LOGGING config

### Changed

- always log debug logs
- improved responsivness
- more stable inactivity shutdown
- stabler discord bot status

### Fixed

- didn't wait for some shell commands to finish before sending additional commands
- busy state sometimes set incorrectly
- update_players_online_status incorrectly started
- broken ssh timeout detection
- ssh connection not always properly closed
- changing worlds sometimes wouldn't work
