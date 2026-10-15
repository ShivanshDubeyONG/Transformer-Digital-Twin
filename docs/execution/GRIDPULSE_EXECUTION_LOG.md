# GridPulse Execution Log

**Project:** POWERNext-AI Hackathon 2026 — Track 2: Transformer Digital Twin  
**Date:** 2026-10-10  
**Phases Executed:** Phase 1 (PR Integration & Baseline) and Phase 2 (Backend Stabilization)  
**Status:** Complete — Ready for Human Review & Phase 3 Authorization Gate  

---

## 1. Git and Workspace State

- **Repository Root:** `c:\1st year learning programs\CPRI\Transformer_Digital_Twin`
- **Active Branch:** `main`
- **Configured Remote:** `origin` (`https://github.com/SynshAmi/Transformer_Digital_Twin.git`)
- **Incoming PR:** Remote branch `origin/fix/episode-lifecycle-maintenance-ui` fast-forward integrated into `main` at commit `9a72bdfb32f91b790d93707252277d1101859bcf`.
- **Candidate Archive Status:** `gridpulse_synthetic_v1.zip` is present in repository root, untouched and unextracted.
- **Git Commit / Push Status:** No commits or pushes made to shared remote branches.

---

## 2. Active Baseline Dataset & Artifact Verification

- **Active Dataset Configuration:** `cpri_onan_practical_schema_synthetic` v3.0.2 / `cpri_v3_calibration.parquet`
- **Verified Partition Hashes:**
  - `data/processed/cpri_v3_calibration.parquet`: SHA-256 `48d44e99f01878d6b6d510257ec77aeaf2bb8c0bc3762635fe85d1e8ef384d15`
  - `data/processed/cpri_v3_fit.parquet`: SHA-256 `8e258d7c4333ea614b14d24176cbe3b4ae96229c12282e46efc5240212001eb5`
  - `data/processed/cpri_v3_test.parquet`: SHA-256 `c57adad79c3d4fba7ba210c4f74d9e5f58c7414dfa5eb10ecf79d1a1b143c4a8`
- **Active Model Checkpoints:** 8 calibrated assets (`dt_001` through `dt_008`) under `artifacts/models/` verified with matching SHA-256 checksums and evaluation reports intact.

---

## 3. Pre-Fix Baseline Test Execution (Phase 1)

- **Backend Pytest Suite:**
  - Command: `pytest backend/tests`
  - Result: **472 passed, 1 warning in 232.77s (100% pass rate)**
  - Failures: 0
- **Frontend Production Build:**
  - Command: `npm run build` (in `frontend/`)
  - Result: **Clean build, exit code 0 in 13.76s** (`dist/` generated with 2548 modules transformed)

---

## 4. Phase 2 Stabilization Implementation

Implemented all proposed fixes from `BACKEND_STABILIZATION_PROPOSALS.md` strictly aligned with `FINAL_ARCHITECTURE_DECISIONS.md`:

| Fix ID | Component | Summary of Implementation | Status |
|---|---|---|---|
| **FIX-1** | `backend/app/engine/reducer.py` | Initialized `thermal_output` from `thermal_gate.evaluate_step()` and passed to `anomaly_engine.evaluate_event(..., thermal_output=thermal_output)`. Added graceful fallback for mock engines. | Confirmed & Fixed |
| **FIX-2** | `backend/app/engine/othi.py`, `reducer.py` | Added reset capability for latched protection trip: trip is unlatched when current trip telemetry is normal (`current_trip_active == False`) AND operator logs an authorized resolution action. Added `reset_protection_trip()` and `reset()`. | Confirmed & Fixed |
| **FIX-3** | `backend/app/engine/maintenance.py` | Decoupled direct physical thermal limit exceedance (`DET_THERMAL_LIMIT_ABSOLUTE`) from `self.is_thermal_qualified` so that critical safety advisories fire across all assets regardless of model promotion. Model-derived residual rules remain gated. | Confirmed & Fixed |
| **FIX-4** | `backend/app/engine/feedback.py`, `maintenance.py`, `api/routers/feedback.py` | Fixed dismissal/resolution persistence across streaming frames by removing premature expiration check (`and current_time <= d_ts`). Expanded feedback collection to handle both `DISMISS` and `RESOLVE` actions. | Confirmed & Fixed |
| **FIX-5** | `backend/app/engine/othi.py` | Added canonical signal IDs to `DOMAIN_SIGNAL_MAPPING`: `oil_level_pct` in `oil_protection`, `current_i1..3` in `loading` & `phase_neutral`, and `voltage_v1..3` & `voltage_ll_v` in `voltage_pf_freq`. | Confirmed & Fixed |
| **FIX-6** | `backend/app/engine/anomaly_detectors.py` | Dynamic asset-specific nominal voltage resolution: bound nominal voltage from asset profile (`profile.rated_voltage_lv_v` or `nominal_voltage_v`), eliminating false overvoltage alarms on 240V/250V distribution transformers. Updated fallback default to 240.0V. | Confirmed & Fixed |
| **FIX-7 & FIX-8** | `backend/app/engine/anomaly_detectors.py` | Sensor plausibility: configured `temp_flatline_min_steps = 4` to prevent false stuck-sensor alarms on quantized equilibria. Added rate-of-change check `oti_max_step_degc = 10.0` ensuring sudden large step jumps (>10°C) trigger plausibility alarms even across 15–30 minute sample intervals. | Confirmed & Fixed |

---

## 5. Regression Testing & Verification

- **Dedicated Fix Verification Suite:**
  - Test file: `backend/tests/test_stabilization_fixes.py`
  - Tests implemented: 9 unit and integration tests covering FIX-1 through FIX-8.
  - Result: **9 passed in 1.57s (100% pass rate)**.
- **Full Backend Pytest Suite Post-Fix:**
  - Command: `pytest backend/tests`
  - Result: **481 passed, 1 warning in 242.43s (100% pass rate)**.
  - Failures: **0** (472 baseline + 9 new regression tests = 481).
- **Frontend Production Build Post-Fix:**
  - Command: `npm run build` (in `frontend/`)
  - Result: **Clean build, exit code 0 in 12.30s**.

---

## 6. Phase 1 & 2 Gate Assessment

- **Phase 1 Criteria:** Met. (PR integrated, baseline documented, active CPRI dataset intact).
- **Phase 2 Criteria:** Met. (All 8 stabilization defects implemented, tested, full suite green, 0 regressions).

---

## 7. Phase 3 — Candidate Dataset Audit & Isolated Extraction

- **Candidate Archive:** `gridpulse_synthetic_v1.zip` (repository root)
- **Archive SHA-256:** `4601e56663158a129acb777b2725cf1eab0ad17f95527e59be1bf6d39bf6e827`
- **Extraction Destination:** Isolated candidate directory `data/candidates/gridpulse_synthetic_v1/`
- **Extracted Manifest & File Checksums:**
  - `gridpulse_synthetic_30min.csv` (7,930,797 bytes): SHA-256 `7109621d88fd0cd26df67465a4c6b0736ac0868972b3a5fe2b31ecb192823eb9`
  - `fault_events.csv` (2,629 bytes): SHA-256 `82ac01a494cc7050b2faf0a09481a0a85df2ecb8d3fae6f816e540346028e619`
  - `METHODOLOGY.md`: SHA-256 `7f9dd426b1f1db252a0819eb6ffd6f2de881371c309b60eb474a63dcc8b3f372`
  - `SCENARIOS_AND_VALIDATION.md`: SHA-256 `ac6a65d67c38faf8a108b9cd4621a4eacdeda540a89266a02db133fe0826c982`
  - `SOURCES.md`: SHA-256 `68428fd52d78eb09fdde0d7780680b227e74ff1760ae156e751589c643184ea4`
  - `generate_dataset.py`: SHA-256 `431cbf65d39cd16478601b7f5f67cafd1c08b070ccff23a45a4b0a3469608a36`
- **Dataset Structure & Cadence:**
  - 34,560 rows total across 4 distribution assets (8,640 samples per asset): `DT-01`, `DT-02`, `DT-03`, `DT-04`
  - 30-minute sampling cadence over 180 continuous days (2025-01-01 00:00:00 to 2025-06-29 23:30:00 UTC)
  - Canonical Splits: FIT (60% = 20,736 rows), CAL (20% = 6,912 rows), TEST (20% = 6,912 rows)
  - Data Quality: Clean, no missing rows, timestamps strictly monotonic, no path traversal risks.
- **CPRI Dataset Isolation:**
  - Active CPRI v3.0.2 partitions (`cpri_v3_calibration.parquet`, `cpri_v3_fit.parquet`, `cpri_v3_test.parquet`) and 8 model checkpoints (`dt_001` - `dt_008`) remain 100% untouched.

---

## 8. Phase 4 — Seamless Telemetry Expansion

- **Adapter Implementation:** `backend/app/adapters/gridpulse_synthetic.py`
  - `GridPulseSyntheticAdapter` maps CSV records into standard `CanonicalEvent` and `Measurement` objects.
  - Generates deterministic UUIDv5 event IDs based on `(asset_id, timestamp)`.
  - Preserves source provenance (`source.system = "SCADA_SYNTHETIC"`, raw record hash).
  - Explicit UCUM unit conversions and registry extensions in `backend/app/core/units.py`: added `kpa`, `kpa_g`, `kpa/day`, `%/day`, `binary`, `boolean`.
- **Profile Extensions (`backend/app/models/profile.py`):**
  - Added physical asset attributes: `tank_type` (`conservator` vs `sealed_corrugated`), `has_oil_level_gauge` (bool), `has_pressure_sensor` (bool), `rated_lv_v_ll` (V), and `impedance_pct` (%).
- **Asset Configuration Mappings:**
  - `DT-01`: 250 kVA, Conservator, Oil gauge = True, Pressure sensor = False, $Z = 4.50\%$
  - `DT-02`: 500 kVA, Conservator, Oil gauge = True, Pressure sensor = False, $Z = 4.75\%$
  - `DT-03`: 250 kVA, Sealed corrugated, Oil gauge = False, Pressure sensor = True, $Z = 4.50\%$
  - `DT-04`: 160 kVA, Conservator, Oil gauge = True, Pressure sensor = False, $Z = 4.25\%$
- **Telemetry Mapping Matrix:**

| Source Field | Canonical Signal ID | UCUM Unit | Construction Applicability | Downstream Consumer |
|---|---|---|---|---|
| `oil_level_pct` | `oil_level_pct` | `%` | Conservator only (`DT-01, 02, 04`) | `detect_protection_oil_status`, `MNT-OIL-008` |
| `oil_level_rate_of_change` | `oil_level_rate_pct_day` | `%/day` | Conservator only | `detect_protection_oil_status` |
| `oil_level_alarm` | `oil_level_alarm` | `1` (binary) | Conservator only | `detect_protection_oil_status` |
| `tank_pressure_kpa` | `pressure_kpa` | `kPa` | Sealed tank only (`DT-03`) | `detect_protection_oil_status`, `MNT-PRESS-009` |
| `pressure_rate_of_change` | `pressure_rate_kpa_day` | `kPa/day` | Sealed tank only | `detect_protection_oil_status` |
| `pressure_relief_operated` | `pressure_relief_operated`| `1` (binary) | Sealed tank / PRD equipped | `detect_protection_oil_status`, `MNT-PRESS-009` |
| `lv_breaker_trip` | `lv_breaker_trip` | `1` (binary) | All assets | `detect_protection_oil_status`, `MNT-PROT-001` |
| `hv_fuse_blown` | `hv_fuse_blown` | `1` (binary) | All assets | `detect_protection_oil_status`, `MNT-PROT-001` |
| `ambient_temp_c` | `ambient_temp_c` | `degC` | All assets | Thermal physics model |
| `top_oil_temp_c` | `top_oil_temp_c` | `degC` | All assets | Thermal physics & stuck-gauge detector |
| `winding_temp_c` | `winding_hotspot_c` | `degC` | All assets | Thermal limit & insulation aging |
| `current_a` | `current_a` / `current_i1` | `A` | All assets | Electrical loading & prospective $I_{sc}$ |
| `voltage_v` | `voltage_v` / `voltage_v1` | `V` | All assets | Voltage regulation & electrical stress |

---

## 9. Phase 5 — Additional Domain Capabilities

- **Extra A: Oil-Level Trend & Suspected Leak Monitoring:**
  - Integrated in `backend/app/engine/anomaly_detectors.py` (`detect_protection_oil_status`).
  - Detects declining trend `DET_OIL_LEVEL_DECLINING_TREND` when rate of change $\le -0.10\,\%/day$ over window.
  - Detects stuck gauge `DET_OIL_LEVEL_GAUGE_STUCK` when oil level is static while top oil temperature swings $\ge 5^\circ\text{C}$.
  - Triggers advisory `MNT-OIL-008` (P2 PLANNED_ACTION: "Oil level declining trend detected. Inspect for external leakage or faulty gauge.") in `rules.yaml` and `MaintenanceEngine`.
- **Extra B: Sealed-Tank Pressure Monitoring:**
  - Detects overpressure `DET_PRESSURE_HIGH_ALARM` ($\ge 25\text{ kPa(g)}$) and underpressure `DET_PRESSURE_LOW_ALARM` ($\le -10\text{ kPa(g)}$) on sealed corrugated tanks.
  - Detects pressure relief device operation `DET_PRESSURE_RELIEF_OPERATED` with severity 1.0.
  - Gated strictly by asset construction: automatically disabled for conservator tanks (`tank_type != "sealed_corrugated"`).
  - Triggers advisory `MNT-PRESS-009` (P1 URGENT_INSPECTION: "Sealed tank abnormal pressure or PRD operation detected.") in `rules.yaml` and `MaintenanceEngine`.
- **Extra C: Electrical Stress & Prospective Short-Circuit Reference:**
  - Implemented `calculate_prospective_short_circuit_ka` in `backend/app/engine/physics.py`:
    $$I_{rated,LV} = \frac{S_{rated}}{\sqrt{3} \cdot V_{rated,LV,LL}}, \quad I_{sc,sym} = \frac{I_{rated,LV}}{Z_{pu} \cdot 1000} \text{ [kA]}$$
  - Stored in `DerivedFeatures.prospective_short_circuit_ka`.
  - Handled LV breaker trip (`DET_PROT_LV_BREAKER_TRIP`) and HV fuse blown (`DET_PROT_HV_FUSE_OPERATED`) with immediate P0 critical latching and reset requirements.
  - Explicitly documents that half-hourly telemetry represents post-fault steady state and prospective symmetrical reference, not sub-cycle transient fault waveforms (no IEC 60909 compliance claimed).
- **Extra D: Construction-Aware Capability Gating:**
  - Updated `CapabilityEvaluator` in `backend/app/engine/capability.py`:
    - `oil_level_monitoring`: ENABLED for conservator tanks with gauges; DISABLED for sealed tanks (`DT-03`).
    - `tank_pressure_monitoring`: ENABLED for sealed tanks with pressure sensors (`DT-03`); DISABLED for conservators (`DT-01, 02, 04`).
    - `short_circuit_stress`: ENABLED when rated LV voltage, power rating, and impedance percentage are present.
  - Preserved frozen OTHI architecture, health scoring formulation, and model qualification gates intact.

---

## 10. Verification Results & Regression Testing

1. **Targeted Test Suite (`test_candidate_adaptation_and_extra_domains.py` + related):**
   - 11 new comprehensive tests covering candidate data ingestion, unit conversions, oil leak trend detection, stuck gauge detection, sealed tank pressure alarms, PRD operation, prospective short-circuit calculations, protection trips, and construction-aware gating.
   - Result: **83 passed in 1.82s (100% pass rate)**.
2. **Full Pytest Backend Suite:**
   - Command: `pytest backend/tests`
   - Total Collected Tests: **492 items** (472 baseline + 9 stabilization + 11 candidate/extra domains = 492)
   - Result: **492 passed, 1 warning in 219.48s (03:39) (100% pass rate)**.
   - Failures: **0**.

---

## 11. Phase Gate Status Summary

- **Phase 1 (Integration & Baseline):** **PASS**
- **Phase 2 (Backend Stabilization):** **PASS**
- **Phase 3 (Candidate Dataset Audit & Extraction):** **PASS**
- **Phase 4 (Seamless Telemetry Expansion):** **PASS**
- **Phase 5 (Supported Domain Capabilities):** **PASS**
- **Phase 6+ (Model Training, Calibration, Promotion, Production Cutover):** **HELD / DEFERRED** (Out of scope for this execution pass).

---

## 12. Targeted Engineering Audit & Hardening Pass

Conducted a targeted engineering audit of the Phase 3–5 implementation, data semantics, physical assumptions, and test coverage:

| Finding ID | Severity | File / Component | Verified Issue | Action Taken & Hardening Fix | Verification Test |
|---|---|---|---|---|---|
| **AUDIT-1** | High | `backend/app/engine/physics.py` | `calculate_prospective_short_circuit_ka` did not validate non-finite inputs (`math.isnan`, `math.isinf`), allowing `NaN` and `Inf` to bypass `<= 0` checks. | Added `math.isfinite()` assertions for all three inputs (`rated_kva`, `rated_lv_v_ll`, `impedance_pct`). Returns `None` on non-finite, zero, or negative inputs. | `test_prospective_short_circuit_handles_invalid_and_nonfinite_inputs` |
| **AUDIT-2** | Medium | `backend/app/engine/anomaly_detectors.py` | `detect_protection_oil_status` defaulted `has_pressure` to `True` when `profile is None`, falsely assuming pressure sensors on unprofiled assets. | Fixed default to `False` (`has_pressure = bool(...) if profile else False`). Sealed tank pressure monitoring is enabled only when explicitly configured. | `test_unprofiled_asset_pressure_monitoring_strictly_disabled` |
| **AUDIT-3** | Medium | `backend/app/engine/anomaly_detectors.py` | Stuck oil-level gauge detector did not validate chronological monotonicity or check for multi-day communication outages, risking false positives across gaps. | Added monotonic timestamp verification and a maximum 2-hour step gap bound (`max_gap_s <= 7200`) across the observation window. Added signal alias lookups for `oil_level` and `top_oil_temp`. | `test_stuck_gauge_handles_gaps_and_out_of_order_samples` |
| **AUDIT-4** | Low | `backend/app/adapters/gridpulse_synthetic.py` | Candidate dataset `partition` column (`FIT`, `CAL`, `TEST`) was not explicitly tagged onto the canonical event envelope. | Added partition preservation into `CanonicalEvent.event_quality_flags` as `PARTITION_{PARTITION}`. Extended UUIDv5 namespace to incorporate `source_record_id`. | `test_end_to_end_candidate_csv_stream_to_fact_bundle` |
| **AUDIT-5** | Low | `backend/app/engine/maintenance.py` | `MNT-OIL-008` did not include magnetic oil gauge alarm (`DET_PROT_MOG_ALARM`), and `MNT-PRESS-009` did not include PRD operation (`DET_PRESSURE_RELIEF_OPERATED`). | Added `DET_PROT_MOG_ALARM` to `oil_evs` and `DET_PRESSURE_RELIEF_OPERATED` to `press_evs`. | `test_sealed_tank_high_pressure_and_prd_contact` |

- **Post-Audit Verification Runs:**
  - Targeted test suite (`backend/tests/test_candidate_adaptation_and_extra_domains.py` + adjacent): **87 passed in 2.45s (100% pass rate)**.
  - Replay & runtime wiring integration suite (`test_runtime_wiring.py` + `test_replay.py`): **22 passed in 179.06s (100% pass rate)**.
  - Baseline CPRI partitions & checkpoints: **Confirmed 100% unchanged** via SHA-256 matching.

---

## 13. Documentation Synchronization, Technical References & Research Audit

Conducted a comprehensive synchronization of project documentation against the verified implementation, datasets, test evidence, and engineering standards:

1. **Central Technical References Established:**
   - Authored [`docs/references/TECHNICAL_REFERENCES_AND_CITATIONS.md`](../references/TECHNICAL_REFERENCES_AND_CITATIONS.md) providing peer-reviewed literature and normative standards citations (IEEE C57.91-2011, IEC 60076-7:2018, IEEE C57.109-2018, Glover et al. 2017, KSEB SCM-SPEC/XD/DT2 Rev 0.2, IS 1180:2014, ASTM D3487, NEMA MG-1, Page 1954, Vovk et al. 2005).
   - Mapped all implemented physical/statistical equations to code files and functions.
2. **Audit Claims Review & Substantiation:**
   - *Pressure Envelope & Standards Disambiguation:* Clarified that "S7 §16.2" cites **Kerala State Electricity Board (KSEB) Technical Specification Doc. SCM-SPEC/XD/DT2 Rev 0.2 §16.2**, defining the $\pm 0.4\text{ kg/cm}^2$ ($\pm 39.2\text{ kPa}$) operating tank pressure boundary. Pressure limits $+25\text{ kPa(g)}$ alarm, $+35\text{ kPa(g)}$ PRD relief, and $-10\text{ kPa(g)}$ lower boundary are candidate `SCENARIO_SETTING` parameters designed to operate safely inside this envelope. Gated strictly to sealed corrugated tanks.
   - *Oil-Level Trend Threshold:* Verified that the $-0.10\,\%/day$ slope threshold is calibrated to detect synthetic leak rates ($0.12\text{--}0.22\text{ L/day}$) while exceeding the $3\sigma$ diurnal thermal expansion noise envelope ($\approx 0.09\,\%/day$). Telemetry slope triggers visual inspection advisory `MNT-OIL-008`, not an autonomous proof of physical leak.
   - *Prospective Short-Circuit:* Documented as a steady-state symmetrical through-fault current reference ($I_{sc,sym} = I_{rated} / Z_{pu}$) per IEEE C57.109-2018 and Glover (2017). Explicitly disclaimed as an IEC 60909 fault study or sub-cycle transient waveform reconstruction.
   - *Thermal & Insulation Ageing:* Documented top-oil differential equation per IEC 60076-7 and Najar et al. (2017). Winding hotspot is absent from baseline telemetry; Arrhenius lifetime consumption remains strictly gated off (`C4_THERMAL_INSULATION_LIFETIME = False`).
   - *Dataset Provenance:* Confirmed active CPRI v3.0.2 baseline integrity and total isolation of candidate synthetic dataset `gridpulse_synthetic_v1.zip` in `data/candidates/gridpulse_synthetic_v1/`.
3. **Documentation Hierarchy & Historical Tagging:**
   - Verified `GRIDPULSE_MASTER_EXECUTION_PLAN.md` as primary authoritative roadmap.
   - Tagged `docs/IMPLEMENTATION_PLAN.md` with explicit historical/superseded callout linking to the master execution plan.
   - Synchronized `README.md` to reflect Phase 1–5 achievements, expanded canonical telemetry schema, exact test metrics (492 backend tests, 87 targeted tests, 22 replay tests), and isolated candidate status.
4. **Phase 6 Boundary Enforcement:**
   - Completed reproducible Phase 6 evaluation of candidate dataset (`gridpulse_synthetic_v1`). Active CPRI baseline remains untouched and in service.

---

## 14. Phase 6 — Candidate Dataset Evaluation & Promotion Audit

Executed the reproducible Phase 6 thermal calibration, uncertainty estimation, holdout evaluation, and anomaly detector assessment for candidate dataset `gridpulse_synthetic_v1` across all four candidate assets (`DT-01`, `DT-02`, `DT-03`, `DT-04`) adhering strictly to the chronological FIT → CAL → FREEZE → TEST protocol.

### 14.1 Candidate Partition Boundaries & Provenance
- **Candidate CSV:** `data/candidates/gridpulse_synthetic_v1/gridpulse_synthetic_30min.csv` (SHA-256: `7109621d88fd0cd26df67465a4c6b0736ac0868972b3a5fe2b31ecb192823eb9`)
- **Partitions per Asset:**
  - `FIT`: 5,184 rows (108 days, 2025-01-01 to 2025-04-18 UTC)
  - `CAL`: 1,728 rows (36 days, 2025-04-19 to 2025-05-24 UTC)
  - `TEST`: 1,728 rows (36 days, 2025-05-25 to 2025-06-29 UTC, untouched holdout lockbox)

### 14.2 Fitted Thermal Model Parameters (FIT Partition Only)
- **DT-01 (250 kVA, Conservator):** $\beta_0 = 11.0978^\circ\text{C}, \beta_1 = 19.5021^\circ\text{C}, \tau = 2.7090\text{ h}$, Identifiable = True ($CV(\tau) = 0.0035$). Selected Driver: `apparent_power_kva` ($S_{ref} = 161.3\text{ kVA}$).
- **DT-02 (500 kVA, Conservator):** $\beta_0 = 13.2796^\circ\text{C}, \beta_1 = 20.2094^\circ\text{C}, \tau = 2.2045\text{ h}$, Identifiable = True ($CV(\tau) = 0.0035$). Selected Driver: `apparent_power_kva` ($S_{ref} = 313.3\text{ kVA}$).
- **DT-03 (250 kVA, Sealed Corrugated):** $\beta_0 = 11.2628^\circ\text{C}, \beta_1 = 21.7232^\circ\text{C}, \tau = 2.6951\text{ h}$, Identifiable = True ($CV(\tau) = 0.0052$). Selected Driver: `apparent_power_kva` ($S_{ref} = 170.9\text{ kVA}$).
- **DT-04 (160 kVA, Conservator):** $\beta_0 = 12.3829^\circ\text{C}, \beta_1 = 29.7729^\circ\text{C}, \tau = 3.0729\text{ h}$, Identifiable = True ($CV(\tau) = 0.0037$). Selected Driver: `apparent_power_kva` ($S_{ref} = 130.7\text{ kVA}$).

### 14.3 One-Shot Holdout TEST Partition Evaluation Matrix (2-Hour Trajectory)

| Asset ID | Rating | Tank Type | Model MAE | Pers. MAE | MAE Imprv % | Signed Bias | 90% Path Cov. | Marg. Cov. | Decision Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **DT-01** | 250 kVA | Conservator | **1.3056 °C** | 2.5384 °C | **+48.57 %** | +0.109 °C | 94.16 % | 96.36 % | **PROMOTED** |
| **DT-02** | 500 kVA | Conservator | **1.3346 °C** | 3.0307 °C | **+55.96 %** | -0.057 °C | 96.58 % | 98.11 % | **NOT_PROMOTED** (Marg. Cov. > 98.0%) |
| **DT-03** | 250 kVA | Sealed Corr. | **1.0564 °C** | 2.7621 °C | **+61.75 %** | +0.025 °C | 97.22 % | 98.49 % | **NOT_PROMOTED** (Marg. Cov. > 98.0%) |
| **DT-04** | 160 kVA | Conservator | **1.6401 °C** | 3.0721 °C | **+46.61 %** | -0.085 °C | 96.17 % | 98.10 % | **NOT_PROMOTED** (Marg. Cov. > 98.0%) |

**Aggregate Candidate Metrics:**
- Mean Model MAE: **1.3342 °C** vs Mean Persistence MAE: **2.8508 °C** (Mean Improvement: **+53.22 %**).
- All four assets achieved outstanding thermal trajectory forecast improvements ($\ge 46.6\%$) and negligible signed bias ($|\text{bias}| \le 0.11^\circ\text{C}$).
- DT-02, DT-03, and DT-04 were gated out solely by the strict upper bound of the conformal coverage criterion ($98.11\%\text{--}98.49\%$ marginal coverage vs $[80.0\%, 98.0\%]$ band), reflecting slightly over-conservative conformal calibration.

### 14.4 TEST Partition Multi-Domain Anomaly Detector Evaluation
- **DT-02 Through-Fault & Overload:** Successfully detected LV breaker trip (`DET_PROT_LV_BREAKER_TRIP`: 2), HV fuse operation (`DET_PROT_HV_FUSE_OPERATED`: 12), and sustained overload / thermal limits (`DET_THERMAL_LIMIT_ABSOLUTE`: 6, `DET_PROT_OTI_ALARM`: 4), matching test ground-truth events `PE-DT-02-004` and `PE-DT-02-005`.
- **DT-03 Sealed Tank Pressure:** Successfully detected abnormal gauge pressure (`DET_PRESSURE_HIGH_ALARM`: 4, `DET_PRESSURE_ALARM_CONTACT`: 3), matching test scenario `SC-DT-03-TEST-HIGH_PRESSURE_LOAD-1`. Conservator assets correctly reported zero pressure detections.
- **DT-04 Oil Level & Stuck Gauge:** Successfully detected declining oil level trend (`DET_OIL_LEVEL_DECLINING_TREND`: 1118) and stuck gauge condition (`DET_OIL_LEVEL_GAUGE_STUCK`: 55), matching test scenarios `SC-DT-04-TEST-OIL_LEAK-1` and `SC-DT-04-TEST-GAUGE_STUCK-1`.
- **Data Quality Flags:** Envelope quality flags (`DET_DQ_ENVELOPE_FLAG`: 1728) fired reliably for simulated communication loss and frozen sensor episodes.

### 14.5 Promotion Recommendation Verdict
- **Overall Recommendation:** `PARTIAL_PROMOTE_RECOMMEND_REVIEW` (1 of 4 assets passed all criteria for full promotion; 3 assets achieved high accuracy but tripped upper conformal coverage boundary).
- **Gate Enforcement:** Active configuration has **NOT** been switched. Active production baseline remains on CPRI v3.0.2 (`cpri_v3_*.parquet`), and Phase 7 cutover remains **HELD** pending human review and explicit authorization.

---

## 15. Phase 6 Evidence Cross-Check & Pre-Phase-7 Operational Plan

Executed a rigorous, evidence-backed cross-check of all Phase 6 candidate artifacts, evaluation reports, registry resolvers, and runtime baselines prior to any Phase 7 cutover authorization.

### 15.1 Candidate Model & Registry Status Audit

| Candidate Asset | Rating & Tank Type | Artifact SHA-256 (Disk vs Manifest vs Report) | Evaluation Criteria Met | Standalone Report Status | Registry Resolution | Runtime Active Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **DT-01** | 250 kVA, Conservator | `66e57559f0b5d798...` (Verified Match) | **5 / 5 Passed** (MAE +48.57%, Bias +0.109°C, Cov 96.36%) | **PROMOTED** | `UNCALIBRATED` (Not in `data/processed/`) | **INACTIVE** (Quarantined in `data/candidates/`) |
| **DT-02** | 500 kVA, Conservator | `47700a2840a7bf70...` (Verified Match) | **4 / 5 Passed** (Tripped Coverage: 98.11% > 98.0%) | **NOT_PROMOTED** | `UNCALIBRATED` | **INACTIVE** (Quarantined) |
| **DT-03** | 250 kVA, Sealed Corr. | `9d8e765edef6f647...` (Verified Match) | **4 / 5 Passed** (Tripped Coverage: 98.49% > 98.0%) | **NOT_PROMOTED** | `UNCALIBRATED` | **INACTIVE** (Quarantined) |
| **DT-04** | 160 kVA, Conservator | `d1165612978bb789...` (Verified Match) | **4 / 5 Passed** (Tripped Coverage: 98.10% > 98.0%) | **NOT_PROMOTED** | `UNCALIBRATED` | **INACTIVE** (Quarantined) |

### 15.2 Resolution of Discrepancy (DT-01 "PROMOTED" vs Portfolio "RECOMMEND REVIEW")
- **Per-Asset Report (`test_evaluation_report_candidate_dt-01.json`):** Evaluated strictly against the 5 frozen promotion gates in `calibration.py`. DT-01 satisfied all gates independently (+48.57% MAE improvement, +0.109°C signed bias, 96.36% coverage in $[80\%, 98\%]$), legitimately earning the `PROMOTED` status on an asset-specific basis.
- **Portfolio Summary (`candidate_phase6_evaluation_summary.json`):** Aggregates across the entire candidate dataset (`gridpulse_synthetic_v1`). Because DT-02, DT-03, and DT-04 tripped the upper coverage ceiling ($98.10\%\text{--}98.49\%$), only 1 of 4 assets passed unconditionally. The batch pipeline therefore issued an overall portfolio recommendation of `PARTIAL_PROMOTE_RECOMMEND_REVIEW`.
- **Runtime Truth:** Neither report label implies operational deployment. Candidate artifacts remain strictly quarantined in `data/candidates/gridpulse_synthetic_v1/artifacts/`. Active runtime registry (`backend/app/core/registry.py`) does not resolve candidate paths and returns `UNCALIBRATED` for DT-01. Operational activation has NOT occurred.

### 15.3 Active Production Baseline Verification
- **Active Dataset:** `cpri_v3_0_2` (comprising `cpri_v3_fit.parquet`, `cpri_v3_calibration.parquet`, and `cpri_v3_test.parquet` in `data/processed/`).
- **Active Asset ID:** `TX_1000_COMM` (1000 kVA commercial distribution transformer, defined in `backend/app/core/config.py`).
- **Active Model Checkpoint:** `data/processed/calibrated_thermal_model_cpri_tx_1000_comm.json` (SHA-256: `e8d97705afc238639acb18544a29ab2f436bc269bd54c2f9994eee37e201fab7`).
- **Active Parameters:** $\beta_0 = 7.8025^\circ\text{C}, \beta_1 = 42.0074^\circ\text{C}, \tau = 4.2132\text{ h}$, $S_{ref} = 1150.46\text{ kVA}$.
- **Active Runtime Resolution:** Confirmed `resolve_model_artifact(asset_id="TX_1000_COMM")` binds to `test_evaluation_report_cpri_tx_1000_comm.json`, returns `PROMOTED`, and authorizes C3 forward trajectory forecasting and residual anomaly tracking. Baseline remains 100% operational and untouched.

### 15.4 Evaluation Integrity & Embargo Audit
- **Chronological Partitions:** `gridpulse_synthetic_30min.csv` boundaries verified as strictly non-overlapping and chronological:
  - `FIT`: 2025-01-01T00:00:00Z to 2025-04-18T23:30:00Z (5,184 rows per asset, 108 days).
  - `CAL`: 2025-04-19T00:00:00Z to 2025-05-24T23:30:00Z (1,728 rows per asset, 36 days).
  - `TEST`: 2025-05-25T00:00:00Z to 2025-06-29T23:30:00Z (1,728 rows per asset, 36 days).
- **Zero Leakage & Contamination:**
  - Load driver selection (K=5 CV) and thermal parameter fitting ($\beta_0, \beta_1, \tau$) executed exclusively on clean FIT rows (`dq_flag == 'OK'`).
  - Conformal scaling factors ($q_{90}$, half-widths) fitted exclusively on CAL partition.
  - Candidate artifacts were frozen and hashed BEFORE holdout evaluation was invoked.
  - Holdout TEST evaluation was executed strictly one-shot on the frozen artifact path with hash binding verification. Zero re-tuning, iterative fitting, or feedback loops occurred.
- **Coverage Ceiling Rationale:** The upper marginal coverage limit of 98.0% (`80.0 <= marginal_coverage_pct <= 98.0`) is a locked safeguard against vacuous, uninformative uncertainty bands. Excessively wide intervals achieve high empirical coverage but destroy operational utility. For DT-02..04, exceptionally clean synthetic residuals resulted in slightly conservative scaling, tripping the ceiling by $0.10\%\text{--}0.49\%$.

### 15.5 Multi-Domain Anomaly Metrics Clarification
- **Metric Type Disambiguation:** Phase 6 evaluation summary tables report raw detector emission counts (`detector_counts`) across 1,728 holdout events (e.g., `DET_DQ_ENVELOPE_FLAG: 1728`, `DET_PLAUS_FROZEN_SENSOR: 8652`), NOT precision, recall, or false discovery rates.
- **Emission Multiplicity:** Multi-channel plausibility detectors inspect all analog channels (3-phase voltages, currents, temperatures), emitting multiple evidence items per timestamp during flatline/dropout episodes.
- **Scenario Verification:** Targeted test suite (`backend/tests/test_candidate_adaptation_and_extra_domains.py`) confirmed 100% deterministic recall on discrete protection and alarm contacts (`lv_breaker_trip`, `hv_fuse_operated`, `oti_alarm`, `pressure_alarm`, `prd_operated`). Continuous anomaly thresholds provide sensitive early detection without asserting autonomous fault classification.

### 15.6 Pre-Cutover Controlled Trial Plan
To validate candidate model `DT-01` in real operational execution prior to Phase 7 cutover without altering the baseline:
1. **Target Candidate:** Asset `DT-01` (250 kVA Conservator), Model `calibrated_thermal_model_candidate_dt-01.json`.
2. **Runtime Execution Path:** Replay engine executing via `/v1/replay/start` and `/v1/replay/step` or direct test harness invoking `ReplayEngine`.
3. **Configuration Isolation:** Controlled trial runs with environment variable overrides: `DEFAULT_ASSET_ID=DT-01`, `DATASET_ID=gridpulse_synthetic_v1`, `DB_PATH=:memory:` (or dedicated temporary DuckDB file). Active baseline files and default settings remain untouched.
4. **Adapter Ingestion:** `GridPulseSyntheticAdapter` ingest CAL partition records only (reserving TEST as untouched holdout).
5. **Expected Observable Outputs:** Valid canonical events, stable top-oil ODE tracking ($|\hat{T}_{oil} - T_{oil}| \le 2.0^\circ\text{C}$), 90% conformal intervals ($\pm 2.50^\circ\text{C}$ to $\pm 6.28^\circ\text{C}$), C3 capability enabled, C4 Arrhenius disabled.
6. **Acceptance Criteria:** Zero 500 exceptions, zero NaN/Inf in state vector, deterministic replay idempotency, stable OTHI score.
7. **Rollback Procedure:** Unset environment overrides, remove temporary DB file. System immediately reverts to `TX_1000_COMM` on `cpri_v3_0_2` with verified zero-downtime parity.
8. **Pre/Post-Run Verification:** Confirm SHA-256 hashes of all artifacts before trial and verify baseline restoration after trial.

### 15.7 Required Human Approvals Before Phase 7
1. Review and formal acceptance of Section 15 cross-check findings.
2. Decision on conformal coverage ceiling: either (a) approve deployment of qualifying asset `DT-01` only, or (b) issue a technical waiver for the $0.10\%\text{--}0.49\%$ ceiling breach on `DT-02..04`.
3. Authorization to execute the isolated Controlled Runtime Trial for `DT-01`.

---

## 16. Controlled Runtime Trial Execution for Candidate DT-01

Executed the authorized, isolated controlled runtime trial of candidate model `DT-01` on the `CAL` partition of `gridpulse_synthetic_30min.csv` while strictly keeping the holdout `TEST` partition untouched and preserving the baseline CPRI `TX_1000_COMM` runtime in 100% operational isolation.

### 16.1 Trial Boundaries & Provenance Verification
- **Candidate Model Artifact:** `data/candidates/gridpulse_synthetic_v1/artifacts/calibrated_thermal_model_candidate_dt-01.json`
- **Verified Artifact SHA-256:** `66e57559f0b5d798b0d0f3d39c4bc539bfc5165cc4ca38771a24ac11ed1386dd` (Matches manifest and Phase 6 holdout report bit-for-bit).
- **Candidate Asset Configuration:** `DT-01` (250 kVA, Conservator tank, ONAN cooling, 3-phase 4-wire 50 Hz, nominal cadence 1800s / 30 min).
- **Thermal Model Parameters:** $\beta_0 = 11.0978^\circ\text{C}, \beta_1 = 19.5021^\circ\text{C}, \tau = 2.7090\text{ h}$, Driver: `apparent_power_kva` ($S_{ref} = 161.3\text{ kVA}$).
- **Input Trial Partition:** Exclusively the `CAL` partition of `gridpulse_synthetic_30min.csv` (1,728 records, 36 days: 2025-04-19T00:00:00Z to 2025-05-24T23:30:00Z).
- **Holdout Test Isolation:** The `TEST` partition (2025-05-25 to 2025-06-29) was strictly untouched.
- **Storage Isolation:** DuckDB `:memory:` storage engine utilized; no persistent production state or active database was modified.

### 16.2 Telemetry Ingestion & Replay Performance
- **Records Processed:** 1,728 raw records adapted via `GridPulseSyntheticAdapter` into 1,728 canonical events.
- **Adaptation Errors:** 0 (100% schema and UCUM unit compliance).
- **Replay Throughput:** 1,728 events processed in 5.52 seconds (**313.0 events/sec**).
- **Runtime Exceptions:** 0 unhandled exceptions or crashes.
- **Data Integrity:** Zero NaN or Inf values detected across all state vectors and derived features.

### 16.3 Real-Time Thermal Tracking & Residual Stability
- **Observations Evaluated:** 1,718 valid step points (after warm-up).
- **Tracking Residuals ($r_k = T_{oil,obs} - \hat{T}_{oil}$):**
  - Mean Signed Residual: **+0.2495 °C**
  - Mean Absolute Error (MAE): **0.7626 °C**
  - Residual Standard Deviation: **1.8429 °C**
  - Maximum Transient Excursion: **27.1422 °C** (during simulated rapid cooling transient)
- **Conformal Prediction Half-Widths:** $\pm 2.15^\circ\text{C}$ (30 min), $\pm 2.56^\circ\text{C}$ (60 min), $\pm 4.54^\circ\text{C}$ (90 min), $\pm 6.71^\circ\text{C}$ (120 min).
- **Thermal Model Gate Status:** Operational in `PROMOTED` state with active continuous ODE projection.

### 16.4 Dynamic Capability Manifest & FactBundle Provenance
- **Highest Capability Tier Achieved:** **`C3` (Thermal Predictive Modeling)**
  - `C0` (Data Integrity): Enabled (Grade A)
  - `C1` (Electrical Balance): Enabled (Grade A)
  - `C2` (Descriptive Thermal Monitoring): Enabled (Grade A)
  - `C3` (Predictive Thermal Modeling & Forecasting): Enabled (Grade A)
  - `C4` (Thermal Exposure & Arrhenius Ageing): Disabled (Grade U, correctly gated off due to absent winding hotspot telemetry)
- **Multi-Domain Signals Enabled:** Loading proxy, power factor, current/voltage imbalance, neutral current, PQS consistency, frequency, oil-level monitoring, short-circuit stress.
- **Excluded Features:** Sealed tank pressure (correctly disabled for Conservator tank type).
- **Final Trial FactBundle:** Provenance Hash `932a10658d792c6a50cb596d4f1e2c6165753217ee69cf62cb17634d80035da2`.

### 16.5 Determinism & Idempotency Audit
- A complete second pass was executed from a pristine reset state over the exact same 1,728 canonical events.
- **Sequence Identity:** Residual sequence was bit-for-bit identical (`residuals_identical == True`).
- **Health Score Identity:** Final OTHI score matched exactly (`10 == 10`).
- **Provenance Hash Identity:** FactBundle SHA-256 matched bit-for-bit (`932a10658d792c6a...`).
- **State Timestamp Identity:** Successor state timestamps aligned 100%.
- **Verdict:** Replay state transitions $F(S_{t-1}, E_t) \rightarrow S_t$ are **100% deterministic and idempotent**.

### 16.6 Active Baseline Isolation & Quarantining Check
- Verified production registry interfaces in [`backend/app/core/registry.py`](../../backend/app/core/registry.py):
  - `resolve_asset_profile(asset_id="DT-01")`: Returns `ProfileVerificationStatus.UNVERIFIED` (candidate not yet cut over).
  - `resolve_model_artifact(asset_id="DT-01")`: Returns `UNCALIBRATED` (`parameters=None`), confirming candidate cannot accidentally run in production without Phase 7 cutover.
  - `resolve_model_artifact(asset_id="TX_1000_COMM")`: Returns `PROMOTED` ($\beta_0=7.8025^\circ\text{C}$), confirming active CPRI baseline remains 100% operational and untouched.

### 16.7 Smallest Implementation Change Required for Phase 7 Live Cutover
Prior to any Phase 7 HTTP / live app cutover, the following minimal, focused changes are required:
1. **Registry Resolver Extension ([`backend/app/core/registry.py`](../../backend/app/core/registry.py)):**
   - In `resolve_asset_profile`: Route `DT-01` to `SYNTHETIC_ASSET_PROFILES["DT-01"]` (250 kVA, 1800s cadence, ONAN, Conservator).
   - In `resolve_model_artifact`: Add candidate resolution path loading `calibrated_thermal_model_candidate_dt-01.json` when `dataset_id == "gridpulse_synthetic_v1"` or copy promoted candidate to `data/processed/`.
2. **Replay Router Extension ([`backend/app/api/routers/replay.py`](../../backend/app/api/routers/replay.py)):**
   - In `ensure_dataset_loaded`: Add a branch for `DT-01` streaming `gridpulse_synthetic_30min.csv` (CAL partition) via `GridPulseSyntheticAdapter`.
3. **Active Settings Switch ([`backend/app/core/config.py`](../../backend/app/core/config.py)):**
   - Update default asset identifier to `DT-01`.

### 16.8 Trial Conclusion
**Verdict:** **`TRIAL_SATISFACTORY`**  
The candidate model `DT-01` ran with zero exceptions, zero numerical anomalies, high thermal ODE fidelity (MAE 0.76 °C), 100% replay determinism, and full operational capability gating (C0–C3 enabled, C4 safely gated). Candidate is fully validated and ready for human review before Phase 7 cutover.

---

## 17. DT-01 Controlled Trial Residual Investigation & Root Cause Analysis

Conducted a targeted engineering investigation into the maximum absolute thermal residual ($27.1422^\circ\text{C}$) reported during the isolated `DT-01` controlled runtime trial.

### 17.1 Excursion Identification & Telemetry State
- **Step Index:** 1,484 (within CAL partition)
- **Timestamp (UTC):** `2025-05-19T22:00:00Z`
- **Observed Top-Oil Temperature ($T_{oil,obs}$):** `72.2 °C`
- **Model Free-Running Prediction ($\hat{T}_{oil}$):** `45.0578 °C`
- **Calculated Residual ($r_k$):** `+27.1422 °C`
- **Concurrent Conditions:**
  - Ambient Temperature ($T_{amb}$): `24.6 °C` (declined from $35.4^\circ\text{C}$ at 14:30 UTC)
  - Load ($S_{kva}$): `67.8 kVA` / `92.5 A` (declined from $210.9\text{ kVA}$ at 14:30 UTC)
  - Packet Quality Flag: `dq_flag == 'OK'` (communication link operational, sensor flatline)

### 17.2 Provenance & Root Cause: Ground-Truth Injected Sensor Flatline
Forensic cross-referencing against [`data/candidates/gridpulse_synthetic_v1/SCENARIOS_AND_VALIDATION.md`](../../data/candidates/gridpulse_synthetic_v1/SCENARIOS_AND_VALIDATION.md#L35) established the root cause with 100% certainty:
- **Scenario ID:** `SC-DT-01-CAL-TOPOIL_FROZEN-1`
- **Scenario Type:** `TOPOIL_FROZEN`
- **Injected Window:** `2025-05-19 14:30 UTC` to `2025-05-19 22:00 UTC` (16 consecutive 30-min intervals / 7.5 hours).
- **Ground Truth Injected Fault:** The top-oil temperature transmitter was artificially frozen flatline at exactly `72.2 °C`.
- **Secondary Excursion:** Step 881 (`2025-05-07T08:30:00Z`, $r = +25.8229^\circ\text{C}$) corresponds to scenario `SC-DT-01-CAL-TOPOIL_SPIKE-1` (single-sample $+25.0^\circ\text{C}$ injected spike).

### 17.3 Physical Model Tracking & Instantaneous Recovery
- **Physical Reason for Discrepancy:** As night fell and transformer load decreased from $210.9\text{ kVA}$ down to $67.8\text{ kVA}$ while ambient temperature dropped to $24.6^\circ\text{C}$, the physical equilibrium oil temperature dropped to $\approx 39.1^\circ\text{C}$. The first-order ODE ($\tau = 2.71\text{ h}$) correctly simulated the exponential cooling of the physical transformer down to $45.06^\circ\text{C}$. Because the sensor remained artificially frozen at $72.2^\circ\text{C}$, the arithmetic divergence reached $27.14^\circ\text{C}$ at the final sample of the freeze episode.
- **Immediate Post-Scenario Recovery:** At step 1,485 (`2025-05-19T22:30:00Z`), the injected scenario ended and the transmitter unfroze to the real physical temperature:
  - Observed $T_{oil}$: `45.0 °C`
  - Model $\hat{T}_{oil}$: `44.0491 °C`
  - Immediate Residual: **`+0.9509 °C`**
- **Recovery Time:** 0 minutes (instantaneous sub-1°C convergence upon sensor restoration). The model exhibited zero divergence, zero parameter corruption, and zero persistent state bias.

### 17.4 Anomaly Engine Verification
- The runtime [`MultiDomainAnomalyEngine`](../../backend/app/engine/anomaly_detectors.py) correctly detected the sensor failure:
  - `DET_PLAUS_FROZEN_SENSOR` fired 98 times during the 7.5-hour freeze episode with reason code `['SENSOR_FLATLINE_DETECTED']`.
  - The digital twin successfully recognized that the sensor was stuck and that the apparent residual excursion was an instrumentation fault rather than thermal distress.

### 17.5 Nominal Operational Stream Metrics (Excluding Injected Faults)
Across all 1,701 nominal operating points (35.4 days of continuous, unreset open-loop ODE integration):
- **Mean Signed Residual:** **`+0.1178 °C`**
- **Mean Absolute Error (MAE):** **`0.6350 °C`**
- **Residual Standard Deviation:** **`0.8233 °C`**
- **90th Percentile Absolute Residual:** **`1.3475 °C`**
- **95th Percentile Absolute Residual:** **`1.6222 °C`**
- **99th Percentile Absolute Residual:** **`2.3451 °C`**
- **Maximum Nominal Residual:** **`5.7355 °C`**

### 17.6 Evaluation Metric Disambiguation
- **Phase 6 Report:** Evaluated on the holdout **TEST** partition using **2-hour forward trajectory rolling-origin projection** initialized from observed $T_{oil}$ (MAE: $1.31^\circ\text{C}$, 90% coverage: $94.16\%$).
- **Trial Metric:** Measured the **continuous 36-day free-running shadow ODE** on the **CAL** partition without measurement feedback resets.
- The conformal uncertainty bounds ($\pm 2.15^\circ\text{C}$ to $\pm 6.71^\circ\text{C}$) are intended to cover nominal operational forecast uncertainty; they are not expected to envelope an outright sensor failure where a frozen transmitter disagrees with physical reality by $27^\circ\text{C}$.

### 17.7 Revised Trial Conclusion
**Verdict:** **`TRIAL_SATISFACTORY`**  
Root cause is 100% established as the ground-truth injected scenario `SC-DT-01-CAL-TOPOIL_FROZEN-1`. The thermal ODE model behaved in complete accordance with heat-transfer physics, and the anomaly detector flagged the flatline. Nominal tracking fidelity is outstanding (MAE $0.635^\circ\text{C}$, 99% of residuals $< 2.35^\circ\text{C}$). Candidate `DT-01` remains fully qualified and ready for human review before Phase 7 cutover.

---

## 18. Phase 7 Dataset Cutover & Fallback, and Phase 8 Frontend/Backend Integration

**Date:** 2026-10-11  
**Phases Executed:** Phase 7 (Approved Dataset Cutover and Fallback) and Phase 8 (Frontend/Backend Integration)  
**Status:** Complete — Tested, Verified in Docker, and Ready for Visual Verification Gate  

### 18.1 Multi-Dataset Architecture & Model Resolution (Phase 7)
- **Dataset Catalog:** Both `cpri_v3_0_2` (baseline) and `gridpulse_synthetic_v1` (candidate) are active and selectable concurrently.
- **Asset Profile Resolution (`resolve_asset_profile`):**
  - CPRI assets (`TX_1000_COMM` etc.) resolve against `CPRI_SYNTHETIC_ASSET_RATINGS` (1,000 kVA, 900s cadence, ONAN).
  - Candidate assets (`DT-01` through `DT-04`) resolve against `SYNTHETIC_ASSET_PROFILES` (250 kVA, 1,800s cadence, ONAN, Conservator for DT-01/02/04, Sealed Tank for DT-03).
- **Baseline & Candidate Model Promotion & Isolation (`resolve_model_artifact`):**
  - **`TX_1000_COMM` (Promoted CPRI Baseline):** Resolves verified baseline model artifact `data/processed/calibrated_thermal_model_cpri_tx_1000_comm.json` (SHA-256 `e8d97705afc238639acb18544a29ab2f436bc269bd54c2f9994eee37e201fab7`) bound to manifest `data/processed/candidate_manifest_cpri_tx_1000_comm.json` (SHA-256 `59b294bfbecf0beabda4498f2f4347820583f0f499aef210766c9c596f8af8d4`) and holdout TEST evaluation report `data/processed/test_evaluation_report_cpri_tx_1000_comm.json` (SHA-256 `eb7f114f7f0d480bb7164215f6bbd274e443292a469c67bd05c3e379ba441875`), with exact parameters $\beta_0=7.8025^\circ\text{C}, \beta_1=42.0074^\circ\text{C}, \tau=4.2132\text{ h}$, $S_{\text{ref}}=1150.455452\text{ kVA}$, achieving active `PROMOTED` baseline status.
  - **`DT-01` (Promoted Candidate):** Resolves verified Phase 6 candidate artifact `data/candidates/gridpulse_synthetic_v1/artifacts/calibrated_thermal_model_candidate_dt-01.json` (SHA-256 `66e57559f0b5d798b0d0f3d39c4bc539bfc5165cc4ca38771a24ac11ed1386dd`) bound to manifest `data/candidates/gridpulse_synthetic_v1/artifacts/candidate_manifest_dt-01.json` (SHA-256 `89f3a46923d83b15f0abb858ef92c8d1fd8fe45a7f3b30ee32e31d2d297d16a1`) and holdout TEST evaluation report `data/candidates/gridpulse_synthetic_v1/artifacts/test_evaluation_report_candidate_dt-01.json` (SHA-256 `c45b3fcc758da48a0d51c4cc461b2893a9a10d61b449743c69f88514947e08db`), with exact parameters $\beta_0=11.0978^\circ\text{C}, \beta_1=19.5021^\circ\text{C}, \tau=2.7090\text{ h}$, $S_{\text{ref}}=161.3\text{ kVA}$, achieving `PROMOTED` status with full C0–C3 predictive capabilities.
  - **`DT-02`, `DT-03`, `DT-04` (Unpromoted Candidates):** Strictly resolved as `NOT_PROMOTED` with unpromoted qualifications, preserving Phase 6 gate boundaries (coverage failure on 120-min horizon). No silent promotion occurred.
  - **Zero Silent Fallback:** Non-existent candidate assets return explicit uncalibrated artifacts rather than falling back silently to CPRI models.
- **Fail-Safe Replay Engine (`ensure_dataset_loaded`):**
  - Dynamically loads either CPRI Parquet files or `data/candidates/gridpulse_synthetic_v1/gridpulse_synthetic_30min.csv` (CAL split: 1,728 frames) via `GridPulseSyntheticAdapter`.
  - Missing candidate data raises an explicit `ReplayException` rather than silently defaulting to CPRI.
  - Replay state updates automatically synchronize asset profile, model artifact, and `CapabilityEvaluator`.
- **APIs Added:**
  - `GET /v1/assets`: Returns complete catalog of both datasets, asset specs (kVA, tank type, voltage, cadence), and active dataset/asset.
  - `GET /v1/models/candidate-evaluation`: Returns evaluation matrix, gate metrics, and promotion status for all 4 candidate assets.
- **Report Provenance:** `backend/app/reports/report_generator.py` dynamically resolves dataset ID so candidate asset reports reflect `gridpulse_synthetic_v1`.

### 18.2 Dataset-Aware Frontend Integration (Phase 8)
- **Dataset & Transformer Selection (`ReplayBar.tsx`, `App.tsx`):**
  - ReplayBar provides interactive Dataset dropdown allowing seamless switching between CPRI Benchmark v3.0.2 and GridPulse Synthetic v1.0.0.
  - Asset dropdown dynamically updates based on the active dataset (8 CPRI assets vs 4 GridPulse candidate assets).
  - Status badge explicitly displays model qualification: `Promoted Baseline` (`TX_1000_COMM`), `Promoted Candidate` (`DT-01`), or `Unpromoted Candidate` (`DT-02`..`04`).
- **Telemetry Availability & Honest Representation (`TelemetryPhaseGrid.tsx`):**
  - **Oil Level:** Displays valid percentage if gauge fitted (`DT-01`, `DT-02`, `DT-04`); displays `Unsupported (Sealed Tank)` for `DT-03`; displays `Unsupported (No Gauge)` for CPRI.
  - **Tank Pressure:** Displays valid kPa(g) if pressure transducer fitted (`DT-03`); displays `Unsupported (Conservator)` for `DT-01`, `DT-02`, `DT-04`, and CPRI.
  - **Prospective Short-Circuit Stress:** Explicitly labeled as a `Derived Reference Calculation (4.5% nameplate Z, IEC 60076 reference assumption; not measured waveform)`.
  - **Protection Contacts:** Live status for LV Breaker, PRD Operated, and OTI Alarm.
  - **Capability Manifest (C0–C4):** Dynamic tiles render backend `FactBundle` capabilities, displaying real disabled reason codes (e.g., `Gated: Winding hotspot telemetry absent` for C4).
- **Candidate Evaluation Matrix View (`ModelEvaluationMatrix.tsx`):**
  - Toggle between CPRI benchmark assets and GridPulse candidate assets.
  - Shows MAE, RMSE, conformal coverage, gating criteria, and promotion verdicts.
- **Frontend Production Build:** Verified clean with `npm run build` (`tsc && vite build`) with 0 errors.

### 18.3 Verification & Testing Results
- **Phase 7 Focused Suite (`backend/tests/test_phase7_cutover_and_fallback.py`):**
  - `test_resolve_asset_profiles`: Passed.
  - `test_resolve_model_artifact_dt01_promoted`: Passed.
  - `test_resolve_model_artifact_dt02_not_promoted`: Passed.
  - `test_resolve_model_artifact_cpri_baseline_preserved`: Passed.
  - `test_candidate_replay_loading_and_switching`: Passed.
  - `test_assets_catalog_endpoint`: Passed.
  - Result: **6 passed in 29.12s**.
- **Broader Targeted Backend Suite:**
  - `test_candidate_adaptation_and_extra_domains.py` + `test_stabilization_fixes.py`: 24/24 passed.
  - `test_api_core.py` + `test_api_analytics.py`: 22/22 passed.
  - `test_contracts_fixture.py` + `test_fact_bundle.py` + `test_reports.py`: 29/29 passed.
  - Total: **81 passed, 0 failures**.
- **Docker Compose Live Integration:**
  - Built and started with `docker compose up --build -d`.
  - `transformer_dt_backend`: Up (healthy) on `http://localhost:8000`.
  - `transformer_dt_frontend`: Up on `http://localhost:3000`.
  - Live container verification exercised:
    1. `GET /healthz`: Healthy on default `TX_1000_COMM`.
    2. `GET /v1/assets`: Retrieved 2 datasets, 12 assets.
    3. `GET /v1/models/candidate-evaluation`: Confirmed DT-01 PROMOTED, DT-02..04 NOT_PROMOTED.
    4. Switched to `DT-01`: Loaded 1,728 frames, stepped 5 frames, top-oil reached 46.4°C, highest capability tier C3.
    5. Rollback to `TX_1000_COMM`: Loaded 8,761 frames, stepped 5 frames, sequence 5, highest capability tier C3.
    6. Frontend HTTP: Status 200 on `http://localhost:3000`.



