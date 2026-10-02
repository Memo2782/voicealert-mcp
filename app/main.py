# app/main.py
import unicodedata
from mcp.server.mcpserver import MCPServer
from app.database.mock_db import ABUELITOS_DB
from app.tools.emergency import caregiver_notifier
from app.core.behavioral_ai import behavioral_ai_engine

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
    """
    senior = ABUELITOS_DB.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."

    clean_input = normalize_text(voice_text)
    caregiver_phone = senior["caregiver_routing"]["caregiver_phone"]

    # 1. RUN BEHAVIORAL PATTERN ANALYSIS FIRST
    analysis = behavioral_ai_engine.analyze_behavioral_safety(name, current_time, voice_text)
    # Train the machine learning matrix with this current data point
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

if __name__ == "__main__":
    mcp.run()
