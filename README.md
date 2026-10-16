# GridPulse — Distribution Transformer Digital Twin



> **Current Implementation State:** Phases 1–8 Implemented, Evaluated, and Integrated (**PASS**).  
> Both CPRI v3.0.2 Baseline (8 assets) and GridPulse Synthetic v1.0.0 Candidate (`DT-01` Promoted; `DT-02`..`04` Gated) are operational with dynamic switching and reliable fallback.  
> **Key References:**
> - Master Execution Plan: [`GRIDPULSE_MASTER_EXECUTION_PLAN.md`](GRIDPULSE_MASTER_EXECUTION_PLAN.md)
> - Extra Domains & Candidate Scope: [`GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md`](GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md)
> - Technical References & Bibliography: [`docs/references/TECHNICAL_REFERENCES_AND_CITATIONS.md`](docs/references/TECHNICAL_REFERENCES_AND_CITATIONS.md)
> - Execution & Verification Log: [`docs/execution/GRIDPULSE_EXECUTION_LOG.md`](docs/execution/GRIDPULSE_EXECUTION_LOG.md)

---

## ⚡ Project Overview

GridPulse is a physics-grounded, stateful real-time condition monitoring and predictive maintenance digital twin engineered specifically for medium- and low-voltage distribution assets. Unlike black-box machine learning approaches that overclaim remaining useful life without physical validation, GridPulse combines deterministic physical principles with robust statistical anomaly detection, conformal uncertainty estimation, and construction-aware operational capability gating.

<img width="1600" height="815" alt="WhatsApp Image 2026-10-16 at 10 03 08" src="https://github.com/user-attachments/assets/36ec7b82-23f3-4195-a919-f6af5e30b781" />



The core twin tracks transformer telemetry in continuous time using a first-order grey-box thermal differential equation (IEC 60076-7 / IEEE C57.91) coupled with multi-domain electrical, oil-level, tank pressure, and protection analysis. It processes active/reactive power, line currents, line-to-neutral voltages, winding temperatures, ambient conditions, conservator oil level, sealed-tank gauge pressure, and protection trip contacts to maintain a strictly synchronized, replayable state vector. Every state update produces a cryptographically hashed FactBundle ensuring complete auditability and provenance.

<img width="1600" height="815" alt="WhatsApp Image 2026-10-16 at 10 03 08 (1)" src="https://github.com/user-attachments/assets/091d7052-71fa-4174-94e9-1af15eb1260e" />


Operational health is evaluated across five independent diagnostic domains: **Thermal**, **Electrical**, **Insulation**, **Mechanical**, and **Oil/Protection Status**. The system computes a bounded Operational Transformer Health Index (OTHI) on a 0–100 scale, dynamically gating domain weights based on telemetry freshness, asset construction (conservator vs sealed corrugated tank), and sensor reliability.

---

## 🎨 Interactive 3D Digital Twin & CAD Disassembly

GridPulse includes an interactive WebGL/Three.js digital twin visualization engineered for substation engineers and operators:

- **CAD Exploded-View Disassembly**: Interactive disassembly slider with smooth animated explosion along calibrated 3D radial vectors. Separates high-voltage and low-voltage bushings, main corrugated tank, radiator fin banks, conservator tank, Buchholz relay piping, and internal core & windings.
- **Auto-Framing Camera & Responsive Canvas**: Automated 3D bounding-box calculation dynamically adjusts the camera frustum and target center to keep all disassembled components in frame at any zoom or explosion level.
- **Authentic ANSI Utility Aesthetics**:
  - Main Tank & Conservator: Standard **ANSI 70 / ANSI 61 Substation Steel Gray** (`#64707d`).
  - Radiator Fin Banks: Differentiated cooling plate steel (`#54606e`).
  - Structural Stiffeners & Flanges: High-contrast structural steel (`#3d4550`).
  - Bushings & Terminals: Terracotta glazed electrical porcelain (`#733822`), natural copper buswork (`#c86a3b`), and machined brass terminals (`#cfa036`).
  - **Satin-Matte Industrial Finish**: Tuned roughness (`0.44`) and metalness (`0.16`) avoiding plastic high-gloss/chrome shine.
  - Multi-Point Studio Lighting: Directional key, soft fill, rim, and ground bounce lighting for crisp depth and contour visibility.
- **Low-Profile Micro-Tag HUD**: Compact, non-occluding pill callout badge showing live component status, sensor readings, quick navigation links (`details →`), and instant dismissal without obstructing 3D geometry.
- **Workspace Optimization**: Collapsible left navigation sidebar maximizing viewport real estate for detailed 3D inspection.

<img width="1600" height="814" alt="WhatsApp Image 2026-10-16 at 10 03 08 (2)" src="https://github.com/user-attachments/assets/f8e4a66c-5056-4eab-b74b-82e4d2d70d5f" />

---

## 🏗️ Architecture & Pipeline

The end-to-end processing pipeline operates deterministically from raw telemetry ingestion to formal compliance reporting:

```text
Source (SCADA / IoT Telemetry / CSV / Parquet)
   ↓
Canonical Telemetry (Pydantic schema validation & explicit UCUM unit normalization)
   ↓
Validation (Deduplication, timestamp monotonicity, rate-of-change & stuck-gauge plausibility)
   ↓
Features (Symmetrical components, THD, unbalance ratios, prospective I_sc, rolling slopes)
   ↓
Stateful Twin (Deterministic state reducer F(State_{t-1}, Event_t) -> State_t)
   ↓
Thermal / Electrical / Pressure Analysis (Grey-box ODE, conformal bounds, tank limits)
   ↓
Anomaly / Evidence (Multi-domain CUSUM/Z-score detectors, evidence episodes)
   ↓
Capability Gating (Construction-aware enabling of oil vs pressure vs thermal tiers)
   ↓
OTHI (Gated Multi-Domain Operational Transformer Health Index [0–100])
   ↓
Maintenance (Deterministic rule policy, priority ranking P0–P3, action windows)
   ↓
Reports (Deterministic JSON, CSV, and WeasyPrint PDF audit reports)
```

---

## 🚀 Quick Start

### 1. Single-Command Deployment (Recommended)

Start the full system (Backend API on `:8000` and Frontend UI on `:3000`) using Docker Compose:

```bash
docker compose up --build
```

Verify backend readiness:

```bash
curl http://localhost:8000/healthz
```

Access the interfaces:
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check:** [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 2. Local Development Setup

#### Backend (FastAPI + Python 3.11+)

```bash
cd backend
pip install -e ".[dev]"

# Run FastAPI backend server (default asset: CPRI TX_1000_COMM)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or run with another asset
DEFAULT_ASSET_ID=DT-01 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend dynamically supports both datasets and all 12 assets with interactive switching in the UI ReplayBar:
- **CPRI Synthetic Benchmark v3.0.2 (Baseline):** 8 assets (`TX_1000_COMM` PROMOTED; 7 assets run in descriptive/shadow mode).
- **GridPulse Synthetic v1.0.0 (Candidate):** 4 assets (`DT-01` PROMOTED; `DT-02` through `DT-04` run in descriptive mode).

#### Frontend (React + Vite + Three.js)

```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Demo Script

Execute the end-to-end 7-stage automated demonstration script:

```bash
# Via Docker:
docker compose exec backend python /app/demo_script.py

# Or locally:
python demo_script.py
```

The script executes 7 deterministic verification stages:
1. **Baseline Telemetry Replay:** Nominal state tracking and storage ingestion.
2. **Sensor Quality Event:** High-gradient current spike detection and plausibility gating.
3. **Sustained Overload Excursion:** 140% loading event, evidence accumulation, and health impact.
4. **Multi-Domain Corroboration:** Cross-domain evidence fusion and OTHI gating.
5. **What-If Scenario Simulation:** Qualification gating on unpromoted thermal models.
6. **Operator Feedback:** Human-in-the-loop acknowledgement recorded in an immutable ledger.
7. **Audit PDF Export:** Deterministic WeasyPrint / xhtml2pdf audit report generation.

---

## 📡 REST API Reference

Mounted under `/v1` (with `/healthz` at root):

| Endpoint | Method | Description |
|---|---|---|
| `/healthz` | `GET` | System liveness probe and subsystem readiness diagnostics |
| `/v1/assets` | `GET` | Multi-dataset catalog (available datasets, ratings, tank types, active asset) |
| `/v1/telemetry/frame` | `POST` | Ingest raw SCADA frame and advance state |
| `/v1/telemetry/canonical` | `POST` | Ingest canonical telemetry event |
| `/v1/replay` | `GET` | Current deterministic chronological replay status and position |
| `/v1/replay` | `POST` | Control replay playback (`start`, `pause`, `resume`, `step`, `reset`, `seek`, `asset_id`, `dataset_id`) |
| `/v1/assets/{asset_id}/state` | `GET` | Current digital twin state vector, telemetry, and FactBundle |
| `/v1/assets/{asset_id}/history` | `GET` | Temporal query of historical state trajectory |
| `/v1/assets/{asset_id}/capabilities`| `GET` | Active C0–C4 capability tier manifest with disabled reasons |
| `/v1/analytics/othi` | `GET` | Multi-domain OTHI score, sub-indices, and gating status |
| `/v1/analytics/anomalies` | `GET` | Active and historical anomaly evidence episodes |
| `/v1/analytics/maintenance` | `GET` | Prioritized maintenance recommendations (P0–P3) |
| `/v1/analytics/model-card` | `GET` | Grey-box thermal model parameters and qualification tier |
| `/v1/models/cpri-evaluation` | `GET` | CPRI baseline model evaluation matrix and gate outcomes (8 assets) |
| `/v1/models/candidate-evaluation` | `GET` | GridPulse candidate evaluation matrix and gate outcomes (4 assets) |
| `/v1/scenarios/what-if` | `POST` | Bounded 2-hour forward scenario simulation |
| `/v1/feedback/ledger` | `GET` | Immutable operator action and resolution ledger |
| `/v1/feedback/acknowledge` | `POST` | Record human operator feedback (ACK, DISMISS, RESOLVE, OVERRIDE) |
| `/v1/reports/compliance` | `GET` | Structured machine-readable compliance report (JSON/CSV) |
| `/v1/reports/pdf` | `GET` | Formal engineering audit PDF report (WeasyPrint / xhtml2pdf fallback) |

---

## 🛡️ Engineering Honesty & Safety Guarantees

GridPulse adheres to strict physical and ethical boundaries:

1. **No RUL Overclaiming:** The system does **not** estimate whole-life Remaining Useful Life (RUL) in hours or years without verified multi-year degradation datasets and dissolved gas analysis (DGA).
2. **No Arbitrary Failure Probability Claims:** Arbitrary statistical failure percentages (e.g. "94.2% chance of failure") are rejected in favor of empirical conformal confidence intervals and multi-domain evidence corroboration.
3. **No Autonomous Switching Control:** The twin operates strictly as a decision-support advisory system; autonomous breaker or tap-changer commands are prohibited.
4. **Insulation Ageing Gating:** Arrhenius/IEEE C57.91 thermal life consumption calculations remain disabled (`C4_THERMAL_INSULATION_LIFETIME = False`) unless verified paper insulation class and calibrated hotspot temperatures exist.
5. **No Waveform Reconstruction:** 30-minute SCADA telemetry cannot reconstruct sub-cycle short-circuit waveforms or peak asymmetry. Symmetrical short-circuit values are reported solely as prospective reference indicators.
6. **No Spontaneous Oil Recovery:** Telemetry oil-level slope does not prove a physical leak; it emits advisory `MNT-OIL-008` triggering physical visual inspection.

---

## 📊 Verification & Test Suite

All capabilities are verified with deterministic automated test suites:

```bash
# Run full backend test suite
pytest backend/tests/ -v

# Run targeted suites
pytest backend/tests/test_phase7_cutover_and_fallback.py -v
pytest backend/tests/test_candidate_adaptation_and_extra_domains.py -v
pytest backend/tests/test_stabilization_fixes.py -v

# Verify frontend build
cd frontend && npm run build
```

| Verification Scope | Pass Count | Status |
|---|:---:|:---:|
| **Comprehensive Backend Test Suite** | **586 / 586 Tests** | **PASS** |
| **Phase 7 Cutover & Fallback** | 6 / 6 Tests | **PASS** |
| **Candidate Adaptation & Extra Domains** | 24 / 24 Tests | **PASS** |
| **Backend Stabilization Fixes** | 9 / 9 Tests | **PASS** |
| **Frontend Production Build** (`tsc && vite build`) | Clean (0 errors) | **PASS** |
| **Docker Compose Live Integration** | All endpoints healthy (200) | **PASS** |
