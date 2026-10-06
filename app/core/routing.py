# app/core/routing.py
"""Single source of truth for the check-in routing logic.

Both the in-process MCP API (app.main, JSON persistence) and the DB-backed
HTTP service (app.core.service, SQLite persistence) call the same functions
here so the two surfaces can never drift apart.
"""
import unicodedata
from typing import Any, Dict


def normalize_text(text: str) -> str:
    """Removes accents, converts to lowercase, and strips white spaces."""
    text_normalized = unicodedata.normalize('NFD', text)
    clean_text = "".join(c for c in text_normalized if unicodedata.category(c) != 'Mn')
    return clean_text.lower().strip()


_DANGER_KEYWORDS = ["me cai", "me siento mal", "duele", "accidente", "ambulancia"]
_MEDICATION_KEYWORDS = ["pastilla", "medicina", "ya me la tome", "check in"]


async def route_checkin(
    name: str,
    voice_text: str,
    current_time: str,
    engine: Any,
    notifier: Any,
    profiles: Dict[str, Any],
) -> str:
    """Score one check-in against the learned baseline, then persist it.

    Order matters: analyze first, then train, so a late or terse message is
    judged against history before it is folded into the baseline it would
    otherwise drag toward itself.
    """
    senior = profiles.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."

    clean_input = normalize_text(voice_text)
    caregiver_phone = senior["caregiver_routing"]["caregiver_phone"]

    # 1. BEHAVIORAL PATTERN ANALYSIS (scored, then learned)
    analysis = engine.analyze_behavioral_safety(name, current_time, voice_text)
    engine.train_baseline_data(name, current_time, voice_text)

    # 2. EMERGENCY INTRINSIC KEYWORD SCREENING
    if any(keyword in clean_input for keyword in _DANGER_KEYWORDS):
        await notifier.trigger_caregiver_alert(name, "CRITICAL", voice_text, caregiver_phone)
        return f"[🚨 CRITICAL] Emergency handling active. Caregiver notified at {caregiver_phone}."

    # 3. ADVANCED BEHAVIORAL ANOMALY FILTER
    if analysis["is_anomaly"]:
        await notifier.trigger_caregiver_alert(
            senior_name=name,
            alert_type=analysis["type"],
            raw_message=analysis["reason"],
            destination_phone=caregiver_phone,
        )
        return f"[⚠️ BEHAVIORAL WARNING] Anomaly caught: {analysis['reason']} Caregiver dashboard updated."

    # 4. STANDARD REPETITIVE MEDICATION CHECK-IN
    if any(keyword in clean_input for keyword in _MEDICATION_KEYWORDS):
        return (
            f"[SUCCESS] Routine logged: {name} confirmed taking medication: "
            f"{senior['medical_baseline']['critical_medication']}."
        )

    return "[TRACKING] Data logged. Baseline patterns are stable."


def build_son_view(name: str, profiles: Dict[str, Any], notifier: Any) -> str:
    """Son/caregiver read model: learned baseline + recent alert history."""
    senior = profiles.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."

    baselines = senior["learned_behavioral_baselines"]
    routing = senior["caregiver_routing"]
    alerts = notifier.alerts_for(name)
    lines = [
        f"[SON DASHBOARD] {name}",
        f"  Son: {routing.get('son_name', 'N/A')} | Phone: {routing.get('caregiver_phone', 'N/A')}",
        f"  Medication: {senior['medical_baseline']['critical_medication']}",
        f"  Expected intake: {senior['medical_baseline']['expected_intake_window']}",
        f"  Learned wake hour: {round(baselines['avg_waking_hour'], 1)}:00 AM",
        f"  Learned avg word count: {round(baselines['avg_word_count'], 1)}",
        f"  Check-ins logged: {baselines['total_logs_count']}",
        f"  Alerts dispatched: {len(alerts)}",
    ]
    for a in alerts[-5:]:
        lines.append(
            f"    - [{a['status']}] {a['routing_priority']} @ {a['timestamp']}: {a['body']}"
        )
    return "\n".join(lines)


def insert_senior(profiles: Dict[str, Any], engine: Any, name: str, **profile: Any) -> None:
    profiles[name] = profile
    # Make the in-memory profile immediately visible to the (DB-backed) engine.
    engine.profiles[name] = profile
    engine._persist()


def default_profile(name: str, age: int, city: str, living_situation: str,
                    caregiver_phone: str, son_name: str, critical_medication: str,
                    expected_intake_window: str = "08:00 AM - 09:30 AM",
                    baselines: Dict[str, Any] = None, thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
    return {
        "demographics": {"age": age, "city": city, "living_situation": living_situation},
        "caregiver_routing": {"son_name": son_name, "caregiver_phone": caregiver_phone},
        "medical_baseline": {
            "critical_medication": critical_medication,
            "expected_intake_window": expected_intake_window,
        },
        "learned_behavioral_baselines": baselines or {"avg_waking_hour": 8.0, "avg_word_count": 12.0, "total_logs_count": 0},
        "anomaly_thresholds": thresholds or {"max_allowed_delay_hours": 2.5, "speech_drop_percentage": 0.40},
    }


async def provision_senior(profiles: Dict[str, Any], engine: Any, name: str, age: int, city: str,
                           living_situation: str, caregiver_phone: str, son_name: str,
                           critical_medication: str, expected_intake_window: str = "08:00 AM - 09:30 AM") -> str:
    if name in profiles:
        return f"Error: A senior profile for '{name}' is already registered. Use son_view('{name}') to inspect their baseline."
    profile = default_profile(name, age, city, living_situation, caregiver_phone, son_name, critical_medication, expected_intake_window)
    insert_senior(profiles, engine, name, **profile)
    return (f"[PROVISIONED] Senior profile '{name}' added under VoiceAlert Cloud. "
            f"Son '{son_name}' will receive alerts at {caregiver_phone}. "
            f"Commercial offer Tier-1 (Cloud SaaS, basic monitoring) applied.")
