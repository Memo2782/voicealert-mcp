# app/core/behavioral_ai.py
from typing import Dict, Any
from app.database.mock_db import ABUELITOS_DB

class ExtendedBehavioralEngine:
    def __init__(self):
        # Local mirror mapping to track active live profiles
        self.profiles = ABUELITOS_DB

    def train_baseline_data(self, name: str, checkin_time_str: str, message_text: str) -> Dict[str, Any]:
        """
        Runs on every check-in. Automatically adjusts the senior's baseline habits 
        using moving mathematical averages with zero manual code updates required.
        """
        senior = self.profiles.get(name)
        if not senior:
            return {}

        baselines = senior["learned_behavioral_baselines"]
        word_count = len(message_text.split())
        hour = int(checkin_time_str.split(":")[0])

        # Exclude late-night/insomnia texts (00:00 - 05:00) from polluting their morning wake-up average
        if hour >= 5:
            baselines["total_logs_count"] += 1
            n = baselines["total_logs_count"]
            
            # Recalculate moving averages on the fly
            baselines["avg_waking_hour"] = ((baselines["avg_waking_hour"] * (n - 1)) + hour) / n
            baselines["avg_word_count"] = ((baselines["avg_word_count"] * (n - 1)) + word_count) / n

        return baselines

    def analyze_behavioral_safety(self, name: str, checkin_time_str: str, message_text: str) -> Dict[str, Any]:
        """
        Evaluates the current interaction data point against historical patterns 
        to detect hidden anomalies (Sleep disturbances, Lethargy, Delayed Waking).
        """
        senior = self.profiles.get(name)
        if not senior:
            return {"is_anomaly": False, "reason": "User not found"}

        baselines = senior["learned_behavioral_baselines"]
        thresholds = senior["anomaly_thresholds"]
        
        hour = int(checkin_time_str.split(":")[0])
        word_count = len(message_text.split())

        # 🚩 MATRIX 1: Late-Night Insomnia / Anxious Disruption Alert
        if 0 <= hour < 5:
            return {
                "is_anomaly": True,
                "type": "SLEEP_DISTURBANCE",
                "reason": f"Insomnia Warning: Abnormal check-in detected at {checkin_time_str} AM."
            }

        # 🚩 MATRIX 2: Delayed Check-In (Potential Fall or Non-Responsive)
        if hour > (baselines["avg_waking_hour"] + thresholds["max_allowed_delay_hours"]):
            return {
                "is_anomaly": True,
                "type": "DELAYED_WAKING",
                "reason": f"Delayed Waking: Checked in at {checkin_time_str}. Normal baseline is {round(baselines['avg_waking_hour'], 1)}:00 AM."
            }

        # 🚩 MATRIX 3: Severe Vocal/Speech Volumetric Drop (Confusion or Lethargy Indicators)
        # Only checks if a baseline history exists (logs count > 0)
        if baselines["total_logs_count"] > 0 and word_count <= (baselines["avg_word_count"] * thresholds["speech_drop_percentage"]):
            return {
                "is_anomaly": True,
                "type": "LETHARGY_DETECTOR",
                "reason": f"Speech Alteration: Message volume dropped to {word_count} words. Baseline average is {round(baselines['avg_word_count'], 1)} words."
            }

        return {"is_anomaly": False, "type": "NORMAL", "reason": "Behavior consistent with baseline patterns."}

behavioral_ai_engine = ExtendedBehavioralEngine()
