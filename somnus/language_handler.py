import json
import os
from somnus.logger import log

class LanguageHandler:
    dictionary = {}

    def language_setup(self, language: str):
        locales_path = "somnus/locales"

        path_to_correct_dictionary = os.path.join(locales_path, language + ".json")

        if os.path.exists(path_to_correct_dictionary):
            with open(path_to_correct_dictionary, "r", encoding="utf-8") as f:
                self.dictionary = json.load(f)
        else:
            raise FileNotFoundError(f"Language does '{language}' not exist. Change LANGUAGE in .env to {self._get_available_languages(locales_path)}!")

        log.debug(f"Language '{language}' was selecetd succesfully")


    def _get_available_languages(self, path: str) -> str:
        out = []
        for file in os.listdir(path):
            if file.endswith(".json"):
                out.append(file.replace(".json", ""))
        return ", ".join(i for i in out)


    def _get_nested_value(self, data: dict, key_path: str) -> str:
        keys = key_path.split(".")
        for key in keys:
            if key not in data:
                return key_path
            data = data[key]
        return data

    def t(self, key_path: str, **kwargs) -> str:
        try:
            template = self._get_nested_value(self.dictionary, key_path)
            return template.format(**kwargs)
        except KeyError:
            return template

LH = LanguageHandler()
