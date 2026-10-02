# app/main.py
import unicodedata
from mcp.server.mcpserver import MCPServer
from app.database.mock_db import ABUELITOS_DB
from app.tools.emergency import caregiver_notifier
from app.core.behavioral_ai import behavioral_ai_engine  # Linking Behavioral AI

mcp = MCPServer("VoiceAlert-MX")

def normalize_text(text: str) -> str:
    """Removes accents, converts to lowercase, and strips white spaces."""
    text_normalized = unicodedata.normalize('NFD', text)
    clean_text = "".join(c for c in text_normalized if unicodedata.category(c) != 'Mn')
    return clean_text.lower().strip()

@mcp.tool()
async def verify_senior_routine(name: str, voice_text: str, current_time: str = "08:30") -> str:
    """
    Primary Function: Processes check-ins, normalizes text, analyzes behavioral habits,
    and updates caregiver telemetry when anomalies occur.
    """
    senior = ABUELITOS_DB.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert."
    
    clean_input = normalize_text(voice_text)
    caregiver_phone = senior["caregiver_phone"]
    word_count = len(voice_text.split())
    
    # 1. RUN BEHAVIORAL LEARNING LOOP
    # Score the check-in against the already-learned profile FIRST, then fold this
    # check-in in. Learning first would let a late or terse message drag the baseline
    # toward itself and mask the very anomaly it should raise.
    analysis = behavioral_ai_engine.analyze_vocal_anomaly(name, voice_text, current_time)
    profile = behavioral_ai_engine.learn_checkin_baseline(name, current_time, word_count)

    # 2. EMERGENCY TRIGGER FILTER
    danger_keywords = ["me cai", "me siento mal", "duele", "accidente", "ambulancia", "no me puedo mover"]
    if any(keyword in clean_input for keyword in danger_keywords):
        await caregiver_notifier.trigger_caregiver_alert(
            senior_name=name,
            alert_type="CRITICAL",
            raw_message=voice_text,
            destination_phone=caregiver_phone
        )
        return f"[🚨 CRITICAL EMERGENCY] Caregiver notified at {caregiver_phone}. Core system activated."

    # 3. BEHAVIORAL ANOMALY FILTER
    if analysis["is_behavioral_anomaly"]:
        # Alert the caregiver about a shift in habits, not an immediate crash
        await caregiver_notifier.trigger_caregiver_alert(
            senior_name=name,
            alert_type="ROUTINE_ANOMALY",
            raw_message=f"Behavior Shift Detected: {analysis['reason']}",
            destination_phone=caregiver_phone
        )
        return f"[⚠️ BEHAVIORAL ALERT] Habit anomaly found: {analysis['reason']} Caregiver dashboard updated."

    # 4. STANDARD MEDICATION CHECK-IN
    medication_keywords = ["pastilla", "medicina", "ya me la tome", "check in", "ya quedo"]
    if any(keyword in clean_input for keyword in medication_keywords):
        expected_hour = round(profile["expected_checkin_hour"], 1)
        return f"[SUCCESS] Routine logged: {name} confirmed taking their medication: {senior['medication']}. Expected check-in hour is learned at {expected_hour}."
        
    return f"[TRACKING] Routine data entry saved for {name}."

if __name__ == "__main__":
    mcp.run()
