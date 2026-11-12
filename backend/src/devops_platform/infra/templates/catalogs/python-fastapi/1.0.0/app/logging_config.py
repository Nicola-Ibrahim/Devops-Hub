"""Small structured logging setup that keeps credentials out of log fields."""

import json
import logging
import logging.config
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
            },
            separators=(",", ":"),
        )


def configure_logging() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
            "root": {"handlers": ["console"], "level": "INFO"},
        }
    )
