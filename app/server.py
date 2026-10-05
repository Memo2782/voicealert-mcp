# app/server.py
"""Public HTTP surface for the VoiceAlert Cloud SaaS provisioning (module 4)
and the son's dashboard (module 3).

The learning API itself stays an isolated MCP server (app.main). This FastAPI
process only re-exposes the same engine functions over HTTP so the public
provisioning page and the son dashboard can consume them over the network.
"""
import os
from typing import List

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.main import verify_senior_routine, son_view, provision_senior
from app.tools.emergency import caregiver_notifier
from app.database.mock_db import ABUELITOS_DB

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def _run(coro):
    """Run the async MCP API coroutines synchronously inside HTTP handlers."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


app = FastAPI(title="VoiceAlert Cloud", version="2.0")
app.mount("/static", StaticFiles(directory=_TEMPLATES_DIR), name="static")


@app.get("/", response_class=FileResponse)
def provisioning_page():
    return FileResponse(os.path.join(_TEMPLATES_DIR, "provisioning.html"))


@app.get("/dashboard", response_class=FileResponse)
def dashboard_page():
    return FileResponse(os.path.join(_TEMPLATES_DIR, "dashboard.html"))


@app.get("/api/son/{name}")
def get_son_view(name: str):
    view = _run(son_view(name))
    if view.startswith("Error"):
        raise HTTPException(status_code=404, detail=view)
    return JSONResponse({"name": name, "dashboard": view})


@app.post("/api/provision")
def api_provision(
    name: str = Form(...),
    age: int = Form(...),
    city: str = Form(...),
    living_situation: str = Form(...),
    caregiver_phone: str = Form(...),
    son_name: str = Form(...),
    critical_medication: str = Form(...),
    expected_intake_window: str = Form("08:00 AM - 09:30 AM"),
    max_allowed_delay_hours: float = Form(2.5),
    speech_drop_percentage: float = Form(0.40),
):
    result = _run(
        provision_senior(
            name=name, age=age, city=city, living_situation=living_situation,
            caregiver_phone=caregiver_phone, son_name=son_name,
            critical_medication=critical_medication,
            expected_intake_window=expected_intake_window,
            max_allowed_delay_hours=max_allowed_delay_hours,
            speech_drop_percentage=speech_drop_percentage,
        )
    )
    if result.startswith("Error"):
        raise HTTPException(status_code=409, detail=result)
    return JSONResponse({"result": result, "profile": ABUELITOS_DB.get(name)})


@app.post("/api/checkin")
def api_checkin(name: str = Form(...), voice_text: str = Form(...), current_time: str = Form("08:30")):
    result = _run(verify_senior_routine(name, voice_text, current_time))
    return JSONResponse({"result": result})


if __name__ == "__main__":
    # uvicorn app.server:app --host 0.0.0.0 --port 8000
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
