"""Single logging entry point for the project.

Wraps the stdlib ``logging`` module so call sites never touch ``print`` or
``console`` directly. ``debug``/``info`` are silenced in production (when the
``ENV`` environment variable is ``prod``/``production``); ``warn``/``error``
always emit. When telemetry is added later, only this module changes.
"""

import logging
import os

_PROD_VALUES = {"prod", "production"}
_IS_PROD = os.environ.get("ENV", "development").strip().lower() in _PROD_VALUES
_LEVEL = logging.WARNING if _IS_PROD else logging.DEBUG

_logger = logging.getLogger("scraper")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
    _logger.addHandler(_handler)
    _logger.setLevel(_LEVEL)
    _logger.propagate = False


def debug(msg: str, *args: object) -> None:
    """Verbose debugging output. Development only."""
    _logger.debug(msg, *args)


def info(msg: str, *args: object) -> None:
    """General flow milestones. Development only."""
    _logger.info(msg, *args)


def warn(msg: str, *args: object) -> None:
    """Unexpected but recoverable situations. Always emitted."""
    _logger.warning(msg, *args)


def error(msg: str, *args: object) -> None:
    """Failures that need attention. Always emitted."""
    _logger.error(msg, *args)
