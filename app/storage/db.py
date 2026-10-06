# app/storage/db.py
"""SQLite storage backend for the VoiceAlert Cloud SaaS.

Stores per-senior profiles (with their learned behavioral baselines and
thresholds), per-senior alert history, and phone-based subscriptions. Uses a
thread-safe sqlite3 connection; tests pass ":memory:" to get an isolated,
throw-away database.

The senior profile is persisted as a single JSON column so the schema stays
stable as new reference fields are added, while the mutable, frequently
written fields (baselines, alerts, subscriptions) are indexed individually.
"""
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

DEFAULT_DELAY_HOURS = 2.5
DEFAULT_SPEECH_DROP = 0.40
DEFAULT_MEDICATION_WINDOW = "08:00 AM - 09:30 AM"
DEFAULT_BASELINES = {"avg_waking_hour": 8.0, "avg_word_count": 12.0, "total_logs_count": 0}
DEFAULT_THRESHOLDS = {
    "max_allowed_delay_hours": DEFAULT_DELAY_HOURS,
    "speech_drop_percentage": DEFAULT_SPEECH_DROP,
}


class SQLiteBackend:
    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # check_same_thread=False because FastAPI runs handlers in a threadpool.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS seniors (
                    name           TEXT PRIMARY KEY,
                    profile_json   TEXT NOT NULL,
                    created_at     TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    senior_name    TEXT NOT NULL,
                    status         TEXT NOT NULL,
                    title          TEXT NOT NULL,
                    body           TEXT NOT NULL,
                    timestamp      TEXT NOT NULL,
                    routing_priority TEXT NOT NULL,
                    delivery_channel TEXT NOT NULL,
                    FOREIGN KEY (senior_name) REFERENCES seniors(name)
                );
                CREATE TABLE IF NOT EXISTS subscriptions (
                    phone          TEXT PRIMARY KEY,
                    senior_name    TEXT,
                    tier           TEXT NOT NULL,
                    status         TEXT NOT NULL,
                    son_name       TEXT,
                    caregiver_phone TEXT,
                    created_at     TEXT NOT NULL,
                    activated_at   TEXT
                );
                """
            )
            self._conn.commit()

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # ---- seniors / baselines ----
    def upsert_senior(self, name: str, profile: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO seniors (name, profile_json, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET profile_json=excluded.profile_json",
                (name, json.dumps(profile, ensure_ascii=False), self._now()),
            )
            self._conn.commit()

    def get_senior(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT profile_json FROM seniors WHERE name=?", (name,)
            ).fetchone()
        return json.loads(row["profile_json"]) if row else None

    def load_seniors(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, profile_json FROM seniors"
            ).fetchall()
        return {r["name"]: json.loads(r["profile_json"]) for r in rows}

    def upsert_baselines(self, name: str, baselines: Dict[str, Any]) -> None:
        # Reload-modify-replace the whole profile so JSON embedding stays a real
        # object (SQLite json_set on a JSON-string argument would double-encode
        # it and read back as a string).
        senior = self.get_senior(name)
        if senior is None:
            return
        senior["learned_behavioral_baselines"] = baselines
        self.upsert_senior(name, senior)

    def get_baselines(self, name: str) -> Optional[Dict[str, Any]]:
        senior = self.get_senior(name)
        if senior is None:
            return None
        return senior.get("learned_behavioral_baselines")

    # ---- alerts ----
    def add_alert(self, senior_name: str, payload: Dict[str, Any]) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alerts (senior_name, status, title, body, timestamp, "
                "routing_priority, delivery_channel) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    senior_name,
                    payload["status"], payload["title"], payload["body"],
                    payload["timestamp"], payload["routing_priority"],
                    payload["delivery_channel"],
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def list_alerts(self, senior_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, status, title, body, timestamp, routing_priority, delivery_channel "
                "FROM alerts WHERE senior_name=? ORDER BY id DESC LIMIT ?",
                (senior_name, limit),
            ).fetchall()
        return [
            {
                "id": r["id"], "status": r["status"], "title": r["title"],
                "body": r["body"], "timestamp": r["timestamp"],
                "routing_priority": r["routing_priority"],
                "delivery_channel": r["delivery_channel"],
            }
            for r in rows
        ]

    # ---- subscriptions (phone-based provisioning) ----
    def upsert_subscription(
        self, phone: str, tier: str = "TIER_1_TRIAL", senior_name: Optional[str] = None,
        son_name: Optional[str] = None, caregiver_phone: Optional[str] = None,
        status: str = "ACTIVE",
    ) -> None:
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT created_at FROM subscriptions WHERE phone=?", (phone,)
            ).fetchone()
            created = row["created_at"] if row else now
            self._conn.execute(
                "INSERT INTO subscriptions "
                "(phone, senior_name, tier, status, son_name, caregiver_phone, created_at, activated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(phone) DO UPDATE SET tier=excluded.tier, status=excluded.status, "
                "son_name=excluded.son_name, caregiver_phone=excluded.caregiver_phone, "
                "activated_at=excluded.activated_at",
                (phone, senior_name, tier, status, son_name, caregiver_phone, created, now),
            )
            self._conn.commit()

    def get_subscription(self, phone: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM subscriptions WHERE phone=?", (phone,)
            ).fetchone()
        return dict(row) if row else None

    def subscriptions(self, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if tier:
                rows = self._conn.execute(
                    "SELECT * FROM subscriptions WHERE tier=? ORDER BY created_at DESC", (tier,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM subscriptions ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def env_backend() -> Optional[SQLiteBackend]:
    """A SQLiteBackend when VA_DB_PATH is set (production), else None (JSON in-memory)."""
    path = os.environ.get("VA_DB_PATH")
    if not path:
        return None
    return SQLiteBackend(path)
