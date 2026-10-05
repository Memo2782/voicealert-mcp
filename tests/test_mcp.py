# tests/test_mcp.py
import unittest
import asyncio
from app.main import verify_senior_routine, son_view, provision_senior, normalize_text
from app.core.behavioral_ai import ExtendedBehavioralEngine, _DEFAULT_BASELINE
from app.core.persistence import store
from app.tools.emergency import caregiver_notifier, CaregiverNotificationEngine
from app.database.mock_db import ABUELITOS_DB

# Seniors shipped from the seed database; provisioning must not pollute them.
SEED_SENIORS = list(ABUELITOS_DB)


def _reset_state():
    """Wipe persisted + in-memory state so every test starts from the seed profile."""
    store.clear()
    caregiver_notifier.clear()
    ABUELITOS_DB["Don Manuel"]["learned_behavioral_baselines"] = dict(_DEFAULT_BASELINE)
    for name in list(ABUELITOS_DB):
        if name not in SEED_SENIORS:
            del ABUELITOS_DB[name]


class TestVoiceAlertExtendedScenarios(unittest.TestCase):

    def setUp(self):
        """Resets the behavioral memory cache before every single test execution."""
        self.loop = asyncio.get_event_loop()
        _reset_state()

    def test_insomnia_edge_case(self):
        """
        SCENARIO 1: Deep Night / Insomnia Disturbance
        Verifies that messages sent between 00:00 and 05:00 AM immediately 
        trigger a SLEEP_DISTURBANCE warning without polluting daytime habits.
        """
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "No puedo dormir mijo me siento ansioso", "03:00")
        )
        self.assertIn("[⚠️ BEHAVIORAL WARNING]", result)
        self.assertIn("Insomnia Warning", result)

        # Verify it didn't change the daytime waking baseline
        baselines = ABUELITOS_DB["Don Manuel"]["learned_behavioral_baselines"]
        self.assertEqual(baselines["avg_waking_hour"], 8.0)
        self.assertEqual(baselines["total_logs_count"], 0)

    def test_progressive_habit_adaptation(self):
        """
        SCENARIO 2: Gradual Lifestyle Shift (Dynamic Learning)
        If the senior slowly starts waking up earlier over a week, the engine
        must adapt smoothly without triggering false alarms.
        """
        hours_sequence = ["08:00", "08:00", "07:30", "07:00", "06:30", "06:00", "06:00"]
        message = "Hola mijo buenos dias ya me tome la pastilla del desayuno"

        for daily_hour in hours_sequence:
            result = self.loop.run_until_complete(
                verify_senior_routine("Don Manuel", message, daily_hour)
            )
            # Ensure a gradual change NEVER triggers a false alarm delay block
            self.assertNotIn("[⚠️ BEHAVIORAL WARNING]", result)
            self.assertNotIn("[🚨 CRITICAL]", result)

        # Confirm the baseline successfully adapted to the new habit curve
        baselines = ABUELITOS_DB["Don Manuel"]["learned_behavioral_baselines"]
        self.assertLess(baselines["avg_waking_hour"], 8.0)

    def test_vocal_lethargy_and_recovery_loop(self):
        """
        SCENARIO 3: Cognitive Fatigue followed by Recovery Flow
        Tests that an abrupt drop in word count triggers an alert, but if 
        the senior recovers and speaks normally again, the alert clears.
        """
        long_msg = "Hola mijo buenos dias ya me tome la pastilla de la presion"
        for _ in range(3):
            self.loop.run_until_complete(verify_senior_routine("Don Manuel", long_msg, "08:00"))

        # Day 4: Sudden drop to 1 word (Lethargy/Confusion index)
        fatigue_result = self.loop.run_until_complete(verify_senior_routine("Don Manuel", "tome", "08:00"))
        self.assertIn("[⚠️ BEHAVIORAL WARNING]", fatigue_result)
        self.assertIn("Speech Alteration", fatigue_result)

        # Day 5: Recovery (Senior speaks normally again)
        recovery_result = self.loop.run_until_complete(verify_senior_routine("Don Manuel", long_msg, "08:00"))
        self.assertIn("[SUCCESS]", recovery_result)

    def test_malicious_empty_input_injection(self):
        """
        SCENARIO 4: Security and Input Sanitization Fault-Tolerance
        Verifies that empty audio transcriptions or whitespace strings do not 
        crash the engine or corrupt the mathematical moving averages.
        """
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "     ", "08:00")
        )
        self.assertIn("[TRACKING]", result)

        baselines = ABUELITOS_DB["Don Manuel"]["learned_behavioral_baselines"]
        self.assertTrue(baselines["avg_word_count"] > 0)
        self.assertEqual(baselines["total_logs_count"], 0)


class TestProvisioningAndSonView(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        _reset_state()

    def test_provision_then_monitor_individual(self):
        """A provisioned senior gets a fresh baseline and is learned independently."""
        provision = self.loop.run_until_complete(
            provision_senior(
                name="Abuelita Rosa", age=68, city="Guadalajara",
                living_situation="Lives alone", caregiver_phone="+525511111111",
                son_name="Luis Pineda",
                critical_medication="Metformina 500mg (Diabetes)",
            )
        )
        self.assertIn("[PROVISIONED]", provision)

        # Each individual has its own baselines, distinct from Don Manuel's.
        self.assertIn("Abuelita Rosa", ABUELITOS_DB)
        self.assertEqual(
            ABUELITOS_DB["Abuelita Rosa"]["caregiver_routing"]["caregiver_phone"],
            "+525511111111",
        )

        for _ in range(3):
            self.loop.run_until_complete(
                verify_senior_routine("Abuelita Rosa", "Ya me la tome hoy mijo buenos dias", "07:00")
            )
        baselines = ABUELITOS_DB["Abuelita Rosa"]["learned_behavioral_baselines"]
        self.assertLess(baselines["avg_waking_hour"], 8.0)

    def test_provision_duplicate_is_rejected(self):
        dup = self.loop.run_until_complete(
            provision_senior(
                name="Don Manuel", age=72, city="Ecatepec",
                living_situation="Lives alone", caregiver_phone="+525512345678",
                son_name="Guillermo", critical_medication="Losartán 50mg",
            )
        )
        self.assertIn("Error", dup)
        self.assertIn("already registered", dup)

    def test_son_view_reports_baseline_and_alerts(self):
        self.loop.run_until_complete(provision_senior(
            "Abuelita Rosa", 68, "Guadalajara", "Lives alone",
            "+525511111111", "Luis Pineda", "Metformina 500mg (Diabetes)"))

        # One normal check-in + one delayed check-in that raises an alert.
        self.loop.run_until_complete(verify_senior_routine("Abuelita Rosa", "Ya me la tome", "08:00"))
        self.loop.run_until_complete(verify_senior_routine("Abuelita Rosa", "Ya me la tome", "12:00"))

        view = self.loop.run_until_complete(son_view("Abuelita Rosa"))
        self.assertIn("[SON DASHBOARD]", view)
        self.assertIn("Abuelita Rosa", view)
        self.assertIn("Luis Pineda", view)
        self.assertIn("Check-ins logged: 2", view)
        self.assertIn("Alerts dispatched: 1", view)

    def test_son_view_unknown_user(self):
        view = self.loop.run_until_complete(son_view("Stranger"))
        self.assertIn("Error", view)

    def test_behavioral_alert_is_not_routine_ok(self):
        """A habit-shift alert must reach the son's feed as ELEVATED_QoS, not ROUTINE_OK."""
        self.loop.run_until_complete(verify_senior_routine("Don Manuel", "Ya me la tome", "08:00"))
        self.loop.run_until_complete(verify_senior_routine("Don Manuel", "Ya me la tome", "12:00"))
        last = caregiver_notifier.notification_log[-1]
        self.assertEqual(last["status"], "⚠️ BEHAVIORAL_ANOMALY")
        self.assertEqual(last["routing_priority"], "ELEVATED_QoS")

    def test_normal_check_in_does_not_alert_son(self):
        self.loop.run_until_complete(verify_senior_routine("Don Manuel", "Ya me la tome", "08:00"))
        view = self.loop.run_until_complete(son_view("Don Manuel"))
        self.assertIn("Alerts dispatched: 0", view)

    def test_state_is_persisted_and_reloadable(self):
        """Baselines + alerts survive a simulated restart from the JSON store."""
        self.loop.run_until_complete(verify_senior_routine("Don Manuel", "Ya me la tome", "08:00"))
        self.loop.run_until_complete(verify_senior_routine("Don Manuel", "Ya me la tome", "12:00"))
        persisted_hour = ABUELITOS_DB["Don Manuel"]["learned_behavioral_baselines"]["avg_waking_hour"]
        persisted_alerts = len(caregiver_notifier.alerts_for("Don Manuel"))

        # Simulate restart: fresh engine + notifier hydrate from the state file.
        reloaded_engine = ExtendedBehavioralEngine()
        reloaded_notifier = CaregiverNotificationEngine()

        self.assertIn("Don Manuel", store.profiles)
        reloaded_hour = reloaded_engine.profiles["Don Manuel"]["learned_behavioral_baselines"]["avg_waking_hour"]
        self.assertAlmostEqual(reloaded_hour, persisted_hour)
        self.assertEqual(len(reloaded_notifier.alerts_for("Don Manuel")), persisted_alerts)
        self.assertEqual(persisted_alerts, 1)

    @classmethod
    def tearDownClass(cls):
        store.clear()


if __name__ == "__main__":
    unittest.main()
