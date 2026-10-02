import unittest
import asyncio
from app.main import verify_senior_routine, normalize_text
from app.tools.emergency import caregiver_notifier

class TestVoiceAlertPipeline(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def test_text_normalization(self):
        input_text = "Ya me la tomé, Don Manuel"
        expected_output = "ya me la tome, don manuel"
        self.assertEqual(normalize_text(input_text), expected_output)

    def test_routine_success_with_accents(self):
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Ya me la tome")
        )
        self.assertIn("[SUCCESS]", result)

    def test_emergency_trigger_logic(self):
        result = self.loop.run_until_complete(
            verify_senior_routine("Don Manuel", "Me caí y me duele mucho")
        )
        self.assertIn("[🚨 CRITICAL EMERGENCY]", result)

if __name__ == "__main__":
    unittest.main()
