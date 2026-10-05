# VoiceAlert Cloud MCP Server (v2.0)

**VoiceAlert** is an automated Cloud Software-as-a-Service (SaaS) platform that converts zero-friction elderly voice interfaces—such as everyday WhatsApp voice notes—into predictive health tracking metrics. Utilizing the modern **Model Context Protocol (MCP) v2.0**, VoiceAlert processes natural conversational data, automatically learns senior habits over time in real time, and securely routes real-time alert logs to family members and sitters when behavioral anomalies or emergencies occur.

---

## 📂 System Directory Tree

The application follows a highly scalable, decoupled cloud architecture layout:

```text
voicealert-mcp/
├── .github/
│   └── workflows/          # Automated Cloud Testing CI/CD (GitHub Actions)
├── app/
│   ├── main.py             # Central Entry Point - MCP v2.0 Server Core Brain (the learning API)
│   ├── server.py           # Public HTTP surface for provisioning + the son dashboard
│   ├── core/
│   │   ├── config.py       # Safe .env variable parser & security controller
│   │   ├── persistence.py  # JSON-backed per-senior baseline + alert history
│   │   └── behavioral_ai.py# Real-time Moving Average Behavioral Analytics AI Engine
│   ├── database/
│   │   └── mock_db.py      # Low-overhead structured patient & user profile schema
│   ├── tools/
│   │   └── emergency.py    # Caregiver cloud notification channels & webhook routers
│   └── templates/
│       ├── provisioning.html # Public commercial-offer / senior signup page
│       └── dashboard.html    # Son/caregiver monitoring dashboard
├── tests/
│   └── test_mcp.py         # Automated multi-day behavior simulation testing suite
├── .env                    # Local runtime hidden keys (Ignored by Git)
├── .gitignore              # Defines file exclusions from global cloud syncing
└── README.md               # Technical Blueprint and System documentation
```

The four modules map to: (1) the MCP API in `app/main.py`, (2) the per-individual
old-man tracker in `app/core/behavioral_ai.py` (+ persistence), (3) the son monitor
exposed as the `son_view` MCP tool and `/api/son/{name}` HTTP route, and (4) the
provisioning module (`provision_senior` tool + `/api/provision` + `provisioning.html`).

## Running

```bash
# Isolated MCP learning API (consumed by tracker/son clients over stdio):
python3 app/main.py

# Public HTTP provisioning + son dashboard (module 4 + 3):
python3 -m uvicorn app.server:app --host 0.0.0.0 --port 8000
# GET  /                 -> provisioning page (commercial offer)
# GET  /dashboard        -> son monitoring dashboard
# POST /api/provision    -> onboard a senior (form/JSON)
# POST /api/checkin     -> route a voice note through the MCP learning API
# GET  /api/son/{name}   -> learned baseline + recent alerts for the son
```

---

## 📡 Cloud SaaS & Multi-User Provisioning Architecture

VoiceAlert acts as a unified central API hub that can be securely deployed to cloud instances (such as AWS, Render, or Railway). It bridges the gap between older adults who don't want to use complex phone apps and caregivers who need deep data insights.

