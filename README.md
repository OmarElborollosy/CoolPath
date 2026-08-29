# 🥵 CoolPath

**Autonomous heat-safety agents for outdoor delivery workers — powered by FortyGuard's hyperlocal Temperature Intelligence.**

Built for the FortyGuard Global AI Hackathon — Agentic AI Track

---

## The Problem

Every summer, delivery riders spend hours outside in cities where street-level heat regularly exceeds 110–120°F. The only thing protecting them today is a generic weather number on a phone — reactive, city-wide, and easy to ignore. Heat stroke doesn't happen because no data existed. It happens because nobody was watching that data closely enough, in real time, for the one person standing outside in it.

## What CoolPath Does

CoolPath is a network of autonomous AI agents that continuously monitor hyperlocal heat conditions along active delivery routes and **act on their own** — without a human checking a dashboard — to protect riders before heat becomes dangerous.

- 🌡️ **Perceives** real, street-level temperature, heat index, solar irradiance, and air quality via FortyGuard's Temperature API
- ⚠️ **Scores risk** using an OSHA-grounded formula that weighs *how hot* and *how long*, not just a single snapshot
- 🗺️ **Reroutes autonomously** to the nearest genuinely shaded refuge, verified with real canopy and street-shade data — not assumptions
- 🚨 **Escalates automatically** to a mandatory-stop alert when no safe refuge exists nearby
- 📋 **Explains every decision** in plain language, grounded in the exact sensor data and safety standard behind it

No human intervention required. The system watches, decides, and acts.

---

## Why This Is Different

A car's thermometer tells you it's hot right now, where the vehicle is. It can't tell you a zone has been dangerously hot for the last 40 minutes, can't compare your route against a cooler alternative, and can't act. CoolPath closes exactly that gap — from *sensing* to *deciding* to *acting*, autonomously.

---

## Architecture

CoolPath runs a **two-speed system**, so every live safety decision is instant even though the underlying heat data is expensive to compute:
SLOW PATH (background, every ~15 min) FAST PATH (live, <10ms)
───────────────────────────────────── ────────────────────────
FortyGuard API (heatmap, env_params, → Rider GPS event
satellite + street-view segmentation) → Decision Coordinator
→ Cache (Redis + in-memory fallback) → Risk Scoring Agent
→ Reroute / Alert Agent
→ Explanation Agent


**Six specialist agents**, orchestrated by a dynamic decision coordinator:

| Agent | Role |
|---|---|
| Heat Perception | Reads live/cached hyperlocal thermal data for a rider's exact position |
| Risk Scoring | Computes an OSHA-grounded 4-factor Thermal Risk Score |
| Decision Coordinator | Routes to Reroute or Alert agents based on real-time risk thresholds |
| Reroute | Finds and scores the nearest genuinely shaded refuge via a tiered spatial cascade |
| Alert Automation | Fires tiered Advisory / Warning / Critical Mandatory-Stop alerts |
| Explanation | Generates a plain-language safety briefing grounded in the real sensor data behind each decision |

### Core Formulas

**Thermal Risk Score** (drives every autonomous decision):
Risk = 0.35·NormHeatIndex + 0.30·NormPersistence + 0.20·NormSolar + 0.15·NormAQI


**Refuge Score** (ranks candidate shaded routes, clamped to [0,1]):
Score = 0.40·(1 − NormTemp) + 0.35·Canopy% + 0.25·StreetShade% − 0.20·(Detour/3km)


---

## Built With

- **[FortyGuard Temperature API](https://fortyguard.com)** — hyperlocal thermal heatmaps, environmental parameters, satellite canopy and street-view shade segmentation
- **FastAPI** + **WebSockets** — real-time backend and live dashboard streaming
- **LangGraph** — multi-agent orchestration
- **Leaflet** + **OpenStreetMap** — live fleet visualization
- **Redis** — layered caching for sub-10ms decision latency
- **Python**, **Pydantic**, **APScheduler**

---

## Running Locally

```bash
git clone https://github.com/<your-org>/coolpath.git
cd coolpath
pip install -r requirements.txt
cp .env.example .env   # add your FortyGuard API key
uvicorn app.api.server:app --reload
```

Open `http://localhost:8000` for the live fleet dashboard.

---

## Data Transparency

Every data point CoolPath reports carries an explicit `is_synthesized` flag, showing whether it came from a live FortyGuard call or a graceful fallback. We believe an autonomous safety system should never quietly guess — if live data isn't available, the system says so.

---

## Team

Built by [Omar Elborollosy] and [Ahmed Sami] for the FortyGuard Global AI Hackathon.

## Acknowledgments

Huge thanks to **FortyGuard** for providing the Temperature API and hyperlocal heat intelligence that makes CoolPath possible, and for hosting the Global AI Hackathon.
