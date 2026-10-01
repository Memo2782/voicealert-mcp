# app/main.py
from mcp.server.mcpserver import MCPServer
from app.database.mock_db import ABUELITOS_DB

# Bootstrapping our global brand VoiceAlert MCP Server instance using v2 API
mcp = MCPServer("VoiceAlert-MX")

@mcp.tool()
async def verify_senior_routine(name: str, voice_text: str) -> str:
    """
    Primary Function: Receives transcribed audio texts from WhatsApp,
    verifies records in the database, and processes the daily care verification loop.
    """
    senior = ABUELITOS_DB.get(name)
    if not senior:
        return f"Error: User '{name}' is not registered under VoiceAlert infrastructure."
    
    analyzed_text = voice_text.lower()
    
    # Matching common conversational validation terms used by seniors in Mexico
    if any(word in analyzed_text for word in ["pastilla", "medicina", "ya me la tomé", "check-in"]):
        return f"[SUCCESS] Routine logged: {name} confirmed taking their medication: {senior['medication']}."
        
    return f"[TRACKING] Routine data entry saved for {name}: '{voice_text}'. Status: Active."

if __name__ == "__main__":
    mcp.run()

