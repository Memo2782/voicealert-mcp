# app/core/behavioral_ai.py
from typing import Dict, Any, Optional
from app.database.mock_db import ABUELITOS_DB
from app.core.persistence import store

_DEFAULT_BASELINE = {
    "avg_waking_hour": 8.0,          # Learns normal morning wake-up time
    "avg_word_count": 12.0,          # Learns normal talking message length
    "total_logs_count": 0
}
_DEFAULT_THRESHOLDS = {
    "max_allowed_delay_hours": 2.5,  # Alert if 2.5 hours past typical time
    "speech_drop_percentage": 0.40   # Alert if speech drops below 40% of standard volume
}


class ExtendedBehavioralEngine:
    """Tracks one behavioral profile per senior.

    A senior may be backed by the JSON state store (default) or by a real
    SQLite backend (app.storage.db.SQLiteBackend). When backed by a database
    the in-memory profile dict is seeded from the DB and every training step
    writes baselines back, so day-by-day learning survives restarts.
    """

    def __init__(self, backend=None):
        self.backend = backend
        if backend is None:
            self.profiles = ABUELITOS_DB
            # Restore any persisted baselines so learning is continuous.
            for name, senior in self.profiles.items():
                saved = store.profiles.get(name, {}).get("learned_behavioral_baselines")
                if saved:
                    senior.setdefault("learned_behavioral_baselines", dict(_DEFAULT_BASELINE))
                    senior["learned_behavioral_baselines"].update(saved)
        else:
            self.profiles = backend.load_seniors()

    def _persist(self) -> None:
        if self.backend is None:
            store.profiles = {
                name: {"learned_behavioral_baselines": senior["learned_behavioral_baselines"]}
                for name, senior in self.profiles.items()
            }
            store.save()
        else:
            for name, senior in self.profiles.items():
                self.backend.upsert_baselines(name, senior.get("learned_behavioral_baselines", dict(_DEFAULT_BASELINE)))

    def train_baseline_data(self, name: str, checkin_time_str: str, message_text: str) -> Dict[str, Any]:
        """
        Runs on every check-in. Adjusts habits using moving mathematical averages.
        Includes validation guards to protect averages from corrupt empty inputs.
        """
        senior = self.profiles.get(name)
        if not senior:
            return {}

        baselines = senior["learned_behavioral_baselines"]

        # Clean whitespaces and calculate true words
        words_list = [w for i, w in enumerate(message_text.split()) if w.strip()]
        word_count = len(words_list)

        #  GUARD: Completely ignore empty text inputs or silent voice notes
        if word_count == 0:
            return baselines

        hour = int(checkin_time_str.split(":")[0])

        # Exclude late-night/insomnia texts (00:00 - 05:00) from normal morning averages
        if hour >= 5:
            baselines["total_logs_count"] += 1
            n = baselines["total_logs_count"]

            # Recalculate moving averages cleanly on the fly
            baselines["avg_waking_hour"] = ((baselines["avg_waking_hour"] * (n - 1)) + hour) / n
            baselines["avg_word_count"] = ((baselines["avg_word_count"] * (n - 1)) + word_count) / n

        self._persist()
        return baselines

    def analyze_behavioral_safety(self, name: str, checkin_time_str: str, message_text: str) -> Dict[str, Any]:
        """
        Evaluates the current interaction data point against historical patterns
        to detect hidden anomalies (Sleep disturbances, Lethargy, Delayed Waking).
        Scored against already-learned history only; it never folds the current
        check-in into the baseline it is compared against.
        """
        senior = self.profiles.get(name)
        if not senior:
            return {"is_anomaly": False, "type": "NORMAL", "reason": "User not found"}

        baselines = senior["learned_behavioral_baselines"]
        thresholds = senior["anomaly_thresholds"]

        hour = int(checkin_time_str.split(":")[0])

        # Clean whitespaces and calculate true words
        words_list = [w for i, w in enumerate(message_text.split()) if w.strip()]
        word_count = len(words_list)

        #  GUARD: If message is empty, don't trigger anomalies, skip downstream calculation
        if word_count == 0:
            return {"is_anomaly": False, "type": "NORMAL", "reason": "Empty text skipped during evaluation."}

        # MATRIX 1: Late-Night Insomnia / Anxious Disruption Alert
        if 0 <= hour < 5:
            return {
                "is_anomaly": True,
                "type": "SLEEP_DISTURBANCE",
                "reason": f"Insomnia Warning: Abnormal check-in detected at {checkin_time_str} AM."
            }

        # MATRIX 2: Delayed Check-In (Potential Fall or Non-Responsive)
        if hour > (baselines["avg_waking_hour"] + thresholds["max_allowed_delay_hours"]):
            return {
                "is_anomaly": True,
                "type": "DELAYED_WAKING",
                "reason": f"Delayed Waking: Checked in at {checkin_time_str}. Normal baseline is {round(baselines['avg_waking_hour'], 1)}:00 AM."
            }

        # MATRIX 3: Severe Vocal/Speech Volumetric Drop (Confusion or Lethargy Indicators)
        if baselines["total_logs_count"] > 0 and word_count <= (baselines["avg_word_count"] * thresholds["speech_drop_percentage"]):
            return {
                "is_anomaly": True,
                "type": "LETHARGY_DETECTOR",
                "reason": f"Speech Alteration: Message volume dropped to {word_count} words. Baseline average is {round(baselines['avg_word_count'], 1)} words."
            }

        return {"is_anomaly": False, "type": "NORMAL", "reason": "Behavior consistent with baseline patterns."}


# Module-level singleton: real DB when VA_DB_PATH is set, else JSON store.
from app.storage.db import env_backend  # noqa: E402

behavioral_ai_engine = ExtendedBehavioralEngine(backend=env_backend())
