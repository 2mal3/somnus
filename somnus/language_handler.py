from yai18n import Translator

from somnus.config import CONFIG


LH = Translator(fallback_locale="en", default_locale=CONFIG.LANGUAGE)
