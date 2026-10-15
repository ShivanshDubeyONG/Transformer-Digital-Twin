# Distribution Transformer Digital Twin — Hackathon Presentation Runbook

**Track 2: Digital Twin for Intelligent Health Monitoring and Predictive Maintenance of Distribution Transformers**  
**POWERNext-AI Hackathon 2026**

---

## 1. Pre-Presentation Checklist (15 Minutes Before Demo)

Complete this exact checklist before taking the presentation stage:

- [ ] **1. Docker Daemon Running:** Ensure Docker Desktop / Docker daemon is active on the presentation machine.
- [ ] **2. Single-Command Build & Up:**
  ```bash
  docker compose down
  docker compose up --build -d
  ```
- [ ] **3. Backend Health Check Verification:**
  ```bash
  curl -s http://localhost:8000/healthz | grep '"status":"ok"'
  ```
  *Expected Output:* `{"status":"ok", "is_ready": true, ...}`
- [ ] **4. Verify Datasets, Assets, and Model Records in Container:**
  ```bash
  docker compose exec backend ls -la /app/data/processed/cpri_v3_calibration.parquet
  curl -s http://localhost:8000/v1/assets                   # multi-dataset inventory catalog
  curl -s http://localhost:8000/v1/models/cpri-evaluation   # CPRI benchmark qualification matrix
  curl -s http://localhost:8000/v1/models/candidate-evaluation # GridPulse candidate qualification matrix
  ```
- [ ] **5. Run Demo Verification in Container:**
  ```bash
  docker compose exec backend python /app/demo_script.py
  ```
  *Ensure all 7 stages output green `PASS`.*
- [ ] **6. Verify PDF Generation Endpoint:**
  ```bash
  curl -s -o test_report.pdf http://localhost:8000/v1/reports/summary.pdf?asset_id=TX_250_MIX
  file test_report.pdf  # Or open in viewer to verify WeasyPrint rendering
  ```
- [ ] **7. Browser Dashboard Setup:**
  - Open Chrome / Edge to `http://localhost:3000`.
  - Navigate to **3D Twin** tab to confirm WebGL hardware acceleration, CAD disassembly slider, and sidebar toggle.
  - Open secondary tab to `http://localhost:8000/docs` (OpenAPI Swagger UI).
  - Open PDF viewer window with `test_report.pdf` ready for instant side-by-side inspection.

---

## 2. Scripted Synthetic-Injection Demo (`demo_script.py`, optional)

The primary live demo is the CPRI dashboard in §2b. This scripted sequence runs injected synthetic events through the same
engines (it labels its synthetic asset `DT-TRIPURA-001`; no Tripura data is used):

```
[1. Baseline] → [2. Sensor Spike] → [3. Sustained Overload] → [4. Multi-Domain Corroboration]
      ↓
[8. PDF Audit] ← [7. Operator ACK] ← [6. What-If Gating] ← [5. Health & Evidence Breakdown]
```

---

### Step 1: Baseline Telemetry Tracking & Synchronization
- **Action:** Point to the Dashboard Overview (`http://localhost:3000`) or run Stage 1.
- **System State:**
  - Asset ID: `DT-TRIPURA-001`
  - Apparent Power: Nominal ($\approx 45.2\text{ kVA}$, Relative Load Index: $0.32$)
  - OTHI Score: $100.0 / 100$ (Optimal Health)
  - Active Episodes: $0$
- **Speaker Notes:**
  > *"We begin with baseline nominal telemetry from the Tripura distribution substation. The digital twin ingest pipeline validates canonical events, performs timestamp monotonic sorting, computes symmetrical components, and synchronizes the state vector. Notice the relative load index: because nameplate rating is unverified, our twin transparently indexes against the empirical 95th percentile load rather than fabricating an ungrounded per-unit base."*

---

### Step 2: Sensor Quality Spike Detection & Plausibility Gating
- **Action:** Demonstrate single-phase current spike injection ($I_A = 480\text{ A}$ instantaneous step with unphysical gradient $\Delta I = 440\text{ A}$).
- **System State:**
  - Anomaly Detected: `SENSOR_SPIKE` in Sensor Plausibility domain.
  - Sensor Health Index: Reduced from $100.0$ to $40.0$.
  - Thermal Model Gating: Temperature estimation remains stable; the spike is flagged as uncorroborated by thermal inertia.
  - Advisory: P3 Data Review (Sensor inspection scheduled, no false breaker trip alarm).
- **Speaker Notes:**
  > *"Here we inject a single-point current spike. An un-gated machine learning model would immediately predict imminent failure or trigger a spurious trip alarm. Our twin's plausibility detector catches the unphysical rate of change ($\Delta I > 50\text{ A/s}$) with no corresponding thermal or voltage response. The sensor sub-index is penalised, but thermal estimation is shielded by physical inertia gating. Maintenance recommendation is P3: Inspect sensor calibration."*

---

### Step 3: Sustained Overload Excursion ($140\%$ Loading)
- **Action:** Advance replay to a sustained 30-minute overload injection ($S = 200.1\text{ kVA}$, Relative Load Index: $1.40$).
- **System State:**
  - Active Episodes: `OVERLOAD_SUSTAINED` (Electrical domain).
  - Episode Status: Transitioned from `OPEN` to `CORROBORATED` after $3$ consecutive persistent intervals.
  - Estimated Top-Oil Temp: Rising at $\Delta T_{\text{oil}} = +14.2^\circ\text{C}$.
- **Speaker Notes:**
  > *"Next, the transformer undergoes a sustained $140\%$ overload lasting over 30 minutes. The electrical episode state machine accumulates evidence across successive intervals. Unlike single-point noise, this is sustained. As energy accumulates, the grey-box thermal ODE predicts rising top-oil temperature with conformal 90% uncertainty bounds."*

---

### Step 4: Multi-Domain Evidence Corroboration
- **Action:** Highlight cross-domain corroboration between Electrical ($I_{\text{RMS}}$), Thermal ($\Delta T_{\text{oil}}$), and Phase Imbalance ($I_{\text{unbalance}} = 14.2\%$).
- **System State:**
  - Multi-Domain Episode: Corroborated across Electrical and Thermal domains.
  - Freshness Weights: Recomputed dynamically based on interval age.
- **Speaker Notes:**
  > *"A critical pillar of our twin is multi-domain corroboration. The overload episode is not evaluated in isolation: the system cross-references electrical current with thermal exposure and symmetrical unbalance. Both domains confirm abnormal stress, escalating the episode confidence to corroborated status."*

---

### Step 5: Health (OTHI) & Explainable Maintenance Policy
- **Action:** Open OTHI diagnostic view and Maintenance Priority list.
- **System State:**
  - Composite OTHI: $68.4 / 100$ (Degraded status).
  - Domain Sub-indices:
    - Electrical: $52.0 / 100$
    - Thermal: $61.0 / 100$
    - Insulation: $85.0 / 100$ (Discrete contact normal)
    - Mechanical: $100.0 / 100$
    - Sensor Plausibility: $80.0 / 100$
  - Maintenance Advisory: `P1_URGENT` — *Load Rebalancing & Thermal Inspection*. Action Window: 24 Hours.
- **Speaker Notes:**
  > *"The Operational Transformer Health Index (OTHI) aggregates these five physical domains into an explainable 0–100 score. Notice the composite health drops to 68.4. Our deterministic policy maps this evidence directly to a P1 Urgent advisory with a 24-hour action window, explicitly highlighting the contributing factors: sustained overload and phase unbalance."*

---

### Step 6: Predictive What-If Simulation with Qualification Gating
- **Action:** Trigger 2-hour forward scenario simulation ($+20\%$ load continuation).
- **System State:**
  - Simulated Trajectory: 8 future steps (15-minute intervals).
  - Top-Oil Temperature Projection: $72.4^\circ\text{C} \rightarrow 88.6^\circ\text{C}$ ($+16.2^\circ\text{C}$).
  - Conformal Uncertainty: $[81.2^\circ\text{C}, 96.0^\circ\text{C}]$ (90% coverage).
  - Qualification Banner: `QUALIFIED_PREDICTION: NOT_PROMOTED (DEVELOPMENT_ONLY)`.
- **Speaker Notes:**
  > *"When an operator explores mitigation options, the twin simulates forward what-if scenarios using the discretized grey-box ODE with conformal uncertainty intervals. Crucially, look at the qualification tag: because ambient temperature sensors were unavailable in the field feed, the model is honestly labeled `NOT_PROMOTED`. We provide operators with transparent uncertainty bounds rather than ungrounded false precision."*

---

### Step 7: Human-in-the-Loop Operator Feedback
- **Action:** Submit an operator acknowledgement via UI or `POST /v1/feedback/acknowledge`.
- **System State:**
  - Action Recorded: `ACKNOWLEDGE` for Episode `EP-OVERLOAD-001`.
  - Operator: `operator_control_room_1`.
  - Resolution Ledger: Cryptographically chained immutable entry.
- **Speaker Notes:**
  > *"Safety systems must remain accountable. When the control room operator acknowledges the advisory or registers an on-site thermal scan, the action is logged to an immutable append-only audit ledger with cryptographic state linkage. P0 and P1 recommendations cannot be silently dismissed."*

---

### Step 8: Deterministic WeasyPrint Engineering Audit PDF Export
- **Action:** Click Export PDF or view `http://localhost:8000/v1/reports/summary.pdf?asset_id=DT-TRIPURA-001`.
- **Document Content:**
  - Executive Health & Domain Breakdown
  - FactBundle Provenance Hash (`SHA-256`)
  - Active Anomaly Episodes & Corroboration History
  - Prioritized Maintenance Actions with Action Windows
  - Model Card Qualification Transparency Notice
  - Operator Feedback Audit Trail
- **Speaker Notes:**
  > *"Finally, we generate a formal engineering audit PDF. Generated in real-time by WeasyPrint directly from the authoritative FactBundle, this report contains complete cryptographic provenance hashes, domain breakdowns, and maintenance action plans. It is ready for utility compliance and maintenance crew dispatch."*

---

## 2b. Primary Live Demo — CPRI Synthetic Benchmark v3.0.2 (dashboard)

### Setup (once)
```bash
python -m venv .venv            # Python 3.11+
.venv/Scripts/pip install -e "backend[dev]"     # Linux/macOS: .venv/bin/pip
cd frontend && npm ci && cd ..
```

### Launch (two terminals, from the repo root)
```bash
# Terminal 1 - backend serves ONE asset per process (default TX_1000_COMM)
cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
#   fallback/unqualified-model demo:  DEFAULT_ASSET_ID=TX_250_MIX ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# Terminal 2
cd frontend && npm run dev        # open http://localhost:3000
```
Replay uses each asset's **CAL partition** (2025-01-01 to 2025-07-03 IST, 30-min cadence). TEST partitions are never loaded at
runtime; `y_*` oracle labels are dropped before ingestion. Docker: `docker compose up --build` (defaults to TX_1000_COMM).

### Model qualification (one-shot TEST, frozen before evaluation)
Live matrix: **Data & Model Card** tab, or `GET /v1/models/cpri-evaluation`. Gates: 2-h MAE ≥ 5 % better than persistence;
|bias| ≤ |persistence bias| + 0.10 °C (residual = observed − predicted); 90 % marginal coverage in [80, 98] %; identifiable.

| Asset | Status | 2-h MAE model / persistence (°C) | Signed bias (°C) | Coverage marginal / path | Failed gates |
|---|---|---|---|---|---|
| TX_100_RES | NOT_PROMOTED | 0.907 / 1.327 (+31.7 %) | +0.156 | 98.2 / 96.0 % | bias, coverage |
| TX_160_RURAL | NOT_PROMOTED | 0.986 / 1.079 (+8.6 %) | +0.203 | 97.0 / 94.5 % | bias |
| TX_250_MIX | NOT_PROMOTED (historical, evaluated 2026-10-09) | 1.035 / 1.355 (+23.6 %) | +0.260 | 96.2 / 93.1 % | bias |
| TX_315_RES | NOT_PROMOTED | 1.003 / 1.537 (+34.7 %) | +0.133 | 97.3 / 94.2 % | bias |
| TX_400_COMM | NOT_PROMOTED | 1.118 / 2.655 (+57.9 %) | +0.121 | 97.6 / 94.9 % | bias |
| TX_500_RURAL | NOT_PROMOTED | 1.076 / 1.187 (+9.3 %) | +0.283 | 94.9 / 91.0 % | bias |
| TX_630_MIX | NOT_PROMOTED | 1.046 / 1.425 (+26.6 %) | +0.197 | 96.7 / 93.3 % | bias |
| **TX_1000_COMM** | **PROMOTED** | 1.202 / 2.998 (+59.9 %) | +0.097 (limit 0.107) | 96.9 / 93.6 % | none |

All eight models under-predict on average (positive residual bias), a shared structural limitation of the first-order model.
TX_1000_COMM passes the bias gate by only 0.010 °C. All TEST partitions are now consumed: any further tuning needs a fresh holdout.

### Demo sequence (TX_1000_COMM, ~6 min)
Seek with the replay bar or `POST /v1/replay {"action":"seek","seek_position":N}`:

| Seek | Time (UTC) | What the twin shows |
|---|---|---|
| 781 | 2025-01-17 04:30 | Loading CRITICAL (load ≥ 1.25 × 1000 kVA rating) — OTHI drops |
| 6777 | 2025-05-22 10:00 | Thermal limit CRITICAL + `MNT-THERM-002` (enabled because this model is qualified) |
| 7899 | 2025-06-14 19:00 | Phase/neutral CRITICAL + P2 `MNT-PHASE-004` |

1. **Telemetry** tab: measured voltage, phase currents, kVA, oil and ambient temperature.
2. **Overview**: OTHI and the domain that drives it; open the evidence list for detector, threshold and observed value.
3. **Maintenance Advisories**: deterministic rule, priority and action window; acknowledge one (feedback ledger).
4. **Thermal & What-If**: qualified 2-hour projection in four 30-min steps with the asset's own 90 % CAL envelope.
5. **Data & Model Card**: parameters, TEST metrics and the eight-asset qualification matrix.
6. **3D Twin & CAD Exploded View**: interactive 3D digital twin model in authentic ANSI 70 utility gray. Demonstrate the smooth exploded-view disassembly slider separating HV/LV bushings, corrugated tank, radiator fin banks, conservator piping, and internal core/coils. Highlight the low-profile micro-tag HUD and toggle the left sidebar for full-screen CAD inspection.

### Fallback demo (no qualified model): restart with `DEFAULT_ASSET_ID=TX_250_MIX`
Same monitoring, OTHI, alerts and advisories; thermal model runs in **SHADOW_DESCRIPTIVE** mode, C3 forecasting and what-if are
refused with the reason shown, and the model card explains the failed bias gate. Alert seeks: 1628 (voltage/PF/frequency),
4482 (phase/neutral + `MNT-PHASE-004`), 5413 (loading), 5444 (thermal + loading, OTHI 0). No overload maintenance rule exists, and
`MNT-THERM-002` needs a qualified model, so these show as alerts and health impact without a thermal recommendation.

---

## 3. What We Deliberately Refuse to Claim (Engineering Integrity)

When judges ask about predictive horizons or AI claims, emphasize these boundaries:

1. **No RUL in Hours/Years:** Without multi-year dissolved gas analysis (DGA) and paper tensile strength measurements, claiming exact RUL is unscientific. We provide real-time thermal exposure and health indices instead.
2. **No Arbitrary Failure Probabilities:** We do not produce fabricated percentages like "93.4% failure probability." We report empirical conformal confidence intervals.
3. **No Autonomous Switching:** The twin is an operational decision-support tool. It advises human operators and never executes automated grid switching commands.
4. **Transparent Model Qualification:** The Tripura thermal parameters are explicitly labeled `DEVELOPMENT_ONLY` / `NOT_PROMOTED` due to uninstrumented ambient telemetry.

---

## 4. Live Demo Failure Recovery Procedures

If an unexpected technical issue occurs during the presentation, follow these exact recovery steps:

| Failure Scenario | Immediate Action | Command / Solution |
|---|---|---|
| **Backend container stops / returns 502** | Restart backend service cleanly | `docker compose restart backend` |
| **Frontend UI disconnected / white screen** | Use direct Swagger UI / curl API | Switch browser tab to `http://localhost:8000/docs` |
| **Replay stream hangs or desyncs** | Reset replay state via API | `curl -X POST http://localhost:8000/v1/replay/reset` |
| **PDF generation times out** | Run CLI demo generator directly | `docker compose exec backend python /app/demo_script.py` |
| **Port 8000 / 3000 collision** | Terminate conflicting local processes | `docker compose down` then kill conflicting PID on host |
| **Complete container failure** | Run native Python fallback | `cd backend && python -m uvicorn app.main:app --port 8000` |

> [!CAUTION]
> **Safety Rule:** Never bypass capability gates or fabricate mock data to recover from an error. The system's transparency and graceful degradation are primary evaluation strengths.
