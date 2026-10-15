# POST-AUDIT IMPLEMENTATION BRIEF — Methodology and Capability Changes

> [!NOTE]
> **HISTORICAL IMPLEMENTATION BRIEF**  
> This document records the post-audit methodology and runtime specification executed in earlier CPRI stabilization phases.  
> For the current execution roadmap and verified runtime status, consult:
> - [`GRIDPULSE_MASTER_EXECUTION_PLAN.md`](../GRIDPULSE_MASTER_EXECUTION_PLAN.md)
> - [`docs/execution/GRIDPULSE_EXECUTION_LOG.md`](execution/GRIDPULSE_EXECUTION_LOG.md)

**Project:** CPRI Track 2 — Digital Twin for Intelligent Health Monitoring and Predictive Maintenance  
**Date:** 2026-10-09  
**Status:** Completed & Integrated (Phases 1–8)  
**Scope:** Post-audit methodology and runtime changes.

---

## 1. Objective

Implement the justified post-audit refinements in the existing Digital Twin while preserving its design identity and frozen architecture. Be proactive: make the bounded changes specified below, add the necessary tests and documentation, and report any genuine blocker. Do not stop at a list of suggestions when the current repository can support a safe implementation.

This is not authorization for a new model family or an unrestricted redesign. Keep the deterministic state reducer, first-order grey-box thermal model, capability gates, residual/CUSUM qualification, episode handling, five-domain OTHI, evidence lineage and FIT → CAL → FREEZE → TEST governance.

### Explicitly excluded
- Integrating, mapping, training on, or calibrating against the replacement dataset.
- Removing Tripura paths/artifacts.
- Changing the UI design system or doing unrelated frontend redesign.
- Enabling a capability solely to improve a demo.
- Numeric operational RUL or failure-probability claims.
- Adding a new black-box anomaly model, new OTHI domain, or autonomous protection/control action.

## 2. Execution rules

1. Inspect the current checkout and loaded runtime before changing code. Record the commit and working-tree state.
2. Separate **verified current behaviour**, **reported historical claims**, and **proposed changes**. Do not assume reports prove runtime state.
3. Make changes in the batches below, with focused tests after each batch. Keep diffs small and reviewable.
4. Preserve the existing visual design. UI must reflect actual backend responses and capability state.
5. No fabricated readings, mock fallbacks, invented source semantics, hidden default values, or unsupported claims.
6. Do not bypass model qualification, relax identifiability bounds, use evaluation labels at runtime, or tune on TEST.
7. Preserve historical artifact/report identities. If a scientific method, input eligibility rule, threshold, or calibration changes, version the new policy/artifact and rerun the affected development/calibration/evaluation steps as appropriate. Do not relabel old results as if they came from the new method.
8. If a requested behaviour is unsupported by the backend, implement the smallest truthful backend contract change when it is within this brief. Otherwise report the exact blocker and proposed decision; do not fake it in the frontend.
9. **Keep the audit and dataset gates separate.** Do not start replacement-dataset integration during this implementation pass. Dataset integration may begin only after Batches 0–3 are implemented, tested, reviewed and explicitly accepted, and the separate dataset-handoff/schema/oracle audit in §11 is ready. Review Flag UI/workflow and RUL presentation are not global blockers for analytical dataset integration; they remain blockers only for enabling or claiming those specific features. The team may still choose to wait for the entire brief, but do not encode that as a technical dependency without evidence.
10. At completion, provide exact changed files, decisions made, tests/commands and actual results, remaining limitations, and a list of decisions requiring human approval.

---

## 3. Batch 0 — Baseline and evidence reconciliation (mandatory first)

### Work
- Run the post-merge backend tests from the repository root, including the full suite; run frontend typecheck/build and relevant Docker/runtime checks.
- Record commit, commands, environment, pass/fail/skip totals and failures. Do not report only a test count without the exact command.
- Inspect the **actual loaded** thermal artifact/model card/capability manifest and compare them with the state, telemetry, scenario and report APIs.
- Reconcile these reported conflicts using artifact/runtime evidence rather than prose:
  - Thermal parameters and driver: older records cite \(\tau=0.5\) h, \(\beta_0=1.0880\), \(\beta_1=2.8979\) on normalized RMS current; Phase 9.4 cites \(\tau=3.5\) h; Phase 10.5 cites \(\tau=2.5\) h and different coefficients/units.
  - Ambient availability: an audit reports ATI and valid oil/ambient pairs, while other records cite absent ambient.
  - Load reference: approximately 153.865 A versus 142.9 kVA as a reported FIT 95th percentile.
  - CUSUM: “evaluated” versus shadow-only/disabled/zeroed claims.
  - Uncertainty: 97.33% path coverage versus marginal-coverage wording.
  - OTHI: five named domains and integer policy score versus unsupported extra insulation/mechanical indices or inconsistent precision.
  - C3/C4 dependency wording: monolithic legacy descriptions versus capability-specific gates.
- Verify whether the thermal plausibility check has a universal hard override for \(T_o < T_a - 10^\circ C\). If so, correct it in Batch 2.
- Verify that no frontend or report claims measured symmetrical components, rated overload, continuous hot spot, qualified CUSUM, or RUL without supporting evidence.

### Acceptance
- A concise evidence ledger identifies each conflict, inspected source/artifact/API, final finding, and whether a code/documentation change is required.
- No coefficient or artifact is chosen merely because a report is newer.
- Baseline failures are distinguished from regressions introduced by later batches.

---

## 4. Batch 1 — R0 provenance and capability truthfulness

### Implement
- Ensure every runtime thermal artifact and model-card/report reference has a stable identity: artifact/version/hash where supported, dataset/asset identity, driver/reference and units, calibration/qualification status, and relevant policy version.
- Reconcile the runtime capability manifest and UI/API/report language with actual gates.
- Correct unsupported OTHI labels, score precision and domain claims. Retain the frozen five-domain max-plus-secondary policy, coefficient 0.20, declared policy bands, duplicate-family protections, coverage/withholding rules, anti-uplift and protection precedence.
- Make clear that OTHI is an **operational observed-condition policy summary**, not a complete transformer health index or proof of insulation/mechanical health.
- Clearly distinguish shadow/descriptive residuals from qualified operational anomaly evidence.
- Correct the CUSUM explanation: \(k=0.5\) is the conventional reference-value choice targeting a shift of roughly one residual standard deviation under the classical convention; do not silently change the configured \(k\).
- Clarify marginal interval coverage versus simultaneous sampled-path coverage, using the actual numerator/denominator and existing evaluation outputs. If the reported 97.33% cannot be reproduced or its definition is unclear, mark the claim unverified/remove it from current-facing claims rather than inventing a definition.
- Label injected/demo values and synthetic results clearly. Do not claim field validation, unseen-asset generalization, standards compliance or certification without evidence.

### Acceptance
- Artifact, capability, state API, dashboard and reports tell one consistent story.
- No new model fit is performed solely to correct wording. If the loaded artifact is not the one the historical report describes, preserve both identities and correct attribution.
- Add regression tests for corrected claims/contracts where practical.

---

## 5. Batch 2 — R1 signal semantics and R3 electrical applicability

### A. Measurement/source contract
For each signal used in analytics, preserve or add typed metadata where needed:
- Physical quantity, canonical unit, source/raw field, phase and electrical side, winding/component/location, measurement method, quality/status, timestamp meaning and temporal support.
- For a 30-minute record, identify snapshot, interval mean, interval RMS, min/max, or a meter-computed feature from higher-rate sampling. Do not assume logging interval equals measurement window.
- Distinguish top-oil from unspecified oil temperature; ambient; continuous analog winding indication; binary WTI alarm/trip contact; direct local winding probe; actual hot spot; bushing surface/contact temperature; oil-level gauge and compartment; vibration quantity/units/mounting/axis/RMS or peak/window; THD-V versus THD-I, phase, denominator and aggregation; true PF versus displacement PF; and magnitude unbalance versus sequence-component VUF.
- Unknown semantics may be retained in raw records and shown as unresolved, but must not enter dependent analytics or promote a capability.
- Do not make optional CPRI signals mandatory for unrelated capabilities. Ingest/display verified values first; qualify new analytics separately.

### B. Conditional P/Q/S/PF derivations
- Prefer compatible measured apparent power \(S\) and active power \(P\) for \(PF=P/S\), when the meter definitions, signs, timing and aggregation are compatible.
- Apply \(S=\sqrt{P^2+Q^2}\) only when the supplied P/Q convention supports the power triangle (for example, a documented compatible sinusoidal/vector definition). Do not apply it universally under harmonics/unbalance or incompatible three-phase aggregation.
- Keep observed and derived values distinct, with provenance and definitions.
- \(\sqrt{S^2-P^2}\) is a nonactive-power magnitude; do not label it signed reactive power without additional assumptions.
- Respect import/export and leading/lagging conventions. Negative PF is not automatically invalid.
- Derive S from P/PF only if PF is a compatible true ratio and is safely away from zero.
- Inconsistency checks require synchronized support and a tolerance justified by meter accuracy/rounding. Correlated P/Q/S/PF paths are one evidence family, not independent corroboration.
- Keep THD initially descriptive. Do not add a generic THD penalty, K-factor, derating or new OTHI domain from THD alone.
- Keep the current magnitude-unbalance metrics and label them precisely. Do not call them negative-sequence VUF unless verified sequence information or a documented compatible meter calculation is present.

### Acceptance
- Tests cover compatible sinusoidal cases, harmonic/distorted examples, unbalanced or incompatible definitions, signed power, low denominators, observed-versus-derived provenance, and missing/unknown semantics.
- Valid source data are not rejected merely because a universal power-triangle identity fails.
- No new OTHI domain or mandatory sensor requirement is introduced.

---

## 6. Batch 3 — R2 cadence-aware qualification and R4 thermal plausibility

### A. Actual-cadence protocol
The replacement dataset is out of scope here, but the code/configuration must support a future cadence being qualified correctly.

- Retain the existing exact-\(\Delta t\) exponential ODE. Do not replace the model family.
- Make forecast target times/horizon, eligible origins, interval alignment, gaps, warm-up, flatline detection, recovery and episode persistence explicit in elapsed time rather than relying on sample counts where that changes meaning.
- Retain the primary two-hour horizon. At 30-minute cadence, evaluate four supported endpoints; do not create fake observations to preserve an eight-step grid. Fine-grid interpolation may be visual only and must not be counted as additional observed/evaluation points.
- Prevent forecast targets from crossing data gaps or partition boundaries. Do not shift observations to pretend they occurred at target times. Exclude unsupported origins by a predeclared tolerance.
- Keep CUSUM per-observation; do **not** multiply increments by \(\Delta t\) as a shortcut. Define the required one-hour detection target in elapsed time and qualify false episodes per monitored asset-day and detection delay in minutes.
- Unknown intervals do not accrue confirmed persistence or recovery. A gap cannot prove normality or close an episode.
- Preserve current qualification gates. A future cadence must receive its own fit/calibration/evaluation and capability qualification; if a gate fails, withhold that capability rather than borrowing thresholds/bands.
- Separate forecast residual qualification from free-running runtime residual qualification. Good forecast MAE does not qualify an anomaly detector.
- Preserve FIT → CAL → FREEZE → TEST. The exact 60/20/20 policy remains unless a separately documented decision is approved; no TEST tuning.

### B. Thermal plausibility
- If the current code universally labels \(T_o < T_a - 10^\circ C\) physically impossible and forces bad quality/fallback, narrow that rule.
- Treat oil/ambient inversion as contextual plausibility evidence: ambient can rise faster than oil. Use sensor range, source semantics, response/measurement location, duration and operating context. Retain independent range/unit/sensor-quality checks.
- Do not infer sensor failure or physical fault from one inversion alone.

### Acceptance
- Irregular-dt, 15-/30-minute target matching, gaps, warm-up, elapsed-time persistence/recovery, and ambient-rise fixtures pass.
- Tests prove CUSUM cannot produce a qualified alarm while its qualification gate is disabled, and both positive/negative accumulators remain **exactly zero** across replay, checkpoint restore and process restart whenever CUSUM is disabled.
- No cadence-based capability is promoted without its own qualification evidence.

---

## 7. Batch 4 — Review Flag (implement a useful, deterministic workflow)

### Decision
Implement a small Review Flag workflow now, using existing advisories/episodes/evidence/feedback mechanisms where possible. Do not create a parallel detector unless the repository proves no reusable mechanism exists.

### Meaning
> **REVIEW FLAG — Observed behaviour warrants human review; the available evidence does not support a qualified anomaly conclusion.**

### Keep condition, observability, lifecycle and human workflow independent
1. **Condition:** normal / insufficient evidence / qualified anomaly / protection event.
2. **Observability:** current / degraded / stale / conflicting.
3. **Review lifecycle:** `OPEN` / `CLEARING` / `CLOSED` / `SUPERSEDED`.
4. **Human workflow:** `UNACKNOWLEDGED` / `ACKNOWLEDGED` / `DISMISSED`.

Acknowledgement or dismissal records a human workflow decision; it does **not** prove the underlying evidence has cleared. Lifecycle and workflow must not be collapsed into one status field. An asset may have stale thermal telemetry and a separate valid protection event. One must not overwrite the other.

### Initial trigger policy
- Reuse existing P4 sensor/model advisories and evidence IDs for the first release.
- Permit a review record for specific existing, evidence-backed conditions: sensor/source inconsistency, repeated engineering plausibility warnings, or an existing advisory that requires human investigation.
- Model qualification failure, out-of-envelope inputs, or general model-applicability concerns alone produce an **applicability/qualification notice**, not a behavioural Review Flag. A separate eligible behaviour condition may still warrant review.
- Missing/stale telemetry alone produces an **observability notice**, not a behaviour Review Flag.
- Keep automatic flags based solely on unqualified/shadow residuals disabled until the separate validation below passes.
- Do not infer a fault, probability, maintenance action or cause from a Review Flag.
- Acknowledge/resolve must never change OTHI, promote model capability, enable CUSUM, clear a protection event or rewrite underlying evidence.

### Lifecycle and provenance
- Give each review a deterministic `review_id`; deduplicate idempotently by asset + target + condition family. Update the existing active record rather than spamming duplicates.
- Use an idempotency key and expected revision/version for acknowledgement, dismissal, resolution and other feedback mutations so retries and stale clients cannot silently overwrite newer state.
- Record the feedback/control-stream position and logical cutoff used to derive the current review state. Replay determinism must include canonical telemetry **and recorded feedback/control events**, not telemetry alone.
- Use lifecycle transitions `OPEN → CLEARING → CLOSED`, or `SUPERSEDED` when a qualified anomaly takes over; reopen only under a documented deterministic recurrence rule. Track acknowledgement/dismissal separately as human workflow state.
- Preserve actor, rationale, supporting evidence IDs, policy/artifact version, creation/update event times and resolution reason.
- Gaps suspend persistence/recovery accumulation; they prove neither persistence nor recovery.
- When a qualified anomaly appears, link/supersede the matching behaviour review without deleting unrelated sensor/source reviews.
- Review state must replay deterministically and survive checkpoint/restart according to existing persistence conventions. **No reducer decision may depend on wall-clock `now()`**; use recorded event time and logical stream position.
- Use qualitative reason codes and evidence, not an uncalibrated confidence percentage.
- Expose the workflow through the existing API/dashboard using current visual design. Exports should include review state and provenance if those exports already carry comparable event records.

### Automatic residual-trigger promotion gate (not enabled by default)
Build an offline evaluation fixture/harness only if it fits existing test infrastructure. Test frozen candidate rules against normal load steps, ambient ramps, quantization, startup, gaps, source conflicts and independent simulated deviations. Report event coverage/delay, flags per eligible asset-day, benign eligible time flagged, duplicate fragmentation, overlap with qualified anomalies and behavior under missingness. Keep oracle labels evaluation-only. Do not tune on TEST.

Promotion is permitted only when all of the following are satisfied: (a) the candidate rule and threshold are selected using FIT/CAL only and versioned as a separate Review Flag policy artifact; (b) CAL has sufficient benign workload support for every asset where the rule would be enabled; (c) predefined challenge cases pass without unacceptable missed events, delay, duplicate fragmentation or missingness sensitivity; (d) the workload budget is met; and (e) the frozen candidate passes one sealed TEST evaluation, performed once and not used for tuning. This Review Flag policy gate is separate from thermal-model/CUSUM qualification; passing it does not promote either capability.

**Provisional project convention, not a universal statistical standard:** require at least **21 eligible benign CAL asset-days per enabled asset** and no more than **1 unmatched Review Flag occurrence per 7 eligible asset-days**, or a stricter workload budget explicitly approved by the team. Report the denominator and eligibility rules. If support is insufficient or any gate fails, keep automatic residual-triggered flags disabled and retain manual/advisory-based review only.

### Acceptance
- Tests cover deduplication, acknowledgement, resolution/reopening, gaps, replay determinism, persistence, relation to qualified anomalies/protection, and OTHI/capability invariance.
- UI/API do not conflate observability notices with behavioural Review Flags.
- The existing design is preserved.

---

## 8. Batch 5 — Exposure and RUL decision

### A. Observed top-oil exposure
Inspect before implementing; expose/repair only what is actually missing.

- Provide peak observed top-oil temperature, duration in explicitly configured temperature bands, degree-hours over a named window, supported integration hours and wall-clock coverage where the backend can support them.
- Use supported intervals only. Never carry the last reading indefinitely through gaps or imply unobserved peaks were captured.
- Label threshold source/configuration and temperature semantics. Do not describe configured thresholds as universal end-of-life limits.
- Direct observed exposure must not be globally blocked merely because the predictive grey-box model is unpromoted, if the exposure prerequisites are independently met.

Freeze and document one numerical convention before exposing exposure metrics. **Prefer piecewise-linear interpolation between valid endpoint observations** when both endpoints, elapsed time and signal semantics support it; integrate only the supported portion of each interval. If the implementation instead uses sample-hold, label it explicitly as sample-hold. Do not silently switch conventions between reports or assets.

For a configured threshold \(T_b\), the sample-hold degree-hour approximation is:

\[
D_b=\sum_{\text{supported intervals}}\max(T_{o,i}-T_b,0)\Delta t_i
\]

For piecewise-linear endpoints, integrate the positive part of the line segment relative to \(T_b\), including a threshold crossing where applicable. Interval means alone do not establish time above a threshold or nonlinear ageing within the interval unless a defensible within-window assumption is explicitly declared. These remain sampled-data estimates, not reconstruction of continuous exposure.

### B. Equivalent thermal ageing
Do **not** enable it merely because top-oil modelling works.
- Require a credible direct hot-spot measurement or independently qualified hot-spot estimate.
- Require verified insulation profile/class and a reviewed, edition-pinned formulation and constants.
- Keep direct hot spot and model-estimated hot spot as distinct source/capability paths.
- Use supported intervals only; report equivalent ageing hours, supported integration time and wall-clock coverage separately.
- Never convert a binary WTI contact into temperature or infer hot spot from top-oil alone.
- Do not call equivalent ageing hours “remaining life.”
- Verify the applicable IEEE/IEC edition and exact implemented equation before enabling. A citation to a standard is not proof of compliance.
- Add a gating regression: a credible direct-hot-spot path may enable ageing when C3/model-derived hot-spot capability is disabled, provided all independent ageing prerequisites pass; conversely, promoting C3 alone must **not** enable model-derived hot-spot ageing without the separate ageing prerequisites.

### C. RUL decision
**Do not implement a numeric operational RUL countdown in the current evidence state.** Be proactive by implementing a truthful capability state and roadmap, not a fake number.

- Distinguish: observed thermal exposure; equivalent ageing hours; average ageing rate over supported periods; conditional time-to-limit under an explicit scenario; synthetic time-to-injected-event; actual transformer/component remaining useful life.
- These are not interchangeable.
- Review whether the existing API/UI has an RUL placeholder. If so, show a clear unavailable/not-qualified state and the exact blocker rather than a fabricated value.
- Record the RUL capability as `not_qualified`/unavailable using existing conventions, with a reason such as “No validated initial degradation state and life-outcome evidence for operational RUL.”
- A future RUL study must first select a specific target and method. Fleet survival modelling needs relevant failure/maintenance/censoring histories; degradation-trajectory modelling needs longitudinal degradation state and initial condition. Requirements are **method-specific**—do not claim every possible RUL approach needs both degradation trajectories and failure outcomes, or every diagnostic sensor.
- Synthetic time-to-event may be used only as an explicitly offline benchmark, not presented as real-world RUL.
- Do not emit failure probabilities or confident-looking countdowns.

### Acceptance
- Hand-calculated tests cover irregular intervals, missing samples, gaps, coverage and no extrapolation through missing periods.
- Binary WTI cannot feed continuous exposure/ageing.
- RUL is either honestly unavailable or shown only for a separately qualified, well-defined target; current project must not invent that qualification.

---

## 9. Batch 6 — Uncertainty, residual diagnostics and evaluation scope

### Implement now
- Correct the definition/reporting of uncertainty coverage using actual stored results. Separate marginal horizon coverage from simultaneous sampled-path coverage, interval width, usable calibration blocks/origins and supported monitoring duration.
- Do not claim continuous-time coverage, guaranteed coverage under arbitrary dependence/shift, or that an 80–98% acceptance band itself establishes nominal 90% coverage.
- Keep empirical interval terminology unless the exact implemented algorithm and assumptions justify a stronger formal claim.
- Ensure forecast-origin-reset residuals and free-running runtime residuals are not treated as the same sequence unless verified.
- Add FIT/CAL diagnostics for residual bias, spread, autocorrelation and supported operating regimes where feasible.

### Conditional only
- Do not add regime-stratified residual scaling unless permitted FIT/CAL diagnostics show material regime-dependent residual behavior and sufficient sample support. Compare a small frozen stratification against robust global MAD; preserve a global fallback or withhold unsupported strata. Never auto-recenter online in a way that could hide a fault.
- No EWMA, PCA/Hotelling, Mahalanobis, Isolation Forest, autoencoder or Bayesian-model addition is authorized by this brief.

### Synthetic evaluation governance
- Preserve chronological FIT/CAL/FREEZE/TEST and one final TEST evaluation.
- Report per-asset, macro and worst-asset metrics; include monitoring duration, event delay in elapsed time, false episodes per asset-day, uncertainty support and regime coverage where relevant.
- Distinguish software verification, parameter recovery, synthetic scenario sensitivity and field validation.
- Do not claim unseen-asset generalization from chronological splits on the same assets.
- Keep oracle labels, latent parameters and scenario IDs out of runtime features, state transitions and capability gates.

---

## 10. Required tests / evidence checklist

Add or update tests for the applicable items:
- [ ] Artifact identity and capability/UI/API consistency.
- [ ] Disabled CUSUM cannot issue qualified anomaly output; both accumulators remain exactly zero across replay, checkpoint restore and restart while disabled.
- [ ] P/Q/S/PF compatible and incompatible definitions, signs and provenance.
- [ ] Unknown signal semantics are retained but cannot promote dependent analytics.
- [ ] Thermal ambient-rise inversion is contextual rather than universally impossible.
- [ ] Irregular timestamp and actual-dt forecast support.
- [ ] 2-hour horizon evaluated on supported endpoints without invented data.
- [ ] Gap handling for detector persistence, recovery, episode lifecycle and exposure.
- [ ] Review Flag deterministic ID/idempotency/revision handling, separate lifecycle and human workflow, feedback-stream replay, clearing/reopening/persistence.
- [ ] Review Flag does not change OTHI, capability, qualified anomaly or protection state.
- [ ] Observed exposure calculations match hand-calculated fixtures for the frozen piecewise-linear or explicitly labelled sample-hold convention; threshold crossings, interval means, gaps and coverage are tested.
- [ ] Direct-hot-spot ageing gate is independent of C3 promotion; C3 alone cannot enable model-derived hot-spot ageing.
- [ ] WTI contact cannot become a continuous temperature.
- [ ] Marginal/path uncertainty metrics are named and calculated consistently.
- [ ] Runtime never consumes oracle labels/latent truth.
- [ ] Existing regression suite, frontend typecheck/build, and relevant Docker/runtime checks.

Only mark a test passed when the command has actually run and the output is available.

## 11. Delivery sequence, dataset handoff and review gates

Work in this order for the current audit pass:
1. Baseline and evidence reconciliation.
2. Provenance/capability truthfulness.
3. Signal semantics and conditional electrical calculations.
4. Cadence-aware qualification scaffolding and thermal plausibility correction.
5. Review Flag workflow.
6. Observed exposure, ageing gates and honest RUL state.
7. Uncertainty/evaluation reporting and full regression run.

### Separate mandatory gate before replacement-dataset integration

Dataset integration is **not part of this implementation pass**. Before a separate integration task begins, prepare and review a dataset-handoff contract that includes all of the following:
- [ ] Versioned schema and deterministic schema/version hash, including units, source semantics, timestamp/temporal support, quality fields and mapping provenance.
- [ ] Explicit runtime allowlist for columns/features that runtime code may consume; oracle labels, latent truth, scenario IDs and future/outcome columns must be excluded from runtime feature/state/capability paths.
- [ ] FIT/CAL/TEST exposure records identifying asset/time ranges, eligibility/exclusions, event and benign workload support, and the frozen split/policy identities.
- [ ] Truth-column permutation tests: permuting or changing oracle/truth-only columns must not change runtime features, state transitions, capability decisions or predictions. Add equivalent tests for schema extras and unexpected columns.
- [ ] Explicit mapping review for unresolved semantics; unknown remains unknown and cannot silently qualify dependent analytics.

The replacement dataset may be integrated only after Batches 0–3 and this handoff contract are accepted. Then dataset-specific FIT/CAL/FREEZE/TEST, cadence qualification and calibration are a **new, separately reviewed phase**. Never reuse Tripura parameters, CUSUM thresholds, residual scales, uncertainty bands or qualification status without fresh evidence. Review Flag UI/workflow and RUL presentation are not prerequisites for starting that separate analytical integration phase; they remain prerequisites for enabling or claiming those respective features. The team may impose a stricter project-wide gate explicitly, but the implementation must not imply a scientific dependency that has not been established.

After the implementation:
- Produce a concise decision log mapping each audit recommendation (R0–R7 and related Review Flag/RUL decisions) to files changed, tests and outcomes.
- List any item not implemented and the precise reason.
- List any methodology change that requires a new artifact/recalibration or invalidates a historical claim.
- Provide screenshots only if requested; do not redesign.
- Stop after the audit implementation and regression evidence. Do not integrate the replacement dataset in this pass. Request explicit team acceptance of Batches 0–3 plus the dataset-handoff contract before starting that separate phase.

## 12. Required final report format

1. Commit before/after and working-tree state.
2. Summary of implemented decisions by batch.
3. Exact files changed and why.
4. Commands run and actual pass/fail/skip results.
5. Runtime/API evidence for capability states.
6. Claims corrected or withdrawn.
7. New artifacts/policy versions and whether recalibration/evaluation is required.
8. Deferred items and concrete blockers.
9. Explicit statement: **replacement dataset integration has not started**.
10. Acceptance questions for the team, if any.

**Implementation stance:** proactive within the defined scope; conservative only where evidence or qualification gates require it. Do not confuse caution with inaction, and do not confuse a plausible feature with a validated capability.
