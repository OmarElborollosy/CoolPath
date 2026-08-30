# 🥵 CoolPath

**Autonomous heat-safety agents for outdoor delivery workers — powered by FortyGuard's hyperlocal Temperature Intelligence.**

Built for the FortyGuard Global AI Hackathon — Agentic AI Track

🔗 **Live Demo:** [https://coolpath.onrender.com/]
🎥 **Video:** [https://youtu.be/qfhL4tzNiF0] , [https://drive.google.com/file/d/1rxkTe-e2_7-14p3REPjgug6fTLqngtjA/view?usp=sharing]

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

## Running It From Scratch

### Requirements
- Python 3.11+
- A FortyGuard API key ([get one here](https://fortyguard.com))
- Redis (optional — the app runs on an in-process cache fallback if Redis isn't available, see *What Doesn't Work Yet* below)

### Setup

```bash
git clone https://github.com/<your-org>/coolpath.git
cd coolpath
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root with the following:

```env
FORTYGUARD_API_KEY=your_api_key_here
FORTYGUARD_API_BASE_URL=https://api.fortyguard.com
REDIS_URL=redis://localhost:6379/0        # optional — omit to use in-process cache
LOG_LEVEL=INFO
```

### Run

```bash
uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Confirm It's Working

1. Open `http://localhost:8000` — you should see the live fleet dashboard load with the Phoenix map
2. Within a few seconds, 6 rider markers should appear and begin moving
3. Check `http://localhost:8000/api/v1/health` — should return `{"status": "ok"}`
4. Watch the sidebar — as the simulation clock advances, rider risk scores and the Autonomous Decision Feed should update automatically

If markers don't move or the feed stays empty, check your terminal logs — most commonly this means the `FORTYGUARD_API_KEY` is missing or invalid, in which case the system will fall back to synthesized baseline data (see below) rather than fail outright.

---

## What Doesn't Work Yet

We believe in disclosing this clearly rather than letting a judge discover it unexpectedly:

- **FortyGuard Premium segmentation endpoints (`satellite_segmentation`, `street_view_segmentation`) are not used live in the current demo.** During development, these two endpoints experienced an extended outage on FortyGuard's platform side (tasks submitted successfully but never transitioned out of `processing`, even after 120+ second timeouts). We reported this to the FortyGuard team but did not receive a resolution in time for submission. As a result, our Refuge Score's canopy% and street-shade% inputs currently run on synthesized baseline estimates rather than live satellite/street-view data. **Our Thermal Risk Score — the core decision driver — is unaffected and runs on fully live FortyGuard data** (`heatmap` and `env_params` endpoints, both healthy throughout development).
- **Every data point carries an explicit `is_synthesized` flag** in the API response, so it's always possible to see, per field, whether a given number came from a live FortyGuard call or a fallback estimate. We built this transparency mechanism specifically so the system never silently guesses.
- **Redis caching has a graceful fallback, not a hard dependency.** If Redis is unavailable (as in some local dev environments), the system automatically falls back to an in-process cache. This preserves correctness but means cached data isn't shared across multiple server processes — fine for this demo's single-process deployment, not yet built for horizontal scaling.
- **Rider movement in the demo is simulated, not live GPS.** The 6-rider fleet follows precomputed, road-accurate paths (via OSRM) between fixed Phoenix waypoints on a scripted timeline (1:00 PM–4:40 PM), not real-time GPS ingestion from an actual delivery fleet. The multi-agent decision pipeline itself runs identically regardless of whether telemetry is simulated or real.
- **No production-grade authentication or multi-tenant support yet** — this is a single-fleet demo, not a deployed SaaS product.

---

## A Real FortyGuard API Request + Response

Below is an actual request/response pair from our system calling FortyGuard's `env_params` endpoint for a rider position in the Van Buren Corridor, Phoenix, AZ. API key redacted; everything else is genuine, unedited output.

**Request:**
```http
POST https://api.fortyguard.com/v1/env_params
Authorization: Bearer ***REDACTED***
Content-Type: application/json

{
  "latitude": 33.448,
  "longitude": -112.045,
  "temperature": 40.0,
  "date_time": {
    "start_date": "2026-08-03",
    "filter_type": 1,
    "start_time": "14:00"
  },
  "analysis": [
    "heat_index_celsius",
    "apparent_temperature_celsius",
    "relative_humidity_percent",
    "air_quality:idx"
  ]
}
```

**Response:**
```json
{
  "matched_tile_id": "35",
  "tile_temperature_c": 40.0,
  "heat_index_c": 37.7,
  "apparent_temperature_c": 46.1,
  "wet_bulb_c": 23.4,
  "relative_humidity_pct": 14.0,
  "solar_irradiance_ghi": 903.8,
  "aqi": 60.8,
  "persistence_hours": 1.0,
  "exceedance_hours": 1.0,
  "is_synthesized": false,
  "data_source_summary": {
    "env_params": "live_fortyguard_api",
    "heatmap_tiles": "live_fortyguard_api"
  }
}
```

This response fed directly into our Risk Scoring Agent, which computed a Thermal Risk Score of **0.39 (Moderate / OSHA Caution tier)** for this rider at this exact position and time, triggering an automatic hydration advisory.

---

## Built With

- **[FortyGuard Temperature API](https://fortyguard.com)** — hyperlocal thermal heatmaps, environmental parameters, satellite canopy and street-view shade segmentation
- **FastAPI** + **WebSockets** — real-time backend and live dashboard streaming
- **LangGraph** — multi-agent orchestration
- **Leaflet** + **OpenStreetMap** + **OSRM** — live fleet visualization with road-accurate routing
- **Redis** (with in-process fallback) — layered caching for sub-10ms decision latency
- **Python**, **Pydantic**, **APScheduler**

---

## Team

Built by [Omar Elborollosy] and [Ahmed Sami] for the FortyGuard Global AI Hackathon.

## Acknowledgments

Huge thanks to **FortyGuard** for providing the Temperature API and hyperlocal heat intelligence that makes CoolPath possible, and for hosting the Global AI Hackathon.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
