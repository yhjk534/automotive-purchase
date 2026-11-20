"""SQLite-backed deduplication and delivery-attempt tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class DedupeStore:
    """Claim notification keys atomically and persist delivery outcomes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """CREATE TABLE IF NOT EXISTS notification_events (
                   event_key       TEXT PRIMARY KEY,
                   alert_type      TEXT NOT NULL,
                   severity        TEXT NOT NULL,
                   payload_json    TEXT NOT NULL,
                   status          TEXT NOT NULL,
                   attempt_count   INTEGER NOT NULL DEFAULT 0,
                   first_seen_at   TEXT NOT NULL,
                   last_attempt_at TEXT NOT NULL,
                   last_sent_at    TEXT,
                   last_error      TEXT
               )"""
        )
        conn.commit()
        return conn

    def claim(
        self,
        *,
        event_key: str,
        alert_type: str,
        severity: str,
        payload: dict[str, Any],
        cooldown_seconds: int,
    ) -> bool:
        """Return True when this process may send the event."""
        now = datetime.now()
        now_text = now.isoformat()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM notification_events WHERE event_key = ?",
                (event_key,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """INSERT INTO notification_events
                       (event_key, alert_type, severity, payload_json, status,
                        attempt_count, first_seen_at, last_attempt_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        event_key,
                        alert_type,
                        severity,
                        json.dumps(payload, ensure_ascii=False),
                        "claimed",
                        1,
                        now_text,
                        now_text,
                    ),
                )
                conn.commit()
                return True

            last_sent_at = (
                datetime.fromisoformat(row["last_sent_at"])
                if row["last_sent_at"]
                else None
            )
            if (
                row["status"] == "sent"
                and last_sent_at
                and now - last_sent_at < timedelta(seconds=cooldown_seconds)
            ):
                conn.rollback()
                return False

            last_attempt = datetime.fromisoformat(row["last_attempt_at"])
            if row["status"] == "claimed" and now - last_attempt < timedelta(minutes=5):
                conn.rollback()
                return False

            conn.execute(
                """UPDATE notification_events
                   SET severity = ?, payload_json = ?, status = 'claimed',
                       attempt_count = attempt_count + 1, last_attempt_at = ?,
                       last_error = NULL
                   WHERE event_key = ?""",
                (
                    severity,
                    json.dumps(payload, ensure_ascii=False),
                    now_text,
                    event_key,
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def mark_sent(self, event_key: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE notification_events
                   SET status = 'sent', last_sent_at = ?, last_error = NULL
                   WHERE event_key = ?""",
                (datetime.now().isoformat(), event_key),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_failed(self, event_key: str, error: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE notification_events
                   SET status = 'failed', last_error = ?
                   WHERE event_key = ?""",
                (error[:1000], event_key),
            )
            conn.commit()
        finally:
            conn.close()

    def status(self) -> dict[str, int]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM notification_events GROUP BY status"
            ).fetchall()
            return {row["status"]: row["count"] for row in rows}
        finally:
            conn.close()
