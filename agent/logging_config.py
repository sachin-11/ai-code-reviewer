import logging
import os

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    # logging.basicConfig() is a no-op if the root logger already has a
    # handler, so calling this from multiple entrypoints is safe. Without
    # it, INFO-level records are silently dropped everywhere (the default
    # root logger sits at WARNING with no handler at all) -- every logger.*
    # call in agent/ and service/ depends on this having run first.
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=_LOG_FORMAT)
