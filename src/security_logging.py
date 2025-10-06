# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

# Taken from https://github.com/lucabello/owasp-logger

NESTED_JSON_KEY = "owasp_event"


@dataclass
class OWASPLogEvent:
    datetime: str  # ISO8601 timestamp with timezone
    appid: str
    event: str  # The type of event being logged (i.e. sys_crash)
    level: str  # Log level reflecting the importance of the event
    description: str  # Human-readable description of the event being logged
    type: str = "security"
    labels: dict[str, str] = field(default_factory=dict)  # All extra/custom labels go here

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_dict(self) -> Dict:
        log_event = dict(
            asdict(self),
            **self.labels,
        )
        log_event.pop("labels", None)
        return {k: v for k, v in log_event.items() if v is not None}


class OWASPLogger:
    def __init__(self, appid: str, logger: Optional[logging.Logger] = None):
        """OWASP-compliant logger."""
        self.appid = appid
        self.logger = logger or logging.getLogger(__name__)

    def __getattr__(self, item):
        """Delegate standard logging functions to the internal logger."""
        return getattr(self.logger, item)

    def log_event(self, event: str, level: int, description: str, **labels):
        """Emit an OWASP-compliant log."""
        log = OWASPLogEvent(
            datetime=datetime.now(timezone.utc).astimezone().isoformat(),
            appid=self.appid,
            event=event,
            level=logging.getLevelName(level),
            description=description,
            labels=labels,
        )
        self.logger.log(level, log.to_json(), extra={NESTED_JSON_KEY: log.to_dict()})
