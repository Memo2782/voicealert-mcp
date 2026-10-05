# app/main.py
import unicodedata
from mcp.server.mcpserver import MCPServer
from app.database.mock_db import ABUELITOS_DB
from app.tools.emergency import caregiver_notifier
from app.core.behavioral_ai import behavioral_ai_engine, _DEFAULT_BASELINE, _DEFAULT_THRESHOLDS
from app.core.persistence import store

mcp = MCPServer("VoiceAlert-MX")


def normalize_text(text: str) -> str:
    """Removes accents, converts to lowercase, and strips white spaces."""
    text_normalized = unicodedata.normalize('NFD', text)
    clean_text = "".join(c for c in text_normalized if unicodedata.category(c) != 'Mn')
    return clean_text.lower().strip()


@mcp.tool()
async def verify_senior_routine(name: str, voice_text: str, current_time: str = "08:30") -> str:
    """
    Primary Function: Manages conversational text feeds, screens for safety triggers,
    and uses zero-cost background analytics to log behavioral trajectories.
    The learned baseline is persisted per senior, so the tracker keeps a
    day-by-day profile of each individual across restarts.
    """
    senior = ABUELITOS_DB.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."

    clean_input = normalize_text(voice_text)
    caregiver_phone = senior["caregiver_routing"]["caregiver_phone"]

    # 1. RUN BEHAVIORAL PATTERN ANALYSIS FIRST
    # Score against already-learned history, then fold this check-in in. Learning
    # first would let a late/terse message drag the baseline toward itself.
    analysis = behavioral_ai_engine.analyze_behavioral_safety(name, current_time, voice_text)
    # Train the matrix with this current data point (persisted by the engine)
    behavioral_ai_engine.train_baseline_data(name, current_time, voice_text)

    # 2. EMERGENCY INTRINSIC KEYWORD SCREENING
    danger_keywords = ["me cai", "me siento mal", "duele", "accidente", "ambulancia"]
    if any(keyword in clean_input for keyword in danger_keywords):
        await caregiver_notifier.trigger_caregiver_alert(name, "CRITICAL", voice_text, caregiver_phone)
        return f"[🚨 CRITICAL] Emergency handling active. Caregiver notified at {caregiver_phone}."

    # 3. ADVANCED BEHAVIORAL ANOMALY FILTER
    if analysis["is_anomaly"]:
        await caregiver_notifier.trigger_caregiver_alert(
            senior_name=name,
            alert_type=analysis["type"],
            raw_message=analysis["reason"],
            destination_phone=caregiver_phone
        )
        return f"[⚠️ BEHAVIORAL WARNING] Anomaly caught: {analysis['reason']} Caregiver dashboard updated."

    # 4. STANDARD REPETITIVE MEDICATION CHECK-IN
    medication_keywords = ["pastilla", "medicina", "ya me la tome", "check in"]
    if any(keyword in clean_input for keyword in medication_keywords):
        return f"[SUCCESS] Routine logged: {name} confirmed taking medication: {senior['medical_baseline']['critical_medication']}."

    return f"[TRACKING] Data logged. Baseline patterns are stable."


@mcp.tool()
async def son_view(name: str) -> str:
    """
    Son/Caregiver read model: returns the learned baseline + recent alerts for
    one senior, so the family dashboard can monitor day-by-day behavior without
    re-running check-ins.
    """
    senior = ABUELITOS_DB.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."

    baselines = senior["learned_behavioral_baselines"]
    routing = senior["caregiver_routing"]
    alerts = caregiver_notifier.alerts_for(name)
    recent = alerts[-5:]
    lines = [
        f"[SON DASHBOARD] {name}",
        f"  Son: {routing.get('son_name', 'N/A')} | Phone: {routing.get('caregiver_phone', 'N/A')}",
        f"  Medication: {senior['medical_baseline']['critical_medication']}",
        f"  Learned wake hour: {round(baselines['avg_waking_hour'], 1)}:00 AM",
        f"  Learned avg word count: {round(baselines['avg_word_count'], 1)}",
        f"  Check-ins logged: {baselines['total_logs_count']}",
        f"  Alerts dispatched: {len(alerts)}",
    ]
    if recent:
        lines.append("  Recent alerts:")
        for a in recent:
            lines.append(f"    - [{a['status']}] {a['routing_priority']} @ {a['timestamp']}: {a['body']}")
    return "\n".join(lines)


@mcp.tool()
async def provision_senior(
    name: str,
    age: int,
    city: str,
    living_situation: str,
    caregiver_phone: str,
    son_name: str,
    critical_medication: str,
    expected_intake_window: str = "08:00 AM - 09:30 AM",
    max_allowed_delay_hours: float = 2.5,
    speech_drop_percentage: float = 0.40,
) -> str:
    """
    Provisioning API (module 4): onboards a new senior profile + caregiver
    routing and seeds their per-individual behavioral baseline. Idempotent and
    safe to call from the public provisioning page (POST /api/provision) or
    directly via the MCP tool.
    """
    if name in ABUELITOS_DB:
        return (f"Error: A senior profile for '{name}' is already registered. "
                f"Use son_view('{name}') to inspect their baseline instead.")
    ABUELITOS_DB[name] = {
        "demographics": {
            "age": age, "city": city, "living_situation": living_situation,
        },
        "caregiver_routing": {"son_name": son_name, "caregiver_phone": caregiver_phone},
        "medical_baseline": {
            "critical_medication": critical_medication,
            "expected_intake_window": expected_intake_window,
        },
        "learned_behavioral_baselines": dict(_DEFAULT_BASELINE),
        "anomaly_thresholds": {
            "max_allowed_delay_hours": max_allowed_delay_hours,
            "speech_drop_percentage": speech_drop_percentage,
        },
    }
    # Persist the new profile so it survives restarts and is learned independently.
    behavioral_ai_engine._persist()
    return (f"[PROVISIONED] Senior profile '{name}' added under VoiceAlert Cloud. "
            f"Son '{son_name}' will receive alerts at {caregiver_phone}. "
            f"Commercial offer Tier-1 (Cloud SaaS, basic monitoring) applied.")


if __name__ == "__main__":
    mcp.run()
