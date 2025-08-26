import pytest
from somnus.discord_provider.utils import edit_error_for_discord_subtitle, generate_progress_bar

class CustomException(Exception):
    def __str__(self):
        return "error line1\nerror line2"

@pytest.mark.parametrize(
    "err, expected",
    [
        (CustomException(), "error line1\n-# error line2"),
        (Exception(), "No error message. Error type: 'Exception'"),
    ],
)
def test_edit_error_for_discord_subtitle(err, expected):
    result = edit_error_for_discord_subtitle(err)
    assert result == expected

@pytest.mark.parametrize(
    "value, max_value, expected",
    [
        (0, 5, "░░░░░"),
        (3, 5, "███░░"),
        (5, 5, "█████"),
    ],
)
def test_generate_progress_bar_without_message(value, max_value, expected):
    result = generate_progress_bar(value, max_value)
    assert result == expected

def test_generate_progress_bar_with_message():
    message = "Progress"
    value = 2
    max_value = 4
    result = generate_progress_bar(value, max_value, message)
    assert result == "Progress\n██░░"

@pytest.mark.parametrize(
    "value, max_value",
    [
        (6, 5),
        (-1, 5),
    ],
)
def test_generate_progress_bar_invalid_inputs(value, max_value):
    with pytest.raises(ValueError):
        generate_progress_bar(value, max_value)
