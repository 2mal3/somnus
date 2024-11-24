import sys
from os import environ

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, ValidationError

from somnus.logger import log


class Config(BaseModel):
    DISCORD_TOKEN: str
    HOST_SERVER_HOST: str
    HOST_SERVER_USER: str
    HOST_SERVER_SSH_PORT: int = 22
    HOST_SERVER_PASSWORD: str
    HOST_SERVER_MAC: str
    MC_SERVER_START_CMD: str
    MC_SERVER_START_CMD_SUDO: bool = False
    MC_SERVER_ADDRESS: str
    DISCORD_SUPER_USER_ID: int
    DEBUG: bool

    @field_validator("DEBUG", "MC_SERVER_START_CMD_SUDO", mode="before")
    def convert_str_to_bool(cls, value: str):   # noqa: N805
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
    CONFIG = Config(**environ)  # type: ignore
except ValidationError as errors:
    for error in errors.errors():
        log.fatal(f"Missing environment variable: {error['loc'][0]}")
    sys.exit(1)
