import logging
import datetime
from pathlib import Path

from somnus.config import CONFIG

_LEVEL = logging.DEBUG if CONFIG.DEBUG_LOGGING else logging.INFO

log = logging.getLogger("somnus")

_formatter = logging.Formatter(
    "[%(asctime)s] [%(module)s/%(process)d/%(levelname)s]: %(message)s", datefmt="%d-%m-%y %H:%M:%S"
)

log.setLevel(_LEVEL)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(_LEVEL)
_console_handler.setFormatter(_formatter)
log.addHandler(_console_handler)


_file_name = datetime.datetime.now().strftime("%y-%m-%d_%H-%M-%S") + ".log"
_log_file_path = Path.cwd() / "data" / "logs" / _file_name
_log_file_path.parent.mkdir(parents=True, exist_ok=True)
open(_log_file_path, "w").close()

_file_handler = logging.FileHandler(_log_file_path)
_file_handler.setLevel(_LEVEL)
_file_handler.setFormatter(_formatter)
log.addHandler(_file_handler)
