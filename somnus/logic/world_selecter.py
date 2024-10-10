# TODO:
# 
# create_world(display_name: str, start_command: str, sudo_start_command: bool, visible: bool) Super-User-only
# change_world() -> display_name per Drop-Down auswählen
# show_worlds()
# edit_world(id:int, [display_name]: str, [start_command]: str, [sudo_start_command]: bool, [visible]: bool) -> wenn man felder leer lässt (oder nur Leerzeichen) wird nix geändert, sonst wirds überschrieben
# delete_world() -> display_name per Drop-Down auswählen
# 

from somnus.environment import Config, CONFIG
import os
import json
from somnus.logger import log
import aiofiles

json_path = "../world_selecter_data.json"


async def check_world_selecter_json():
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            try:
                if len(data.get("worlds")) > 0:
                    log.debug(f"'{json_path}' imported correctly")
                    return
            except:
                pass
    
    log.warning(f"'{json_path}' was not found")
    await _init_world_selecter_json()



async def _init_world_selecter_json():
    default_data = {
        "current_world": "Minecraft",
        "worlds": [
            {
                "display_name": "Minecraft",
                "start_cmd": Config.MC_SERVER_START_CMD,
                "sudo_start_cmd": Config.MC_SERVER_START_CMD_SUDO,
                "visible": True
            }
        ]
    }

    try:
        async with aiofiles.open(json_path, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(default_data, indent=4))
            log.debug(f"'{json_path}' was created")
    except Exception as e:
        log.error(f"Error creating JSON file: {e}")


async def get_current_world():
    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        
        current_world_name = data[current_world]
        current_world = _search_world(current_world_name, data)
        if current_world == False:
            log.error(f"Current world (display_name='{current_world_name}') not found")

        return current_world


async def create_new_world(display_name, start_cmd, sudo_start_cmd, visible):
    new_world = {
        "display_name": display_name,
        "start_cmd": start_cmd,
        "sudo_start_cmd": sudo_start_cmd,
        "visible": visible
    }

    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        if _search_world(display_name, data) != False:
            log.debug(f"New World {display_name} couldn't be created because the display name is already in use")
            return False
        
        data["worlds"].append(new_world)
        json.dump(data, file, indent=4, ensure_ascii=False)
    return True


async def edit_new_world(id, display_name, start_cmd, sudo_start_cmd, visible):
    new_world = {
        "display_name": display_name,
        "start_cmd": start_cmd,
        "sudo_start_cmd": sudo_start_cmd,
        "visible": visible
    }

    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        world_count = len(data["worlds"])
        if world_count >= id:
            log.debug(f"World index out of range: input={id}; list_lenth={world_count}")
            return False
        
        if display_name != "" and display_name != " ":
            data["worlds"][id]["display_name"] = display_name
        if start_cmd != "" and start_cmd != " ":
            data["worlds"][id]["start_cmd"] = start_cmd
        if sudo_start_cmd != "" and sudo_start_cmd != " ":
            data["worlds"][id]["sudo_start_cmd"] = sudo_start_cmd
        if visible != "" and visible != " ":
            data["worlds"][id]["visible"] = visible

        json.dump(data, file, indent=4, ensure_ascii=False)
    
    return True

async def delete_world(display_name):
    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        world_to_delete = _search_world(display_name, data)
        if world_to_delete == False:
            log.error(f"world to delete (display_name='{world_to_delete}') not found")
            return False
        
        for i in range(0, len(data["worlds"])):
            if data["worlds"][i]["display_name"] == display_name:
                del data["worlds"][i]
                log.debug(f"world '{display_name}' deleted succesfully")

                json.dump(data, file, indent=4, ensure_ascii=False)
                return True


async def get_all_data():
    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        return data


async def _search_world(display_name, data):
    for i in range(0, len(data["worlds"])):
        if data["worlds"][i]["display_name"] == display_name:
            return data["worlds"][i]
    return False