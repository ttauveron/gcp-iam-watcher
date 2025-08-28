import logging
import os
from dataclasses import dataclass

DEFAULT_CHANNEL = "#test-temp"


@dataclass(frozen=True)
class Config:
    dest_types: str
    log_level: int


def load_config() -> Config:
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    # Default to Slack, but we won't require Slack vars unless Slack is actually selected.
    dest_types = os.getenv("DEST_TYPES", os.getenv("DEST_TYPE", "slack"))
    return Config(dest_types=dest_types, log_level=level)
