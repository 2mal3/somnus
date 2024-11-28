import json
import os
import asyncio
from somnus.logger import log

dictionary = {}

def language_setup(language: str):
    global dictionary
    locales_path = "somnus/locales"

    path_to_correct_dictionary = os.path.join(locales_path, language + ".json")

    if os.path.exists(path_to_correct_dictionary):
        with open(path_to_correct_dictionary, "r", encoding="utf-8") as f:
            dictionary = json.load(f)
    else:
        raise FileExistsError(f"Language does '{language}' not exist. Change LANGUAGE in .env to {_get_available_languages(locales_path)}!")
    
    log.debug(f"Language '{language}' was selecetd succesfully")

def _get_available_languages(path: str) -> str:
    out = []
    for file in os.listdir(path):
        if file.endswith(".json"):
            out.append(file.replace(".json", ""))
    return ", ".join(i for i in out)
    

def _get_nested_value(data: dict, key_path: str) -> str:
    keys = key_path.split(".")
    for key in keys:
        if key not in data:
            return key_path
        data = data[key]
    return data

def t(key_path: str, **kwargs) -> str:
    global dictionary
    try:
        template = _get_nested_value(dictionary, key_path)
        return template.format(**kwargs)
    except KeyError as e:
        return template