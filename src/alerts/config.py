"""Alerting configuration loaded from the project environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..agent.env_utils import get_env

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AlertSettings:
    enabled: bool = True
    webhook_url: str = ""
    secret: str = ""
    dry_run: bool = False
    scan_interval_seconds: int = 60
    approval_timeout_minutes: int = 60
    critical_timeout_multiplier: float = 2.0
    critical_order_amount: float = 50000.0
    retry_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    request_timeout_seconds: float = 10.0
    dedupe_cooldown_seconds: int = 86400
    state_db: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "alert_state.db")

    @classmethod
    def from_env(cls) -> "AlertSettings":
        return cls(
            enabled=_env_bool("ALERT_SCHEDULER_ENABLED", True),
            webhook_url=get_env("DINGTALK_WEBHOOK_URL", ""),
            secret=get_env("DINGTALK_SECRET", ""),
            dry_run=_env_bool("DINGTALK_DRY_RUN", False),
            scan_interval_seconds=max(10, int(get_env("ALERT_SCAN_INTERVAL_SECONDS", "60"))),
            approval_timeout_minutes=max(
                1, int(get_env("APPROVAL_TIMEOUT_MINUTES", "60"))
            ),
            critical_timeout_multiplier=max(
                1.0, float(get_env("APPROVAL_CRITICAL_MULTIPLIER", "2"))
            ),
            critical_order_amount=max(
                0.0, float(get_env("APPROVAL_CRITICAL_AMOUNT", "50000"))
            ),
            retry_attempts=max(1, int(get_env("DINGTALK_RETRY_ATTEMPTS", "3"))),
            retry_base_delay_seconds=max(
                0.0, float(get_env("DINGTALK_RETRY_BASE_DELAY", "1"))
            ),
            request_timeout_seconds=max(
                1.0, float(get_env("DINGTALK_TIMEOUT_SECONDS", "10"))
            ),
            dedupe_cooldown_seconds=max(
                0, int(get_env("ALERT_DEDUPE_COOLDOWN_SECONDS", "86400"))
            ),
            state_db=Path(
                get_env(
                    "ALERT_STATE_DB",
                    str(PROJECT_ROOT / "data" / "alert_state.db"),
                )
            ),
        )
