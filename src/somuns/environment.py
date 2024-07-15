from os import environ

from dotenv import load_dotenv
from pydantic import BaseModel


class Config(BaseModel):
    DISCORD_TOKEN: str
    HOST_SERVER_HOST: str
    HOST_SERVER_USER: str
    HOST_SERVER_PASSWORD: str
    HOST_SERVER_MAC: str
    MC_SERVER_START_CMD: str
    MC_SERVER_ADDRESS: str


load_dotenv()
CONFIG = Config(**environ)
