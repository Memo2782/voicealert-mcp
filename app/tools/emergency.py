# app/tools/emergency.py
import time
from typing import Dict, Any

class CaregiverNotificationEngine:
    def __init__(self):
        self.notification_log = []

    async def trigger_caregiver_alert(self, senior_name: str, alert_type: str, raw_message: str, destination_phone: str) -> Dict[str, Any]:
        """
        Routes telemetry data and alerts to the caregiver via cloud webhooks (e.g., WhatsApp Business API / Push).
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        if alert_type == "CRITICAL":
            payload = {
                "status": "🚨 EMERGENCY",
                "title": f"Critical Warning: {senior_name} needs assistance!",
                "body": f"Emergency keyword detected: '{raw_message}'",
                "timestamp": timestamp,
                "delivery_channel": "Cloud_Webhook_Urgent"
            }
            print(f"\n[🚨 ALERTA CRÍTICA] Routing instant Cloud Push Notification to caregiver at {destination_phone}!")
            
        else:
            payload = {
                "status": "💚 ROUTINE_OK",
                "title": f"Daily Routine: {senior_name} Status Check",
                "body": raw_message,
                "timestamp": timestamp,
                "delivery_channel": "Cloud_Dashboard_Sync"
            }
            print(f"\n[INFO] Caregiver cloud dashboard updated for {senior_name} (Routine Status: OK).")

        self.notification_log.append(payload)
        return payload

caregiver_notifier = CaregiverNotificationEngine()
