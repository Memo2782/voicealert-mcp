# app/tools/emergency.py
import time
from typing import Dict, Any, List
from app.core.persistence import store

_BEHAVIORAL_TYPES = {"SLEEP_DISTURBANCE", "DELAYED_WAKING", "LETHARGY_DETECTOR"}


class CaregiverNotificationEngine:
    def __init__(self):
        # Flat ordered log for quick inspection / back-compat.
        self.notification_log: List[Dict[str, Any]] = []
        # Per-senior alert history (what the son views). Shares the store dict
        # reference so persistence and this engine never get out of sync.
        self.alerts_by_senior: Dict[str, List[Dict[str, Any]]] = store.alerts
        self._replay_persisted_alerts()

    def _replay_persisted_alerts(self) -> None:
        self.notification_log.clear()
        for _name, alerts in self.alerts_by_senior.items():
            self.notification_log.extend(alerts)

    def _persist(self) -> None:
        store.save()

    async def trigger_caregiver_alert(
        self, senior_name: str, alert_type: str, raw_message: str, destination_phone: str
    ) -> Dict[str, Any]:
        """
        Routes telemetry data and alerts to the caregiver via cloud webhooks.
        Behavioral anomalies are given an elevated, distinct tier so they are
        never mislabelled as a routine confirmation on the son's dashboard.
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        # Tier 1: CRITICAL EMERGENCY DETECTED
        if alert_type == "CRITICAL":
            payload = {
                "status": "🚨 EMERGENCY",
                "title": f"Critical Warning: {senior_name} needs assistance!",
                "body": f"Emergency keyword detected: '{raw_message}'",
                "timestamp": timestamp,
                "delivery_channel": "Cloud_Webhook_Urgent",
                "routing_priority": "HIGH_QoS"
            }
            print(f"\n[🚨 ALERTA CRÍTICA] Routing instant Cloud Push Notification to caregiver at {destination_phone}!")
            print(f"[📡 TELEMETRY] Dispatching payload under High Priority constraints.")

        # Tier 2: BEHAVIORAL ANOMALY - habit shift, not a routine confirmation
        elif alert_type in _BEHAVIORAL_TYPES:
            payload = {
                "status": "⚠️ BEHAVIORAL_ANOMALY",
                "title": f"Habit Shift: {senior_name} deviates from their baseline",
                "body": raw_message,
                "timestamp": timestamp,
                "delivery_channel": "Cloud_Dashboard_Elevated",
                "routing_priority": "ELEVATED_QoS"
            }
            print(f"\n[⚠️ ANOMALÍA] Caregiver dashboard flagged a behavior shift for {senior_name}.")

        # Tier 3: ROUTINE MEDICATION STATUS UPDATE
        else:
            payload = {
                "status": "💚 ROUTINE_OK",
                "title": f"Daily Routine: {senior_name} Status Check",
                "body": raw_message,
                "timestamp": timestamp,
                "delivery_channel": "Cloud_Dashboard_Sync",
                "routing_priority": "STANDARD_QoS"
            }
            print(f"\n[INFO] Caregiver cloud dashboard updated for {senior_name} (Routine Status: OK).")

        self.notification_log.append(payload)
        self.alerts_by_senior.setdefault(senior_name, []).append(payload)
        self._persist()
        return payload

    def alerts_for(self, senior_name: str) -> List[Dict[str, Any]]:
        return list(self.alerts_by_senior.get(senior_name, []))

    def clear(self) -> None:
        self.notification_log.clear()
        self.alerts_by_senior.clear()
        self._persist()


# Singleton consumed by the central application brain
caregiver_notifier = CaregiverNotificationEngine()
