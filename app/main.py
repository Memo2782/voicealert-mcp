# app/main.py
import unicodedata
from mcp.server.mcpserver import MCPServer
from app.database.mock_db import ABUELITOS_DB
from app.tools.emergency import caregiver_notifier  # Linking the caregiver engine

mcp = MCPServer("VoiceAlert-MX")

def normalize_text(text: str) -> str:
    """Removes accents, converts to lowercase, and strips white spaces."""
    text_normalized = unicodedata.normalize('NFD', text)
    clean_text = "".join(c for c in text_normalized if unicodedata.category(c) != 'Mn')
    return clean_text.lower().strip()

@mcp.tool()
async def verify_senior_routine(name: str, voice_text: str) -> str:
    """
    Primary Function: Receives WhatsApp text, normalizes conversational data,
    evaluates emergency states, and routes real-time telemetry to the caregiver.
    """
    senior = ABUELITOS_DB.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."
    
    clean_input = normalize_text(voice_text)
    caregiver_phone = senior["caregiver_phone"]
    
    # 1. CRITICAL EMERGENCY FILTER (Mexico Context Keywords)
    danger_keywords = ["me cai", "me siento mal", "duele", "accidente", "ambulancia", "no me puedo mover"]
    
    if any(keyword in clean_input for keyword in danger_keywords):
        # Trigger High Priority Emergency Telemetry Alert to the Son/Daughter
        await caregiver_notifier.trigger_caregiver_alert(
            senior_name=name,
            alert_type="CRITICAL",
            raw_message=voice_text,
            destination_phone=caregiver_phone
        )
        return f"[🚨 CRITICAL EMERGENCY] Caregiver has been alerted at {caregiver_phone}. Critical support pipelines open."

    # 2. STANDARD ROUTINE PIECE (Medication Validation Check)
    medication_keywords = ["pastilla", "medicina", "ya me la tome", "check in", "ya quedo"]
    
    if any(keyword in clean_input for keyword in medication_keywords):
        # Trigger Standard Dashboard Update to the Son/Daughter
        await caregiver_notifier.trigger_caregiver_alert(
            senior_name=name,
            alert_type="ROUTINE",
            raw_message=f"Medication confirmed: {senior['medication']}",
            destination_phone=caregiver_phone
        )
        return f"[SUCCESS] Routine logged: {name} confirmed taking their medication: {senior['medication']}."
        
    return f"[TRACKING] Routine data entry saved for {name}: '{voice_text}'. Status: Active."

if __name__ == "__main__":
    mcp.run()
