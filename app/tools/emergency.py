# app/tools/emergency.py
import time
from typing import Dict, Any

class CaregiverNotificationEngine:
    def __init__(self):
        self.notification_log = []

    async def trigger_caregiver_alert(self, senior_name: str, alert_type: str, raw_message: str, destination_phone: str) -> Dict[str, Any]:
        """
        Core logic to route telemetry data and emergency alerts to the caregiver's dashboard.
        Simulates high-priority transmission metrics tailored to elder care.
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        # Tier 1: CRITICAL EMERGENCY DETECTED
        if alert_type == "CRITICAL":
            payload = {
                "status": "🚨 EMERGENCY",
                "title": f"Critical Warning: {senior_name} needs assistance!",
                "body": f"Emergency keyword detected in voice text: '{raw_message}'",
                "timestamp": timestamp,
                "routing_priority": "HIGH_QoS"
            }
            print(f"\n[🚨 ALERTA CRÍTICA] Discharging instant Push Notification to caregiver at {destination_phone}!")
            print(f"[📡 TELEMETRY] Dispatching payload under High Priority constraints.")
            
        # Tier 2: ROUTINE MEDICATION STATUS UPDATE
        else:
            payload = {
                "status": "💚 ROUTINE_OK",
                "title": f"Daily Routine: {senior_name} Status Check",
                "body": raw_message,
                "timestamp": timestamp,
                "routing_priority": "STANDARD_QoS"
            }
            print(f"\n[INFO] Caregiver dashboard updated for {senior_name} (Routine Status: OK).")

        # Logging the event locally for verification testing
        self.notification_log.append(payload)
        return payload

# Instantiating a global notifier to be consumed by the central application brain
caregiver_notifier = CaregiverNotificationEngine()

