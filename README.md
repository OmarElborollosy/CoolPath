# CoolPath — Autonomous Multi-Agent Microclimate Risk Intelligence

CoolPath is an autonomous multi-agent platform designed to protect delivery riders and outdoor workers during extreme heat events in Phoenix, Arizona.

It pairs **FortyGuard’s tOS Enterprise thermal intelligence API** (heatmaps, point environmental parameters, satellite land-cover, and street-view shade segmentation) with a **two-speed multi-agent architecture**  

---

## Key Highlights & Scientific Rules

1. **Two-Speed Architecture**:
   - **Slow Path (Background Worker)**: Periodically refreshes and pre-warms FortyGuard heatmaps (`tcm`, `persistence`, `exceedance`), satellite canopy, and street shade into a `LayeredCache` (Redis + In-Memory fallback).
   - **Fast Path (Live Dispatch)**: Evaluates live rider GPS pings against spatial cache in $< 10$ ms.
2. **OSHA-Grounded 4-Factor Thermal Risk Formula**:
   $$\text{Thermal Risk} = 0.35 \times \text{NormHeatIndex} + 0.30 \times \text{NormPersistence} + 0.20 \times \text{NormSolar} + 0.15 \times \text{NormAQI}$$
   - **Fully Live Data**: Thermal Risk Scoring runs on fully live FortyGuard data (`env_params` + `heatmap`).
   - **Low** ($< 0.35$): Normal monitoring
   - **Moderate** ($0.35 - 0.54$): Hydration & rest advisory
   - **High** ($0.55 - 0.74$): Triggers Reroute Agent
   - **Critical** ($\ge 0.75$): Triggers Mandatory Cooling Stop Alert
3. **Micro-Refuge Cascade (300m $\rightarrow$ 1km $\rightarrow$ 3km $\rightarrow$ Mandatory Stop)**:
   - Evaluates cooling points across hyper-local radii with corridor polyline sampling (every ~175m) and clamped `Refuge Score` ($[0.0, 1.0]$).
   - **Data Transparency & Honesty**: Refuge Score's shade-quality inputs are currently affected by a FortyGuard Premium-tier platform outage on `satellite_segmentation`/`street_view_segmentation`. This degraded condition is correctly reflected via our `is_synthesized: true` transparency flag rather than hidden, demonstrating the system's honesty mechanism working under real degraded conditions.
4. **Phoenix 6-Rider Fleet Simulation (2026-08-03)**:
   - **R3**: Lingering in Van Buren Corridor $\rightarrow$ Critical Alert fires.
   - **R6**: Enters danger corridor $\rightarrow$ Reroute Agent redirects through shaded canopy corridor to Encanto Park ($\Delta T = -4.2^\circ$C).

---

## Running the API & Tests

### 1. Install dependencies
```bash
cd coolpath
pip install -r requirements.txt
```

### 2. Run the test suite
```bash
pytest
```

### 3. Start the FastAPI server
```bash
uvicorn app.api.server:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Fleet Status: `http://localhost:8000/api/fleet/status`
- Phoenix AOIs: `http://localhost:8000/api/aois`
