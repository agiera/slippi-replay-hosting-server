"""LOG_LEVEL from the environment is forgiving: any case works, junk falls back to INFO."""
import logging

import pytest

from app.core import logging as app_logging
from app.core.config import settings


@pytest.fixture()
def fresh_logging(monkeypatch):
    root = logging.getLogger()
    saved = (root.level, root.handlers[:])
    monkeypatch.setattr(app_logging, "_CONFIGURED", False)
    yield
    root.setLevel(saved[0])
    root.handlers = saved[1]


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("info", logging.INFO),
        ("Debug", logging.DEBUG),
        (" WARNING ", logging.WARNING),
        ("verbose", logging.INFO),
        ("", logging.INFO),
    ],
)
def test_log_level_is_case_insensitive_and_falls_back_to_info(monkeypatch, fresh_logging, configured, expected):
    monkeypatch.setattr(settings, "LOG_LEVEL", configured)
    app_logging.configure_logging()
    assert logging.getLogger().level == expected
