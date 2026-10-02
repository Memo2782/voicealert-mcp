# tests/test_mcp.py
import unittest
import asyncio
from app.main import verify_senior_routine, normalize_text
from app.core.behavioral_ai import behavioral_ai_engine

class TestVoiceAlertExtendedScenarios(unittest.TestCase):

    def setUp(self):
        """Resets the behavioral memory cache before every single test execution."""
        self.loop = asyncio.get_event_loop()
        behavioral_ai_engine.profiles["Don Manuel"]["learned_behavioral_baselines"] = {
            "avg_waking_hour": 8.0,
            "avg_word_count": 12.0,
            "total_logs_count": 0
        }

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
        baselines = behavioral_ai_engine.profiles["Don Manuel"]["learned_behavioral_baselines"]
        self.assertEqual(baselines["avg_waking_hour"], 8.0)

    def test_progressive_habit_adaptation(self):
        """
        SCENARIO 2: Gradual Lifestyle Shift (Dynamic Learning)
        If the senior slowly starts waking up earlier over a week, the engine
        must adapt smoothly without triggering false alarms.
        """
        # Week 1: Senior transitions from waking at 8:00 AM to 6:00 AM gradually
        hours_sequence = ["08:00", "08:00", "07:30", "07:00", "06:30", "06:00", "06:00"]
        message = "Hola mijo buenos dias ya me tome la pastilla del desayuno"
        
        for daily_hour in hours_sequence:
            result = self.loop.run_until_complete(
                verify_senior_routine("Don Manuel", message, daily_hour)
            )
            # Ensure a gradual change NEVER triggers a false alarm delay block
            self.assertNotIn("[⚠️ BEHAVIORAL WARNING]", result)

        # Confirm the baseline successfully adapted to the new habit curve
        baselines = behavioral_ai_engine.profiles["Don Manuel"]["learned_behavioral_baselines"]
        self.assertLess(baselines["avg_waking_hour"], 8.0)

    def test_vocal_lethargy_and_recovery_loop(self):
        """
        SCENARIO 3: Cognitive Fatigue followed by Recovery Flow
        Tests that an abrupt drop in word count triggers an alert, but if 
        the senior recovers and speaks normally again, the alert clears.
        """
        # Train baseline with long inputs
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
        
        baselines = behavioral_ai_engine.profiles["Don Manuel"]["learned_behavioral_baselines"]
        self.assertTrue(baselines["avg_word_count"] > 0)

if __name__ == "__main__":
    unittest.main()
