# tests/test_mcp.py
import unittest
import asyncio
from app.main import verify_senior_routine, normalize_text
from app.tools.emergency import caregiver_notifier
from app.core.behavioral_ai import behavioral_ai_engine

class TestVoiceAlertPipeline(unittest.TestCase):

    def setUp(self):
        """Sets up a clean loop environment for testing async routines."""
        self.loop = asyncio.get_event_loop()
        # The engine and notifier are module-level singletons, so reset their
        # learned state to keep each case independent of the ones before it.
        behavioral_ai_engine.behavior_history.clear()
        caregiver_notifier.notification_log.clear()

    def test_text_normalization(self):
        """Tests that accents and casing are stripped correctly for Mexico context."""
        input_text = "Ya me la tomé, Don Manuel"
        expected_output = "ya me la tome, don manuel"
        self.assertEqual(normalize_text(input_text), expected_output)

    def test_routine_success_with_accents(self):
        """Validates that a senior checking in without accents logs a SUCCESS state."""
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome")
        )
        self.assertIn("[SUCCESS]", result)
        self.assertIn("Losartán 50mg", result)

    def test_emergency_trigger_logic(self):
        """Validates that a critical keyword triggers high-priority caregiver routing."""
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Me caí y me duele mucho")
        )
        self.assertIn("[🚨 CRITICAL EMERGENCY]", result)
        
        # Verify the notification engine actually logged the critical payload
        last_notification = caregiver_notifier.notification_log[-1]
        self.assertEqual(last_notification["status"], "🚨 EMERGENCY")
        self.assertEqual(last_notification["routing_priority"], "HIGH_QoS")

    def test_unregistered_user_error(self):
        """Ensures system safely rejects non-registered user inputs."""
        result = self.loop.run_until_complete(
            verify_senior_routine("Unknown User", "Hola")
        )
        self.assertIn("Error", result)

class TestBehavioralAnomalyDetection(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        behavioral_ai_engine.behavior_history.clear()
        caregiver_notifier.notification_log.clear()

    def test_delayed_checkin_flags_anomaly(self):
        """A check-in 3+ hours past the learned baseline raises a habit alert."""
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "08:00")
        )
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "12:30")
        )
        self.assertIn("[⚠️ BEHAVIORAL ALERT]", result)
        self.assertIn("Delayed Check-in", result)

    def test_outlier_cannot_drag_its_own_baseline(self):
        """The late check-in must be scored before it is folded into the baseline."""
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "08:00")
        )
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "12:30")
        )
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "08:00")
        )
        # An 08:00 return is still normal for this senior: the 12:30 outlier did
        # not move the learned average far enough to manufacture false alarms.
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "08:00")
        )
        self.assertIn("[SUCCESS]", result)

    def test_on_time_checkin_is_not_an_anomaly(self):
        """A check-in within 3 hours of the baseline stays a plain routine success."""
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "08:00")
        )
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "09:00")
        )
        self.assertIn("[SUCCESS]", result)

    def test_unusually_brief_message_flags_speech_alteration(self):
        """A drastic drop in word count versus the baseline is treated as lethargy."""
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Buenos dias a todos los que me escuchan hoy", "08:00")
        )
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Auxilio", "08:00")
        )
        self.assertIn("[⚠️ BEHAVIORAL ALERT]", result)
        self.assertIn("Speech Alteration", result)

    def test_behavioral_alert_is_not_logged_as_routine_ok(self):
        """A habit shift must not reach the caregiver dashboard as a routine confirmation."""
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "08:00")
        )
        self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome", "12:30")
        )
        last_notification = caregiver_notifier.notification_log[-1]
        self.assertEqual(last_notification["status"], "⚠️ BEHAVIORAL_ANOMALY")
        self.assertEqual(last_notification["routing_priority"], "ELEVATED_QoS")

    def test_emergency_keyword_outranks_behavioral_anomaly(self):
        """An explicit emergency phrase routes as CRITICAL, not as a habit shift."""
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Me cai y me duele mucho", "08:00")
        )
        self.assertIn("[🚨 CRITICAL EMERGENCY]", result)
        self.assertEqual(caregiver_notifier.notification_log[-1]["status"], "🚨 EMERGENCY")

    def test_immobility_phrase_triggers_emergency(self):
        """"No me puedo mover" is an emergency phrase and must route as CRITICAL."""
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "No me puedo mover de la cama", "08:00")
        )
        self.assertIn("[🚨 CRITICAL EMERGENCY]", result)

if __name__ == "__main__":
    unittest.main()
