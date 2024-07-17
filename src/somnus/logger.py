import logging
from pathlib import Path

_LEVEL = logging.DEBUG

log = logging.getLogger("mc-server-control")

_formatter = logging.Formatter(
    "[%(asctime)s] [%(module)s/%(process)d/%(levelname)s]: %(message)s", datefmt="%d-%m-%y %H:%M:%S"
)

log.setLevel(_LEVEL)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(_LEVEL)
_console_handler.setFormatter(_formatter)
log.addHandler(_console_handler)

_LOG_FILE_PATH = Path.cwd() / "somnus.log"
open(_LOG_FILE_PATH, "w").close()
_file_handler = logging.FileHandler(_LOG_FILE_PATH)
_file_handler.setLevel(_LEVEL)
_file_handler.setFormatter(_formatter)
log.addHandler(_file_handler)
