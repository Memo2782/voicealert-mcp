# app/server.py
"""Public HTTP surface for VoiceAlert Cloud (modules 1-4) over a real DB.

Run locally:
    python -m uvicorn app.server:app --host 0.0.0.0 --port 8000
Then:
    GET  /                     -> provisioning page (commercial offer + signup form)
    GET  /dashboard            -> son monitoring dashboard
    POST /api/provision        -> onboard a senior (form/JSON)
    POST /api/subscribe        -> phone-based subscription (module 4 'by phone')
    POST /api/checkin          -> route a voice note through the learning API
    GET  /api/son/{name}       -> learned baseline + recent alerts
"""
import asyncio
import os
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.core.service import get_service
from app.storage.db import DEFAULT_MEDICATION_WINDOW

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


app = FastAPI(title="VoiceAlert Cloud", version="2.0")


@app.get("/", response_class=FileResponse)
def provisioning_page():
    return FileResponse(os.path.join(_TEMPLATES_DIR, "provisioning.html"))


@app.get("/dashboard", response_class=FileResponse)
def dashboard_page():
    return FileResponse(os.path.join(_TEMPLATES_DIR, "dashboard.html"))


@app.get("/api/son/{name}")
def get_son_view(name: str):
    senior = get_service().backend.get_senior(name)
    if senior is None:
        raise HTTPException(status_code=404, detail=f"Senior '{name}' not found")
    return JSONResponse({"name": name, "dashboard": get_service().son_view(name)})


@app.post("/api/provision")
def api_provision(
    name: str = Form(...),
    age: int = Form(...),
    city: str = Form(...),
    living_situation: str = Form(...),
    caregiver_phone: str = Form(...),
    son_name: str = Form(...),
    critical_medication: str = Form(...),
    expected_intake_window: str = Form(DEFAULT_MEDICATION_WINDOW),
):
    result = get_service().provision_senior(
        name, age, city, living_situation, caregiver_phone, son_name,
        critical_medication, expected_intake_window,
    )
    if result.startswith("Error"):
        raise HTTPException(status_code=409, detail=result)
    return JSONResponse({"result": result})


@app.post("/api/subscribe")
def api_subscribe(phone: str = Form(...), name: str = Form(None), tier: str = Form("TIER_1_TRIAL"),
                  son_name: str = Form(None), caregiver_phone: str = Form(None)):
    record = get_service().subscribe(phone, name=name, tier=tier, son_name=son_name, caregiver_phone=caregiver_phone)
    return JSONResponse({"result": "[SUBSCRIBED] Phone-based provisioning recorded.", "subscription": record})


@app.post("/api/checkin")
def api_checkin(name: str = Form(...), voice_text: str = Form(...), current_time: str = Form("08:30")):
    svc = get_service()
    if svc.backend.get_senior(name) is None:
        raise HTTPException(status_code=404, detail=f"Senior '{name}' not found")
    result = _run(svc.process_checkin(name, voice_text, current_time))
    return JSONResponse({"result": result})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
