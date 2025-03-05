import sys
from os import environ

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, ValidationError


class Config(BaseModel):
    DISCORD_TOKEN: str
    HOST_SERVER_HOST: str
    HOST_SERVER_USER: str
    HOST_SERVER_SSH_PORT: int = 22
    HOST_SERVER_PASSWORD: str
    HOST_SERVER_MAC: str = ""
    MC_SERVER_START_CMD: str
    MC_SERVER_START_CMD_SUDO: bool = False
    MC_SERVER_ADDRESS: str
    GET_PLAYERS_COMMAND_ENABLED: bool = True
    INACTIVITY_SHUTDOWN_MINUTES: int = 0
    DISCORD_STATUS_CHANNEL_ID: int | None = None
    LANGUAGE: str = "en"
    DISCORD_SUPER_USER_ID: str = ""
    DEBUG: bool = False
    DEBUG_LOGGING: bool = False

    @field_validator("DEBUG", "DEBUG_LOGGING", "MC_SERVER_START_CMD_SUDO", mode="before")
    def convert_str_to_bool(cls, value: str | bool) -> bool:  # noqa: N805
        if isinstance(value, bool):
            return value

        return text_is_true(value)


def text_is_true(text: str) -> bool:
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False

    if text.isnumeric():
        return bool(int(text))

    raise ValueError(f"Invalid value: {text}")


load_dotenv()

try:
    environ = {key: value for key, value in environ.items() if value.strip() != ""}
    CONFIG = Config(**environ)  # type: ignore
except ValidationError as errors:
    for error in errors.errors():
        print(f"FATAL: Missing environment variable: {error['loc'][0]}")  # noqa: T201
    sys.exit(1)
