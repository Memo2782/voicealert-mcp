# app/core/service.py
"""DB-backed orchestration for the public HTTP surface (modules 1-4).

The MCP API in app.main stays JSON-backed by default; this service swaps in a
SQLiteBackend so provisioning, check-ins, alerts, and subscriptions are stored
in a real database that survives restarts and scales to many seniors.
"""
import os
from typing import Any, Dict, Optional

from app.storage.db import (
    SQLiteBackend, DEFAULT_MEDICATION_WINDOW, DEFAULT_DELAY_HOURS,
    DEFAULT_SPEECH_DROP,
)
from app.core.behavioral_ai import ExtendedBehavioralEngine
from app.tools.emergency import CaregiverNotificationEngine
from app.core.routing import route_checkin, build_son_view, default_profile


class VoiceAlertService:
    def __init__(self, backend: Optional[SQLiteBackend] = None) -> None:
        self.backend = backend or SQLiteBackend(":memory:")
        self.engine = ExtendedBehavioralEngine(backend=self.backend)
        self.notifier = CaregiverNotificationEngine(backend=self.backend)

    @property
    def profiles(self) -> Dict[str, Any]:
        # In-memory mirror that the engine mutates; kept in sync with the DB.
        return self.engine.profiles

    def provision_senior(
        self, name: str, age: int, city: str, living_situation: str,
        caregiver_phone: str, son_name: str, critical_medication: str,
        expected_intake_window: str = DEFAULT_MEDICATION_WINDOW,
        max_allowed_delay_hours: float = DEFAULT_DELAY_HOURS,
        speech_drop_percentage: float = DEFAULT_SPEECH_DROP,
    ) -> str:
        if self.backend.get_senior(name) is not None or name in self.profiles:
            return (f"Error: A senior profile for '{name}' is already registered. "
                    f"Use son_view('{name}') to inspect their baseline.")
        profile = default_profile(
            name, age, city, living_situation, caregiver_phone, son_name, critical_medication,
            expected_intake_window=expected_intake_window,
            baselines={"avg_waking_hour": 8.0, "avg_word_count": 12.0, "total_logs_count": 0},
            thresholds={
                "max_allowed_delay_hours": max_allowed_delay_hours,
                "speech_drop_percentage": speech_drop_percentage,
            },
        )
        # Persist the full profile, then make it visible to the in-memory engine.
        self.backend.upsert_senior(name, profile)
        self.engine.profiles[name] = profile
        return (f"[PROVISIONED] Senior profile '{name}' added under VoiceAlert Cloud. "
                f"Son '{son_name}' will receive alerts at {caregiver_phone}. "
                f"Commercial offer Tier-1 (Cloud SaaS, basic monitoring) applied.")

    async def process_checkin(self, name: str, voice_text: str, current_time: str = "08:30") -> str:
        return await route_checkin(name, voice_text, current_time, self.engine, self.notifier, self.profiles)

    def son_view(self, name: str) -> str:
        return build_son_view(name, self.profiles, self.notifier)

    def subscribe(
        self, phone: str, name: Optional[str] = None, tier: str = "TIER_1_TRIAL",
        son_name: Optional[str] = None, caregiver_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Phone-based provisioning (module 4 'by phone'). Records a subscription
        and optionally links it to a senior profile."""
        self.backend.upsert_subscription(
            phone, tier=tier, senior_name=name, son_name=son_name,
            caregiver_phone=caregiver_phone,
        )
        return {
            "phone": phone, "tier": tier, "senior_name": name,
            "son_name": son_name, "caregiver_phone": caregiver_phone,
        }

    def subscriptions(self, tier: Optional[str] = None):
        return self.backend.subscriptions(tier)


# Default file-backed instance for the HTTP server, built lazily on first use.
_default_path = os.environ.get("VA_DB_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "voicealert.db"
)

_lazy_service: Optional[VoiceAlertService] = None


def get_service() -> VoiceAlertService:
    global _lazy_service
    if _lazy_service is None:
        _lazy_service = VoiceAlertService(backend=SQLiteBackend(_default_path))
    return _lazy_service
