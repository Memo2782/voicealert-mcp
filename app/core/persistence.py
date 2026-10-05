# app/core/persistence.py
"""Per-senior learning state and alert history persisted to disk.

The behavioral engine and the caregiver notifier are in-process singletons,
so without persistence every server restart would erase a senior's learned
baselines and alert history. This module is the single source of truth for
cross-restart state; it deliberately imports nothing from the rest of the app
to avoid circular imports.
"""
import json
import os
import tempfile

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE_DIR, "data")


class StateStore:
    """Thread-unsafe singleton holding baseline profiles and alert history."""

    def __init__(self) -> None:
        self.profiles: dict = {}
        self.alerts: dict = {}
        self._path = os.environ.get(
            "VA_STATE_PATH", os.path.join(DATA_DIR, "state.json")
        )

    def load(self) -> "StateStore":
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {}
        self.profiles = data.get("profiles", {})
        self.alerts = data.get("alerts", {})
        return self

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        # Atomic-ish write so a crash mid-write never corrupts the state file.
        fd, tmp = tempfile.mkstemp(
            prefix=".state.", suffix=".json.tmp", dir=os.path.dirname(self._path) or "."
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(
                    {"profiles": self.profiles, "alerts": self.alerts},
                    fh,
                    indent=2,
                    ensure_ascii=False,
                )
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def clear(self) -> None:
        try:
            os.remove(self._path)
        except FileNotFoundError:
            pass
        self.profiles.clear()
        self.alerts.clear()


store = StateStore()
store.load()
