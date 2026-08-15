import json
import logging

logger = logging.getLogger("resume_matcher")


def log_event(event: str, **fields: str | int | float | None) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True))
