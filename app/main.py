# app/main.py
from mcp.server.mcpserver import MCPServer
from app.database.mock_db import ABUELITOS_DB
from app.tools.emergency import caregiver_notifier
from app.core.behavioral_ai import behavioral_ai_engine
from app.core.routing import (
    normalize_text,
    route_checkin,
    build_son_view,
    provision_senior as _provision_senior,
)

mcp = MCPServer("VoiceAlert-MX")


@mcp.tool()
async def verify_senior_routine(name: str, voice_text: str, current_time: str = "08:30") -> str:
    """
    Primary Function (Module 1 - MCP learning API): Manages conversational text
    feeds, screens for safety triggers, and uses zero-cost background analytics
    to log behavioral trajectories. Baselines are persisted per senior, so the
    tracker keeps a day-by-day profile of each individual across restarts.
    """
    return await route_checkin(
        name, voice_text, current_time,
        behavioral_ai_engine, caregiver_notifier, ABUELITOS_DB,
    )


@mcp.tool()
async def son_view(name: str) -> str:
    """
    Module 3 - Son monitor: returns the learned baseline + recent alerts for
    one senior so the family dashboard can inspect day-by-day behavior.
    """
    return build_son_view(name, ABUELITOS_DB, caregiver_notifier)


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
) -> str:
    """
    Module 4 - Provisioning API: onboards a new senior profile + caregiver
    routing and seeds their per-individual behavioral baseline (commercial
    offer Tier-1 applied). Idempotent.
    """
    return await _provision_senior(
        ABUELITOS_DB, behavioral_ai_engine,
        name=name, age=age, city=city, living_situation=living_situation,
        caregiver_phone=caregiver_phone, son_name=son_name,
        critical_medication=critical_medication,
        expected_intake_window=expected_intake_window,
    )


if __name__ == "__main__":
    mcp.run()
