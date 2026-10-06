# tests/test_db_pipeline.py
"""Real-DB pipeline (module 1+2+3+4) against an in-memory / file SQLite backend.

These tests deliberately bypass the in-memory JSON engine and drive the
DB-backed VoiceAlertService, so the persistence layer (baselines, alerts,
subscriptions) is exercised as a real database would persist them.
"""
import asyncio
import os
import tempfile
import unittest

from app.core.service import VoiceAlertService
from app.storage.db import SQLiteBackend


def _run(loop, coro):
    return loop.run_until_complete(coro)


class TestDBPipeline(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.service = VoiceAlertService(backend=SQLiteBackend(":memory:"))

    def test_provision_persists_senior_in_db(self):
        result = self.service.provision_senior(
            "Abuelita Rosa", 68, "Guadalajara", "Lives alone",
            "+525511111111", "Luis Pineda", "Metformina 500mg (Diabetes)",
        )
        self.assertIn("[PROVISIONED]", result)

        # The senior exists in the database, not just in memory.
        senior = self.service.backend.get_senior("Abuelita Rosa")
        self.assertIsNotNone(senior)
        self.assertEqual(senior["caregiver_routing"]["caregiver_phone"], "+525511111111")
        self.assertEqual(
            senior["medical_baseline"]["critical_medication"], "Metformina 500mg (Diabetes)"
        )
        # Baselines are seeded fresh for this individual, isolated from Don Manuel.
        self.assertEqual(senior["learned_behavioral_baselines"]["avg_waking_hour"], 8.0)
        self.assertNotIn("Don Manuel", self.service.backend.load_seniors())

    def test_day_by_day_learning_persists_to_db(self):
        self.service.provision_senior(
            "Abuelita Rosa", 68, "Guadalajara", "Lives alone",
            "+525511111111", "Luis Pineda", "Metformina 500mg (Diabetes)",
        )

        # Day 1-3: stable morning routine at 08:00
        msg = "Hola mijo ya me tome la pastilla del desayuno buenos dias"
        for _ in range(3):
            self.assertIsNotNone(_run(self.loop, self.service.process_checkin("Abuelita Rosa", msg, "08:00")))

        # Day 4: delayed to 13:00 -> must flag a behavioral anomaly
        late = _run(self.loop, self.service.process_checkin("Abuelita Rosa", "Ya me la tome", "13:00"))
        self.assertIn("[⚠️ BEHAVIORAL WARNING]", late)
        self.assertIn("Delayed Waking", late)

        # The alert was persisted to the database, not just printed.
        alerts = self.service.backend.list_alerts("Abuelita Rosa")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["status"], "⚠️ BEHAVIORAL_ANOMALY")
        self.assertEqual(alerts[0]["routing_priority"], "ELEVATED_QoS")

        # The adapted baseline is persisted and reflected in the son view.
        senior = self.service.backend.get_senior("Abuelita Rosa")
        self.assertEqual(senior["learned_behavioral_baselines"]["total_logs_count"], 4)
        view = self.service.son_view("Abuelita Rosa")
        self.assertIn("Check-ins logged: 4", view)
        self.assertIn("Alerts dispatched: 1", view)

    def test_phone_subscription_is_recorded(self):
        sub = self.service.subscribe("+525522222222", name="Abuelita Rosa", tier="TIER_1_TRIAL", son_name="Luis Pineda")
        self.assertEqual(sub["phone"], "+525522222222")
        self.assertEqual(sub["tier"], "TIER_1_TRIAL")
        recorded = self.service.backend.get_subscription("+525522222222")
        self.assertIsNotNone(recorded)
        self.assertEqual(recorded["tier"], "TIER_1_TRIAL")

    def test_baselines_and_alerts_survive_restart(self):
        # Use a real file DB so the second service instance has to open & read it.
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            first = VoiceAlertService(backend=SQLiteBackend(path))
            first.provision_senior(
                "Abuelita Rosa", 68, "Guadalajara", "Lives alone",
                "+525511111111", "Luis Pineda", "Metformina 500mg (Diabetes)",
            )
            for _ in range(3):
                _run(self.loop, first.process_checkin("Abuelita Rosa", "Yo ya me tome la pastilla hoy", "08:00"))
            _run(self.loop, first.process_checkin("Abuelita Rosa", "Ya me la tome", "13:00"))
            persisted_hour = first.backend.get_baselines("Abuelita Rosa")["avg_waking_hour"]
            self.assertEqual(first.backend.list_alerts("Abuelita Rosa").__len__(), 1)

            # Simulate restart: brand-new service loading the same DB file.
            second = VoiceAlertService(backend=SQLiteBackend(path))
            senior = second.backend.get_senior("Abuelita Rosa")
            self.assertIsNotNone(senior)
            self.assertAlmostEqual(senior["learned_behavioral_baselines"]["avg_waking_hour"], persisted_hour)
            self.assertEqual(len(second.backend.list_alerts("Abuelita Rosa")), 1)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
