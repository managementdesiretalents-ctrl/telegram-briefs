"""Logging configuration helpers for the telegram briefs services.

The application has a couple of entry-points (FastAPI, background scripts)
that all want a consistent logging format.  Previously the code attempted to
import ``logging_setup`` but the module was missing which resulted in a
``ModuleNotFoundError`` when starting the API.  This module provides the
missing helper and centralises the formatting/handler setup so the callers can
simply request a named logger.
"""

from __future__ import annotations

import logging
from typing import Optional

_DEFAULT_LEVEL = logging.INFO
_DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(name: str, *, level: int = _DEFAULT_LEVEL,
                  fmt: str = _DEFAULT_FORMAT,
                  handler: Optional[logging.Handler] = None) -> logging.Logger:
    """Return a configured logger for ``name``.

    Parameters
    ----------
    name:
        The logger name to configure.
    level:
        Logging level to apply.  Defaults to :data:`logging.INFO`.
    fmt:
        Format string used by the handler.  The default matches the format
        previously used by the project.
    handler:
        Optional handler instance.  If omitted a :class:`~logging.StreamHandler`
        writing to ``sys.stderr`` is created.

    The helper avoids adding duplicate handlers when invoked multiple times
    (which happens with reloads in development).  Callers receive the logger so
    they can log immediately.
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if handler is None:
        handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt))

    # Prevent duplicate handlers on successive calls (e.g. module reloads).
    if not any(isinstance(h, handler.__class__) and h.stream == getattr(handler, "stream", None)
               for h in logger.handlers):
        logger.addHandler(handler)

    logger.propagate = False
    return logger
