# MVP Specification
 
> [!NOTE]
> **HISTORICAL SCOPE FREEZE DOCUMENT**  
> This document defines the initial MVP scope freeze from 2026-10-03.  
> For current architecture, execution plans, and multi-dataset integration status, consult:
> - [`GRIDPULSE_MASTER_EXECUTION_PLAN.md`](../GRIDPULSE_MASTER_EXECUTION_PLAN.md)
> - [`docs/FINAL_ARCHITECTURE_DECISIONS.md`](FINAL_ARCHITECTURE_DECISIONS.md)
> - [`docs/execution/GRIDPULSE_EXECUTION_LOG.md`](execution/GRIDPULSE_EXECUTION_LOG.md)

## POWERNext-AI Hackathon 2026 --- Track 2

### Digital Twin for Intelligent Health Monitoring and Predictive Maintenance of Distribution Transformers

**Document status:** Implementation scope freeze (Initial Baseline)\
**Date:** 2026-10-03\
**Team:** SKY HIGH

------------------------------------------------------------------------

## 1. Purpose

This document converts the approved SRS and frozen
`FINAL_ARCHITECTURE_DECISIONS.md` into the **concrete Minimum
Viable Product (MVP) that the team will build for the hackathon**.

The SRS defines what the product is required to do.

This document defines:

-   what will actually be implemented for the hackathon;
-   what is mandatory for the demo;
-   what is conditional;
-   what is deferred;
-   the concrete system flow;
-   the MVP user journey;
-   the minimum backend/frontend/reporting surface;
-   acceptance criteria for calling the MVP complete.

The MVP does **not** reopen or redesign the frozen architecture.

------------------------------------------------------------------------

# 2. MVP Objective

The MVP shall demonstrate a credible, reproducible Digital Twin
prototype for a distribution transformer using chronological operational
data.

The central demo story is:

> **Observe → validate → synchronize transformer state → understand
> expected behavior → detect abnormal conditions → assess operational
> health → recommend an action → explain the evidence.**

The MVP must demonstrate genuine engineering value rather than maximize
the number of features.

------------------------------------------------------------------------

# 3. MVP Product Boundary

## 3.1 MVP asset model

The MVP shall support the Digital Twin of a monitored transformer asset.

The initial development/calibration source is the locked Tripura
transformer monitoring dataset.

The final CPRI/hackathon dataset shall be supported through the same
canonical contract once its schema is available.

The source-specific adapter may differ, but downstream analytics shall
not contain dataset-specific column logic.

## 3.2 Draft condition-monitoring workbook role

The `Draft Data for Condition Monitoring.xlsx` workbook supplied with the hackathon materials is a reference, configuration, and commissioning artifact.

It provides useful reference semantics for measurement checks and test-trip thresholds where applicable.

It is explicitly NOT:
- the primary operational telemetry dataset;
- a time-series training dataset (it contains snapshots without timestamps or chronological history);
- evidence that every field has fully verified physical semantics.

Downstream thermal models, CUSUM calibration, and statistical health indexes shall not rely on this workbook for model training. The locked Tripura time-series dataset remains the development telemetry source.

------------------------------------------------------------------------

# 4. MVP Must-Build Scope

The following capabilities are **mandatory** for MVP completion.

## 4.1 Data ingestion

### Required

-   Tripura CSV adapter.
-   Canonical telemetry conversion.
-   Raw-record preservation.
-   Source provenance.
-   Timestamp normalization.
-   Measurement/unit mapping.
-   Schema validation.
-   Basic data-quality classification.
-   Chronological replay.

### Required outcome

A source record can travel through:

``` text
Tripura CSV
    ↓
Source Adapter
    ↓
Canonical Event
    ↓
Validation / Quality
    ↓
Chronological Replay
```

------------------------------------------------------------------------

## 4.2 CPRI/final-dataset adapter fixture

The MVP shall include a second adapter fixture that intentionally uses
different source field names and/or units from the Tripura development
data. The fixture shall demonstrate that source-specific names and units
are handled only by the adapter layer, that the same canonical event
contract is produced, and that downstream analytics require no
dataset-specific changes. The mapping shall be declarative, deterministic,
and versioned.

This fixture tests the adapter boundary; it is not a claim about the exact
fields or units that CPRI will provide. The final CPRI dataset, once
supplied, remains the final demonstration target.

------------------------------------------------------------------------

# 5. MVP Data and State Layer

## 5.1 Synthetic scenario injection

The MVP shall include a **labelled scenario-injection component** used for deterministic validation and the live demo.

The injector shall operate on a copy of development/fixture data and shall never modify the authoritative raw dataset.

Minimum supported scenarios:

- sensor spike;
- stuck sensor;
- persistent sensor bias/drift;
- sustained load step;
- phase imbalance where the required signals exist.

Every injected record/output shall carry an explicit `SYNTHETIC_SCENARIO` label and scenario identifier.

The injector exists to validate and demonstrate the evidence/episode pipeline. Synthetic scenarios shall never be presented as real transformer faults or as evidence of real-world fault-detection accuracy.

Data-integrity conditions such as unit/scale errors, timestamp problems,
gaps, duplicate/conflicting records, and direct protection/status events
shall be represented through dedicated validation fixtures. They may live
outside the transformation logic of the injector, but they must be
executable through the same validation/demo harness. Direct
protection/status fixtures shall exercise the critical-evidence precedence
path.

## 5.2 Canonical contract

The MVP shall implement the frozen canonical event contract.

Each usable observation shall retain:

-   asset identity;
-   event time;
-   receive/replay context where applicable;
-   source identity;
-   source record identity;
-   signal identity;
-   value;
-   unit;
-   original signal name/value/unit;
-   quality;
-   mapping/version information.

## 5.3 Raw and canonical storage

The MVP shall preserve:

1.  immutable raw source records;
2.  canonical telemetry;
3.  derived features;
4.  state/checkpoint information.

The storage approach shall follow the frozen architecture.

## 5.4 Data-quality handling

The MVP shall explicitly handle:

-   missing values;
-   invalid values;
-   unknown units;
-   duplicate records;
-   conflicting observations;
-   timestamp irregularities;
-   gaps;
-   out-of-order/late events.

No silent value fabrication is permitted.

## 5.5 Capability tiers and manifest

The MVP shall evaluate a `CapabilityManifest` based on current valid evidence, implementing the frozen capability tiers:

| Tier | Required evidence | Enabled capability |
| - | - | - |
| **C0 — Integrity** | Timestamped event, asset ID, and at least one recognized signal. | Ingest, replay, quality handling, provenance, and raw/canonical reporting. |
| **C1 — Electrical** | At least one usable power or current path (three phases required for phase-level imbalance). | Loading proxy, P-Q-S checks, phase imbalance where possible, status rules, and electrical episodes. |
| **C2 — Thermal descriptive** | Current top-oil or WTI with known units. | Thermal trends, direct limits, hours in bands, and thermal condition domain. No causal forecast is implied. |
| **C3 — Thermal predictive** | Valid top-oil, ambient, and load driver; sufficient history; promoted grey-box model. | Expected behavior, residual/CUSUM, two-hour conditional projection, threshold crossing, and what-if analysis. |
| **C4 — Thermal exposure** | C3 plus credible hot-spot estimate and verified insulation class. | Relative ageing rate and equivalent ageing hours (numeric RUL remains withheld). |

Capabilities are also evaluated as independent flags. Missing or invalid inputs degrade capabilities gracefully according to these prerequisite gates rather than aborting or inventing data.

------------------------------------------------------------------------

# 6. MVP Digital Twin

The MVP Digital Twin shall be a **stateful operational representation**
of the transformer.

It shall maintain, where supported:

-   latest valid observations;
-   electrical operating state;
-   thermal state;
-   detector state;
-   anomaly episodes;
-   OTHI state;
-   thermal exposure;
-   maintenance recommendations;
-   artifact/configuration versions.

## 6.1 Replay

The primary operating mode for the hackathon shall be chronological
replay.

Replay shall:

-   process records in event-time order;
-   use the same reducer as the operational path;
-   update the TwinState;
-   generate deterministic outputs;
-   support accelerated demonstration playback.

## 6.2 Checkpoints

The MVP shall support checkpoints sufficient to:

-   resume replay;
-   restore state;
-   reproduce a state;
-   test late-event handling.

------------------------------------------------------------------------

# 7. MVP Feature Derivation

The MVP shall derive transparent engineering features where the required
measurements exist.

### Electrical

-   apparent power;
-   power factor;
-   phase-current magnitude imbalance;
-   phase-voltage magnitude imbalance;
-   neutral-current ratio;
-   P-Q-S consistency;
-   loading indicator.

### Thermal

-   ambient temperature context;
-   observed top-oil temperature;
-   expected top-oil temperature when the thermal model is promoted;
-   thermal residual;
-   thermal exposure metrics.

Every derived feature must retain lineage to its inputs.

------------------------------------------------------------------------

# 8. MVP Thermal Model

The thermal model is a **core MVP capability**, subject to its promotion
gate.

## 8.1 Model

The MVP shall implement the frozen first-order grey-box top-oil model.

The model shall use the available load driver and ambient temperature to
estimate expected top-oil behavior.

The load-driver precedence remains:

``` text
Measured apparent power
        ↓ if unavailable
sqrt(P² + Q²)
        ↓ if unavailable
RMS-equivalent phase current
```

Where verified transformer rating is unavailable, the system shall use
the declared relative load reference rather than inventing a per-unit
transformer rating.

## 8.2 Calibration

The MVP shall:

-   use chronological data partitions;
-   prevent future leakage;
-   calibrate model parameters only from the permitted training
    partition;
-   validate against later unseen data;
-   compare against the required baselines;
-   evaluate error and bias;
-   evaluate uncertainty;
-   determine whether promotion requirements are satisfied.

## 8.3 Promotion

The thermal model shall only enter predictive mode if its frozen
promotion requirements pass.

If promotion fails, the MVP shall **not attempt to rescue the demo by
weakening the gate**.

Instead it shall enter:

``` text
THERMAL_MODEL: FALLBACK
```

## 8.4 Fallback

Fallback shall still provide:

-   observed temperature trends;
-   thermal exposure;
-   direct thermal-limit evidence where supported;
-   persistence-based expected behavior where appropriate.

Fallback shall disable:

-   causal load/ambient what-if;
-   model-dependent residual CUSUM;
-   model-dependent threshold projection;
-   model-dependent predictive recommendations.

The UI shall clearly communicate the fallback state.

------------------------------------------------------------------------

# 9. MVP Two-Hour Conditional Scenario

If the thermal model is promoted, the MVP shall provide a bounded
two-hour conditional thermal projection.

The user shall be able to inspect a scenario involving:

-   load;
-   ambient condition;
-   projected top-oil trajectory;
-   empirical uncertainty band;
-   threshold crossing where a verified/configured threshold exists;
-   calibration/extrapolation status.

The projection shall be explicitly described as:

> **conditional expected thermal behavior**

and not as a transformer failure prediction or RUL prediction.

------------------------------------------------------------------------

# 10. MVP Anomaly Detection

The MVP anomaly system shall use the frozen evidence architecture.

## 10.1 Evidence sources

It shall include:

1.  telemetry/data-integrity checks;
2.  direct engineering checks;
3.  thermal residual evidence where the model is promoted;
4.  two-sided CUSUM where calibration requirements are met;
5.  independent electrical/protection context.

## 10.2 Episode manager

The MVP shall implement the frozen episode state machine:

``` text
NORMAL ── strong/persistent evidence ──→ WATCH
   │                                      │
   │                                      └──→ WARNING
   │                                             │
   └── verified direct critical ────────────────→ CRITICAL
                                                   │
WATCH / WARNING / CRITICAL ── clean recovery ──→ RECOVERING
                                                   │
                                                   └── sufficient clean period ──→ CLOSED

Not every episode must pass through every state.
```

Transitions shall use persistence, hysteresis, corroboration, and
recovery conditions defined by the architecture.

## 10.3 Critical evidence

Direct verified critical/trip evidence shall retain precedence over
model-derived evidence.

Model evidence alone shall not create a critical state.

The system shall not claim a root cause when the evidence supports only
a hypothesis.

## 10.4 CUSUM calibration and fallback gate

Where thermal model residuals are evaluated, the two-sided CUSUM decision limit $h$ must be calibrated against the clean validation partition:
- $h$ must yield $\le 1$ false warning episode per 7 asset-days on clean validation data.
- The injected 2-sigma drift scenario must be detected within 1 hour (4 nominal samples).

If the required calibration cannot be justified from the available data, the CUSUM detector shall be explicitly disabled (`CUSUM: DISABLED`) and documented in the capability manifest, while direct engineering checks remain fully active. Performance shall never be invented.

------------------------------------------------------------------------

# 11. MVP Operational Transformer Health Index

The MVP shall implement **OTHI**.

## 11.1 Domains & Evidence Families

The MVP shall support, where evidence exists, the 5 exact canonical domains:
- thermal;
- loading;
- phase/neutral;
- voltage/PF/frequency;
- oil/protection.

**Evidence Family Deduplication:**
- Each evidence item is associated with a `condition_family`.
- Domain severity $s_d \in [0.0, 1.0]$ is evaluated as the maximum severity among eligible condition families in that domain. Derived representations of the same physical condition do not sum.
- Across domains, secondary penalties apply only to semantically distinct condition families.

## 11.2 Formula, Algorithm & Status Bands

The MVP shall implement the `MAX_PLUS_SECONDARY_V1` aggregation algorithm:

``` text
Base_Penalty = MAX(domain_severities)

Secondary_Penalty = 0.20 × SUM(other non-duplicative domain severities)

Total_Penalty = MIN(1.0, Base_Penalty + Secondary_Penalty)

OTHI = round(100 × (1 − Total_Penalty))
```

The `0.20` coefficient is a visible **product-policy parameter**, versioned and documented as such. The resulting OTHI is a deterministic integer from 0 to 100.

### Status bands

| OTHI score | Status | Meaning |
| - | - | - |
| **80–100** | **Normal** | Asset operating within expected engineering boundaries. |
| **60–79** | **Watch** | Moderate deviation or persistent minor abnormal evidence in one or more domains. |
| **40–59** | **Warning** | Significant operational stress or multi-domain corroboration. |
| **0–39** | **Critical** | Severe operating exceedance, direct trip/critical protection event, or critical multi-domain failure risk. |

OTHI is strictly an operational/current-condition index reflecting currently observed operating condition, not a whole-life asset-health or remaining useful life (RUL) score.

## 11.3 Evidence Gating, Staleness & Anti-Uplift

The MVP shall:
- expose domain severities and driving domain;
- expose an evidence grade ($A, B, C, U$);
- withhold the numeric OTHI when evidence is insufficient ($\ge 2$ current domains or 1 decisive direct trip required);
- implement **hybrid stale-domain handling**: `CURRENT` (fresh), `WARNING_STALE` (`HELD_STALE`), and `HARD_STALE` (dropped);
- enforce the **Anti-Uplift Rule**: loss of observability must never improve health. If missing/stale domains make the score appear healthier than the last-known abnormal condition, withhold numeric `current_othi` and expose `last_valid_othi` with staleness reason;
- govern categorical health-band transitions by episode persistence (direct trips immediately transition to `CRITICAL`).

------------------------------------------------------------------------

# 12. MVP Thermal Exposure and Ageing

The MVP shall provide **capability-specific gated thermal exposure** (C4 decoupled from C3 grey-box ODE promotion):

1. **Observed Thermal Exposure (Always Active with Valid Telemetry):**
   - peak temperature;
   - time spent in temperature bands ($T_o > 85^\circ\text{C}, > 95^\circ\text{C}, > 105^\circ\text{C}$);
   - degree-hours above configured thresholds;
   - bounded two-hour threshold projection.
2. **Standards-Derived Equivalent Ageing:**
   - Direct verified hot-spot measurement + verified insulation profile (`CELLULOSIC_NON_THERMALLY_UPGRADED` vs `CELLULOSIC_THERMALLY_UPGRADED`) enables relative ageing rate ($F_{AA}$ / $V$) and equivalent ageing hours ($L_{eq}$) even if the C3 grey-box top-oil ODE is unpromoted.
   - Model-derived hot spot requires promoted C3 model.
   - Unverified insulation profile (`UNKNOWN`) gracefully gates standards-derived ageing.
   - Every standards-derived calculation records its explicit standard edition (e.g. IEEE Std C57.91-2011 / IEC 60076-7:2018).

WTI binary alarm/trip contacts shall not be interpreted as continuous winding hot-spot measurements. Whole-life RUL and failure probabilities remain unsupported.

------------------------------------------------------------------------

# 13. MVP Maintenance Engine

The MVP shall implement deterministic, versioned maintenance rules (`backend/app/engine/rules.yaml`).

Each active recommendation shall expose:
- rule ID (`MNT-PROT-001` .. `MNT-MODEL-007`);
- title, triggering condition, evidence IDs, severity, priority;
- qualitative action window (`IMMEDIATE`, `WITHIN_24H`, `NEXT_AUTHORIZED_MAINTENANCE_WINDOW`, `MONITOR`, `MODEL_REVIEW`);
- **action-window provenance metadata**: `window_provenance_type` (`APPLICABLE_STANDARD_OR_GUIDE`, `MANUFACTURER_REQUIREMENT`, `PROTECTION_OR_SITE_PROCEDURE`, `OPERATOR_POLICY`, `ENGINEERING_POLICY`, `DEMO_DEFAULT`), `window_source_reference`, `source_version`, `approved_by`, `binding_vs_advisory`;
- advisory rationale and safe wording ("review", "inspect", "investigate").

### Priority hierarchy & rules:
``` text
P0 — Safety (MNT-PROT-001: immediate operator attention / follow site procedure)
P1 — Urgent inspection (MNT-THERM-002: suppressed on Tripura; MNT-FORE-003: central forecast limit crossing)
P2 — Planned action (MNT-PHASE-004: persistent phase imbalance)
P3 — Monitor (MNT-FORE-003: upper uncertainty band crossing; MNT-PF-005: downstream reactive review)
P4 — Data/model review (MNT-SENS-006: sensor fault; MNT-MODEL-007: model drift)
```

The maintenance engine shall:
- suppress dependent recommendations when prerequisite data is invalid (never suppress P0 protection);
- merge compatible recommendations sharing a `merge_key` with strictest compatible urgency;
- escalate incompatible actions for qualified human review;
- record operator feedback in an immutable, append-only ledger (`POST /v1/feedback`) preserving all historical telemetry and calculated records.

------------------------------------------------------------------------

# 14. MVP FactBundle

The MVP shall produce a versioned **FactBundle** as the authoritative
output consumed by user-facing surfaces.

It shall contain, as applicable:

-   current transformer state;
-   current measurements;
-   derived features;
-   thermal-model state;
-   prediction/uncertainty;
-   anomaly evidence;
-   anomaly episodes;
-   OTHI;
-   thermal exposure;
-   maintenance recommendations;
-   evidence grades;
-   provenance;
-   model/configuration/rule versions.

The dashboard and reports shall consume these facts rather than
independently recomputing decisions.

------------------------------------------------------------------------

# 15. MVP Backend/API Surface

The MVP shall expose the minimum API surface needed for the dashboard
and demo.

### Required API capabilities

``` text
POST   /v1/telemetry
POST   /v1/replay

GET    /v1/assets/{asset_id}/state
GET    /v1/assets/{asset_id}/history

GET    /v1/assets/{asset_id}/episodes
GET    /v1/assets/{asset_id}/recommendations

GET    /v1/assets/{asset_id}/health
GET    /v1/assets/{asset_id}/capabilities
GET    /v1/assets/{asset_id}/model-card

POST   /v1/assets/{asset_id}/scenario

GET    /v1/reports/...
POST   /v1/feedback
```

Exact request/response schemas shall follow the canonical contract and
be finalized during implementation.

The API shall never expose a direct transformer-control endpoint.

------------------------------------------------------------------------

# 16. MVP Frontend

The MVP dashboard shall contain the following core views, adhering strictly to transparent engineering representation.

## 16.0 UI honesty and display rules

The frontend must adhere to the following display and transparency rules:

-   **Value distinction:** Visibly distinguish between observed, derived, estimated, configured, unknown, and unavailable values (e.g., solid vs dashed styling, explicit badges).
-   **Missing rating:** When transformer nameplate rating is unavailable, display a relative load index based on the frozen training reference, never an invented percentage loading or per-unit claim.
-   **Demo defaults:** Any demonstration-only thresholds or assumptions must be conspicuously labelled `DEMO_DEFAULT`.
-   **Thermal fallback:** When the thermal model is not promoted, the UI must prominently display `THERMAL_MODEL: FALLBACK` and disable causal what-if controls.
-   **Conditional projection:** Two-hour projections must be explicitly titled conditional expected thermal behavior under declared assumptions, not failure or life predictions.
-   **Uncertainty coverage:** The empirical 90% projection band must always display its actual measured test-partition coverage percentage alongside the band.
-   **Color accessibility:** Critical visual states must never rely on color alone; always pair color with text labels, severity badges, and icons.

## 16.1 Overview

Must show:

-   transformer identity;
-   current operating state;
-   loading;
-   temperatures;
-   OTHI/status;
-   evidence grade;
-   active alerts;
-   active recommendations;
-   data-quality/capability status.

## 16.2 Twin analysis

Must show:

-   observed electrical/thermal trends;
-   expected thermal behavior when available;
-   residuals when available;
-   prediction band;
-   current operating context;
-   scenario comparison where supported.

## 16.3 Anomaly timeline

Must show:

-   active/recent episodes;
-   severity;
-   timeline;
-   evidence;
-   state transitions;
-   affected signals/domains;
-   recommendations.

## 16.4 Maintenance view

Must show:

-   recommendation;
-   priority;
-   action window;
-   evidence;
-   acknowledgement state.

## 16.5 Data/model card

Must expose:

-   data coverage;
-   capabilities;
-   model status;
-   calibration/test status;
-   important limitations.

## 16.6 Conditional 3D

A 3D component navigator is **not mandatory for MVP completion**.

It may be built only if:

-   the core backend/dashboard is stable;
-   it provides genuine component-level interaction;
-   it uses the same FactBundle;
-   it does not threaten the demo-critical path.

If those conditions are not met, the complete 2D dashboard ships without
the 3D layer.

------------------------------------------------------------------------

# 17. MVP Reporting

## Must build

### Transformer condition report

Contains:

-   current OTHI/status;
-   evidence grade;
-   main condition driver;
-   active recommendations;
-   relevant trends;
-   observed/expected thermal behavior;
-   thermal exposure;
-   anomaly summary;
-   data coverage;
-   limitations.

### Anomaly event report

Contains:

-   episode timeline;
-   evidence;
-   severity transitions;
-   observed/expected values where available;
-   recommendation;
-   acknowledgement/outcome;
-   provenance.

### Data/model card

Contains:

-   data sources;
-   signal coverage;
-   mapping/quality information;
-   capability manifest;
-   model/calibration status;
-   validation metrics;
-   known limitations.

## Formats

Must build:

-   PDF;
-   CSV;
-   JSON.

Excel is optional.

------------------------------------------------------------------------

# 18. MVP Feedback

The MVP shall support:

``` text
Alert / Recommendation
        ↓
User acknowledgement
        ↓
Inspection / action outcome
        ↓
Recorded feedback event
```

Feedback shall be auditable.

Feedback shall not silently modify model parameters or maintenance
rules.

------------------------------------------------------------------------

# 19. MVP Testing

The MVP is not complete without tests for:

## 19.1 Data

-   Tripura adapter ingestion;
-   alternate CPRI/final-dataset adapter fixture with different field names and/or units;
-   canonical output equivalence across both adapters;
-   valid records;
-   missing values;
-   invalid units;
-   invalid ranges;
-   duplicates;
-   conflicting duplicates;
-   gaps;
-   out-of-order records;
-   late events.

## 19.2 Thermal

-   irregular time intervals;
-   model calibration;
-   promotion gate;
-   fallback;
-   baseline comparison;
-   uncertainty coverage;
-   extrapolation detection.

## 19.3 Anomaly

-   synthetic spike, stuck, drift, load-step, and phase-imbalance scenarios;
-   unit/scale, timestamp, gap, duplicate/conflict, and direct protection/status fixtures;
-   engineering limits;
-   residual detection;
-   CUSUM calibration (decision limit h yielding <= 1 false warning episode per 7 asset-days and detecting 2-sigma drift within 1 hour / 4 samples) or explicit disablement;
-   episode transitions;
-   recovery;
-   direct critical evidence precedence.

## 19.4 OTHI

-   domain severity;
-   Max + secondary aggregation;
-   integer rounding;
-   status bands (Normal, Watch, Warning, Critical);
-   missing-domain behavior;
-   withholding;
-   evidence grade;
-   driving-domain identification.

## 19.5 Maintenance

-   trigger conditions;
-   priority;
-   action window;
-   suppression;
-   merging;
-   conflicts.

## 19.6 Replay

-   deterministic replay;
-   checkpoint restart;
-   late-event replay;
-   identical output hashes.

## 19.7 Scenario isolation and output consistency

-   what-if scenarios do not mutate live TwinState;
-   scenario execution is reproducible;
-   returning from a scenario leaves live state unchanged;
-   dashboard values match the authoritative FactBundle for measurements, OTHI, evidence grade, episodes, recommendations, and thermal projections;
-   no UI-side recomputation changes authoritative values.

## 19.8 End-to-end

At minimum:

``` text
CSV
 ↓
Canonical
 ↓
Quality
 ↓
Features
 ↓
TwinState
 ↓
Evidence
 ↓
Episode
 ↓
OTHI
 ↓
Maintenance
 ↓
FactBundle
 ↓
API
 ↓
Dashboard / Report
```

------------------------------------------------------------------------

# 20. MVP Demo Journey

The live demonstration should tell one coherent story.

## Stage 1 --- Start

Load the transformer replay.

Show:

-   asset identity;
-   current state;
-   data quality;
-   capability manifest.

## Stage 2 --- Normal operation

Show:

-   electrical trends;
-   loading;
-   ambient/oil temperature;
-   OTHI;
-   healthy/no-active-episode state.

## Stage 3 --- Abnormal behavior

Replay a naturally occurring or clearly labeled synthetic scenario.

Show:

-   abnormal evidence;
-   persistence;
-   episode formation;
-   severity transition.

## Stage 4 --- Explain

Open the episode.

Show:

-   observed values;
-   expected behavior where available;
-   evidence;
-   contributing domains;
-   evidence grade;
-   recommendation.

## Stage 5 --- Conditional prediction

If thermal model is promoted:

Show:

-   two-hour expected thermal trajectory;
-   uncertainty band;
-   scenario input;
-   threshold crossing if applicable.

If thermal model is not promoted:

Show:

``` text
THERMAL_MODEL: FALLBACK
```

Then demonstrate the fallback path rather than hiding it.

## Stage 6 --- Health and maintenance

Show:

-   OTHI;
-   driving domain;
-   recommendation;
-   priority;
-   action window.

## Stage 7 --- Auditability

Open the relevant provenance/model card/report.

Demonstrate that:

``` text
Output
 ↓
Evidence
 ↓
Source observation
 ↓
Version/configuration
```

can be traced.

------------------------------------------------------------------------

# 21. Demo-Critical Path

The following path has highest priority:

``` text
Data ingestion
    ↓
Canonical validation
    ↓
Replay
    ↓
TwinState
    ↓
Electrical + thermal features
    ↓
Thermal model OR explicit fallback
    ↓
Anomaly evidence
    ↓
Episodes
    ↓
OTHI
    ↓
Maintenance recommendation
    ↓
FactBundle
    ↓
Dashboard
```

Anything outside this path shall not threaten its completion.

------------------------------------------------------------------------

# 22. Conditional Features

The following are explicitly conditional rather than guaranteed MVP
features.

  -----------------------------------------------------------------------
  Feature                             Condition
  ----------------------------------- -----------------------------------
  Predictive thermal model            Must pass frozen promotion gate.

  Causal load/ambient what-if         Only if thermal model is promoted.

  Thermal residual CUSUM              Only if model and CUSUM calibration
                                      pass.

  Equivalent thermal ageing           Only if hot-spot/insulation
                                      prerequisites are verified.

  3D component navigator              Only if it passes the value gate
                                      without risking core functionality.

  MQTT adapter                        Optional if core integration is
                                      already stable.

  Drift-monitoring screen             Should-build if time permits.

  Constrained GenAI explanation       Optional and only after FactBundle
                                      validation.

  Excel report                        Optional convenience export.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 23. Explicitly Deferred

The following shall not enter the MVP implementation path:

-   Numeric RUL.
-   Failure probability.
-   General failure prediction.
-   Supervised transformer fault classifier.
-   Isolation Forest as a production anomaly path.
-   Deep neural forecasting.
-   Reinforcement learning.
-   Autonomous control.
-   Protection actuation.
-   Full SCADA/OPC UA/Modbus production integration.
-   Kafka/Kubernetes/microservices architecture.
-   Full CAD/CFD/FEM/EM simulation.
-   Decorative 3D.
-   Free-form LLM diagnostic chatbot.
-   LLM-generated maintenance rules.
-   LLM-generated numerical claims without fact validation.
-   Standards-compliance certification.

------------------------------------------------------------------------

# 24. MVP Completion Criteria

The MVP is considered complete only when:

### Data

-   [ ] Tripura dataset can be ingested through the canonical adapter.
-   [ ] Alternate CPRI/final-dataset adapter fixture with different field names and/or units produces the same canonical contract.
-   [ ] Downstream analytics run unchanged for both adapter fixtures.
-   [ ] Injector produces labelled spike, stuck, drift, load-step, and phase-imbalance scenarios; expected episodes form where the configured evidence path supports them.
-   [ ] Data-integrity fixtures exercise unit/scale errors, timestamp problems, gaps, duplicate/conflicting records, and direct protection/status events.
-   [ ] Raw and canonical records are preserved.
-   [ ] Quality validation works.
-   [ ] Replay works chronologically.
-   [ ] Late/conflicting/duplicate cases are handled.

### Twin

-   [ ] TwinState updates deterministically.
-   [ ] Checkpoint restore works.
-   [ ] Full replay reproduces outputs.

### Thermal

-   [ ] Thermal model calibration runs.
-   [ ] Promotion/fallback enforcement is implemented as a P0 gate.
-   [ ] Promotion decision is evidence-based.
-   [ ] Fallback mode works if promotion fails.
-   [ ] Predictive mode does not appear unless promoted.
-   [ ] Uncertainty is evaluated on held-out data.

### Anomaly

-   [ ] Engineering evidence works.
-   [ ] Thermal residual path works when enabled.
-   [ ] CUSUM is calibrated (decision limit h yielding <= 1 false warning episode per 7 asset-days and detecting 2-sigma drift within 4 samples) or explicitly disabled.
-   [ ] Episodes transition correctly.
-   [ ] Critical precedence works.

### Health

-   [ ] OTHI formula is implemented exactly with integer rounding.
-   [ ] Domain severities and status bands (Normal, Watch, Warning, Critical) are visible.
-   [ ] Evidence grade is visible.
-   [ ] Insufficient evidence withholds OTHI.

### Maintenance

-   [ ] Rules execute deterministically.
-   [ ] Priority and action windows are visible.
-   [ ] Evidence is linked.
-   [ ] Conflicts/suppression work.

### UI

-   [ ] Overview works.
-   [ ] Critical visual states do not rely on color alone.
-   [ ] Observed, derived, estimated, configured, unknown, and unavailable values are visibly distinguished where applicable.
-   [ ] Missing rating is shown as a relative load index rather than a percentage loading claim.
-   [ ] Demonstration-only thresholds are explicitly labelled `DEMO_DEFAULT`.
-   [ ] Conditional thermal projection and empirical interval coverage are labelled honestly, and `THERMAL_MODEL: FALLBACK` is visible in fallback mode.
-   [ ] Trends work.
-   [ ] Episode timeline works.
-   [ ] Maintenance view works.
-   [ ] Capability/fallback state is visible.
-   [ ] Model/data card works.

### Reports

-   [ ] Condition report works.
-   [ ] Anomaly report works.
-   [ ] Data/model card works.
-   [ ] JSON/CSV/PDF values agree with FactBundle.

### Deliverables

-   [ ] Architecture, methodology, assumptions, and user guide exist.
-   [ ] Reproducible source/execution instructions exist.
-   [ ] Short presentation and live/recorded demo artifact exist.

### Reproducibility

-   [ ] Scenario-isolation tests pass: what-if execution does not mutate live TwinState and repeated runs are reproducible.
-   [ ] Dashboard-vs-FactBundle consistency tests pass.
-   [ ] Versions/provenance are present.
-   [ ] Deterministic replay passes.
-   [ ] Core end-to-end test passes.

------------------------------------------------------------------------

# 25. MVP Priority Order

When implementation time becomes constrained, priority is:

## P0 --- Demo survival and safety gates

1. Data ingestion.
2. Canonical contract.
3. Quality handling.
4. Replay.
5. TwinState.
6. Electrical features.
7. Thermal observation.
8. Thermal promotion/fallback enforcement.
9. Anomaly/evidence pipeline.
10. Synthetic scenario and validation fixtures.
11. OTHI.
12. Maintenance rules.
13. Core dashboard.

## P1 --- Core predictive and validation value

14. Thermal calibration quality.
15. Uncertainty.
16. Two-hour conditional projection.
17. CUSUM.
18. Episode refinement.
19. CPRI/final-dataset adapter hardening.

## P2 --- Evidence and polish

20. Reports.
21. Feedback beyond the acknowledgement stub.
22. Model/data card refinement.
23. Checkpoint/late-event hardening beyond the minimum replay path.
24. Drift screen.

## P3 --- Optional enhancement

25. 3D.
26. MQTT.
27. Constrained GenAI.
28. Excel.

The priority order does not change the architecture. It only determines
implementation sequencing under time pressure. Promotion/fallback
enforcement is P0 and cannot be cut; model-promotion quality, uncertainty,
and the full predictive surface may degrade gracefully if their gates are
not satisfied.

------------------------------------------------------------------------

# 26. Required Hackathon Deliverables

The MVP scope includes the official problem-statement deliverables:

1. **Working Digital Twin software prototype.**
2. **Interactive dashboard** showing transformer loading/relative load, temperatures, health condition, alerts, and maintenance recommendations.
3. **Technical documentation** covering architecture, methodology, assumptions, and user guide.
4. **Complete source code** with reproducible execution instructions.
5. **Short presentation and live/recorded demonstration.**

These deliverables are part of MVP completion and may not be silently removed when implementation time is constrained.

---

# 27. MVP Claim Boundary

The final MVP may claim:

> A stateful Digital Twin prototype for operational transformer
> condition monitoring that processes chronological telemetry, maintains
> synchronized asset state, detects abnormal conditions, estimates an
> operational health index, conditionally projects expected thermal
> behavior, and generates traceable maintenance decision support.

The final MVP shall **not** claim:

-   transformer failure prediction;
-   numerical RUL;
-   guaranteed early-failure warning;
-   insulation-health diagnosis;
-   autonomous maintenance;
-   physical transformer control;
-   standards compliance;
-   universal applicability to all transformer designs.

All stronger claims require separate evidence and explicit review.

------------------------------------------------------------------------

# 28. Relationship to Implementation Plan

This MVP document freezes the **hackathon implementation boundary**.

The next document is the implementation plan. It shall convert this MVP
into:

-   repository structure;
-   implementation phases;
-   tasks;
-   dependencies;
-   ownership;
-   test gates;
-   daily milestones;
-   agent instructions;
-   integration order.

The implementation plan may choose how to build the MVP.

It may not silently expand or redesign the MVP.

------------------------------------------------------------------------

# 29. Final MVP Statement

The hackathon MVP is a **complete, auditable condition-monitoring
Digital Twin path**, not a collection of disconnected features.

Its minimum coherent loop is:

``` text
Operational data
      ↓
Validated canonical telemetry
      ↓
Stateful transformer twin
      ↓
Electrical + thermal understanding
      ↓
Evidence-based anomaly detection
      ↓
Operational Health Index
      ↓
Maintenance decision support
      ↓
Interactive explanation
      ↓
Traceable report / feedback
```

The MVP succeeds when this loop works reproducibly on the development
data and can be adapted to the final CPRI dataset through the same
canonical contract.
