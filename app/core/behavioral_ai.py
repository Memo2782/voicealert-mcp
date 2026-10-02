# app/core/behavioral_ai.py
from typing import Dict, Any

# Baseline applied to a senior before any history exists. Scored against, never mutated.
DEFAULT_BASELINE = {
    "expected_checkin_hour": 8,  # Default: 8:00 AM
    "average_word_count": 5.0
}

class SeniorBehavioralEngine:
    def __init__(self):
        # Local memory cache to store historical check-in times and sentiments
        self.behavior_history = {}

    def learn_checkin_baseline(self, senior_name: str, current_checkin_time: str, word_count: int) -> Dict[str, Any]:
        """
        Folds the newest check-in into the senior's running baseline via a simple
        moving average. Must be called *after* analyze_vocal_anomaly: learning first
        would let a late or terse check-in drag the baseline toward itself and mask
        the very anomaly it should raise.
        """
        profile = self.behavior_history.setdefault(senior_name, {
            "expected_checkin_hour": DEFAULT_BASELINE["expected_checkin_hour"],
            "average_word_count": DEFAULT_BASELINE["average_word_count"],
            "total_checkins_logged": 0,
            "consecutive_anomalies": 0
        })

        # Parse current check-in hour
        current_hour = int(current_checkin_time.split(":")[0])

        profile["total_checkins_logged"] += 1
        n = profile["total_checkins_logged"]

        profile["expected_checkin_hour"] = ((profile["expected_checkin_hour"] * (n - 1)) + current_hour) / n
        profile["average_word_count"] = ((profile["average_word_count"] * (n - 1)) + word_count) / n

        return profile

    def analyze_vocal_anomaly(self, senior_name: str, voice_text: str, current_time_str: str) -> Dict[str, Any]:
        """
        Scores a check-in against the habits already learned from previous check-ins.
        Never folds the current check-in into the baseline it is compared against, so
        a single outlier cannot normalize itself away.
        """
        learned = self.behavior_history.get(senior_name)
        expected_hour = learned["expected_checkin_hour"] if learned else DEFAULT_BASELINE["expected_checkin_hour"]
        average_words = learned["average_word_count"] if learned else DEFAULT_BASELINE["average_word_count"]

        current_hour = int(current_time_str.split(":")[0])
        words = len(voice_text.split())

        is_anomaly = False
        reason = "Normal Behavior"

        # Anomaly Condition 1: Check-in hour is 3+ hours later than their learned average
        if current_hour > (expected_hour + 3):
            is_anomaly = True
            reason = f"Delayed Check-in: Senior usually checks in around {int(expected_hour)}:00 AM."

        # Anomaly Condition 2: Drastic reduction in words (potential lethargy or confusion)
        elif words < (average_words * 0.3) and words > 0:
            is_anomaly = True
            reason = "Speech Alteration: Message is unusually brief compared to their normal baseline."

        if learned:
            learned["consecutive_anomalies"] = learned["consecutive_anomalies"] + 1 if is_anomaly else 0

        return {
            "is_behavioral_anomaly": is_anomaly,
            "reason": reason,
            "consecutive_flags": learned["consecutive_anomalies"] if learned else 0,
            "learned_expected_hour": round(expected_hour, 1)
        }

# Instantiate global engine
behavioral_ai_engine = SeniorBehavioralEngine()

