import os
import json

import aiofiles
from pydantic import BaseModel, field_validator

from somnus.environment import CONFIG, Config
from somnus.logger import log

WORLD_SELECTOR_CONFIG_FILE_PATH = "world_selector_data.json"


class UserInputError(Exception):
    pass


class WorldSelectorWorld(BaseModel):
    display_name: str
    start_cmd: str
    start_cmd_sudo: str | bool
    visible: bool

    @field_validator("start_cmd_sudo", mode="before")
    def convert_str_to_bool(cls, value: str) -> bool:  # noqa: N805
        return value in ("", "true", "True", True, "1")


class WorldSelectorConfig(BaseModel):
    new_selected_world: str
    current_world: str
    worlds: list[WorldSelectorWorld]


async def get_current_world() -> WorldSelectorWorld:
    world_selector_config = await get_world_selector_config()

    current_world = await get_world_by_name(world_selector_config.current_world, world_selector_config)
    if not current_world:
        log.error(f"Current world (display_name='{world_selector_config.current_world}') not found")

    return current_world


async def create_new_world(display_name: str, start_cmd: str, start_cmd_sudo: bool, visible: bool):
    new_world = WorldSelectorWorld(
        display_name=display_name, start_cmd=start_cmd, start_cmd_sudo=start_cmd_sudo, visible=visible
    )

    world_selector_config = await get_world_selector_config()

    if await _world_exists(display_name, world_selector_config):
        text = f"New World {display_name} couldn't be created because the display name is already in use"
        log.debug(text)
        raise UserInputError(text)

    world_selector_config.worlds.append(new_world)
    await _save_world_selector_config(world_selector_config)


async def _world_exists(display_name: str, world_selector_config: WorldSelectorConfig) -> bool:
    try:
        await get_world_by_name(display_name, world_selector_config)
        return True
    except UserInputError:
        return False


async def change_world():
    world_selector_config = await get_world_selector_config()

    if world_selector_config.current_world != world_selector_config.new_selected_world:
        for world in world_selector_config.worlds:
            if world.display_name == world_selector_config.new_selected_world and world.visible:
                world_selector_config.current_world = world_selector_config.new_selected_world
                await _save_world_selector_config(world_selector_config)
                return


async def select_new_world(new_world_name):
    world_selector_config = await get_world_selector_config()
    if world_selector_config.current_world == new_world_name:
        world_selector_config.new_selected_world = ""
        await _save_world_selector_config(world_selector_config)
        return True
    else:
        world_selector_config.new_selected_world = new_world_name
        await _save_world_selector_config(world_selector_config)
        return False


async def edit_new_world(
    editing_world_name, new_display_name, start_cmd, start_cmd_sudo, visible
) -> WorldSelectorWorld:
    world_selector_config = await get_world_selector_config()

    for i, world in enumerate(world_selector_config.worlds):
        if world.display_name == editing_world_name:
            if new_display_name not in ("", None):
                world_selector_config.worlds[i].display_name = new_display_name
                if world_selector_config.current_world == editing_world_name:
                    world_selector_config.current_world = new_display_name
            if start_cmd not in ("", None):
                world_selector_config.worlds[i].start_cmd = start_cmd
            if start_cmd_sudo not in ("", None):
                world_selector_config.worlds[i].start_cmd_sudo = start_cmd_sudo
            if visible not in ("", None):
                world_selector_config.worlds[i].visible = visible

            await _save_world_selector_config(world_selector_config)
            return world_selector_config.worlds[i]


async def try_delete_world(display_name: str):
    try:
        await _delete_world(display_name)
        return True
    except Exception:
        return False


async def _delete_world(display_name: str):
    world_selector_config = await get_world_selector_config()

    for i, world in enumerate(world_selector_config.worlds):
        if world.display_name == display_name:
            del world_selector_config.worlds[i]
            log.debug(f"world '{display_name}' deleted succesfully")
            break

    await _save_world_selector_config(world_selector_config)


async def get_world_by_name(display_name: str, world_selector_config: WorldSelectorConfig) -> WorldSelectorWorld:
    found_worlds = [world for world in world_selector_config.worlds if world.display_name == display_name]
    if len(found_worlds) == 0:
        raise UserInputError(f"World '{display_name}' not found")
    return found_worlds[0]


async def get_world_selector_config() -> WorldSelectorConfig:
    try:
        world_selector_config = await _get_world_selector_config_from_path(WORLD_SELECTOR_CONFIG_FILE_PATH)
        return world_selector_config
    except Exception:
        world_selector_config = _get_default_world_selector_config()
        await _save_world_selector_config(world_selector_config)
        return world_selector_config


async def _get_world_selector_config_from_path(path: str) -> WorldSelectorConfig:
    if not os.path.exists(path):
        raise FileNotFoundError

    async with aiofiles.open(path, encoding="utf-8") as file:
        content = await file.read()
        data = json.loads(content)
        return WorldSelectorConfig(**data)


def _get_default_world_selector_config(config: Config = CONFIG) -> WorldSelectorConfig:
    data = WorldSelectorConfig(
        current_world="Minecraft",
        worlds=[
            WorldSelectorWorld(
                new_selected_world="",
                display_name="Minecraft",
                start_cmd=config.MC_SERVER_START_CMD,
                start_cmd_sudo=config.MC_SERVER_START_CMD_SUDO,
                visible=True,
            )
        ],
    )
    return data


async def _save_world_selector_config(data: WorldSelectorConfig):
    async with aiofiles.open(WORLD_SELECTOR_CONFIG_FILE_PATH, "w", encoding="utf-8") as file:
        await file.write(json.dumps(data.model_dump(), indent=4))
