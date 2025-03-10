def trim_text_for_discord_subtitle(text: str) -> str:
    return str(text).replace("\n", " ")


def generate_progress_bar(value: int, max_value: int, message: str = "") -> str:
    progress = "█" * value + "░" * (max_value - value)
    if message:
        return f"{message}\n{progress}"
    return progress
