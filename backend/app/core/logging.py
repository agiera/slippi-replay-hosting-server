import logging

from app.core.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    """Set up the root logger once; idempotent so tests/imports can call it freely."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    root = logging.getLogger()
    requested_level = str(settings.LOG_LEVEL).strip().upper()
    level = requested_level if requested_level in logging.getLevelNamesMapping() else "INFO"
    root.setLevel(level)
    root.handlers = [handler]
    if level != requested_level:
        root.warning("Unknown LOG_LEVEL %r; using INFO", settings.LOG_LEVEL)

    # uvicorn installs its own handlers on these; let ours format them too.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
