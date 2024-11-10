# TODO:
#
# create_world(display_name: str, start_command: str, sudo_start_command: bool, visible: bool) Super-User-only
# change_world() -> display_name per Drop-Down auswählen
# show_worlds()
# edit_world(id:int, [display_name]: str, [start_command]: str, [sudo_start_command]: bool, [visible]: bool) -> wenn man felder leer lässt (oder nur Leerzeichen) wird nix geändert, sonst wirds überschrieben
# delete_world() -> display_name per Drop-Down auswählen
#

from somnus.environment import CONFIG, Config
import os
import json
from somnus.logger import log
import aiofiles

json_path = "world_selecter_data.json"


async def check_world_selecter_json():
    if os.path.exists(json_path):
        try:
            data = await get_data()
            if len(data.get("worlds")) > 0:
                log.debug(f"'{json_path}' imported correctly")
                return
        except:
            pass

    log.warning(f"'{json_path}' was not found")
    await _init_world_selecter_json()


async def _init_world_selecter_json(config: Config = CONFIG):
    default_data = {
        "current_world": "Minecraft",
        "worlds": [
            {
                "display_name": "Minecraft",
                "start_cmd": config.MC_SERVER_START_CMD,
                "sudo_start_cmd": config.MC_SERVER_START_CMD_SUDO,
                "visible": True,
            }
        ],
    }

    try:
        await _save_data(default_data)
        log.debug(f"'{json_path}' was created")
    except Exception as e:
        log.error(f"Error creating JSON file: {e}")


async def get_current_world():
    data = await get_data()

    current_world_name = data["current_world"]
    current_world = await search_world(current_world_name, data)
    if not current_world:
        log.error(f"Current world (display_name='{current_world_name}') not found")

    return current_world


async def create_new_world(display_name, start_cmd, sudo_start_cmd, visible):
    new_world = {
        "display_name": display_name,
        "start_cmd": start_cmd,
        "sudo_start_cmd": sudo_start_cmd,
        "visible": visible,
    }

    data = await get_data()

    log.debug(await search_world(display_name, data))
    if await search_world(display_name, data):
        log.debug(f"New World {display_name} couldn't be created because the display name is already in use")
        return False

    data["worlds"].append(new_world)
    await _save_data(data)

    return True


async def change_world(new_world):
    data = await get_data()
    for world in data["worlds"]:
        if world["display_name"] == new_world and world["visible"]:
            data["current_world"] = new_world
            await _save_data(data)
            return True
    return False


async def edit_new_world(editing_world_name, new_display_name, start_cmd, sudo_start_cmd, visible):
    data = await get_data()

    for i in range(len(data["worlds"])):
        if data["worlds"][i]["display_name"] == editing_world_name:
            if new_display_name not in ("", None):
                data["worlds"][i]["display_name"] = new_display_name
                if data["current_world"] == editing_world_name:
                    data["current_world"] = new_display_name
            if start_cmd not in ("", None):
                data["worlds"][i]["start_cmd"] = start_cmd
            if sudo_start_cmd not in ("", None):
                data["worlds"][i]["sudo_start_cmd"] = sudo_start_cmd
            if visible not in ("", None):
                data["worlds"][i]["visible"] = visible

            await _save_data(data)
            return data["worlds"][i]

    return False


async def delete_world(display_name):
    data = await get_data()

    world_to_delete = await search_world(display_name, data)
    if not world_to_delete:
        log.error(f"world to delete (display_name='{world_to_delete}') not found")
        return False

    for i in range(0, len(data["worlds"])):
        if data["worlds"][i]["display_name"] == display_name:
            del data["worlds"][i]
            log.debug(f"world '{display_name}' deleted succesfully")

            await _save_data(data)
            return True


async def search_world(display_name, data):
    for i in range(0, len(data["worlds"])):
        if data["worlds"][i]["display_name"] == display_name:
            return data["worlds"][i]
    return False


async def get_data():
    async with aiofiles.open(json_path, "r", encoding="utf-8") as file:
        content = await file.read()
        return json.loads(content)


async def _save_data(data: dict):
    async with aiofiles.open(json_path, "w", encoding="utf-8") as file:
        await file.write(json.dumps(data, indent=4))
