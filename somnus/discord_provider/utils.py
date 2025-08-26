def edit_error_for_discord_subtitle(err: Exception) -> str:
    msg = (str(err) or "").strip()
    if msg:
        return str(msg).replace("\n", "\n-# ")
    else:
        return f"No error message. Error type: '{type(err).__name__}'"


def generate_progress_bar(value: int, max_value: int, message: str = "") -> str:
    progress = "█" * value + "░" * (max_value - value)
    if message:
        return f"{message}\n{progress}"
    return progress
