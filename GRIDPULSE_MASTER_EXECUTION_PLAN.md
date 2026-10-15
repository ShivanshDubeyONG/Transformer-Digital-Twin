# GridPulse Master Execution Plan
## POWERNext-AI Hackathon 2026 — Track 2

> [!NOTE]
> **MASTER EXECUTION STATUS: PHASES 1–8 COMPLETE & VERIFIED**  
> Phases 1 through 8 have been sequentially authorized, executed, and verified:
> - **Phase 1:** PR Integration & Baseline Verification (**PASS**)
> - **Phase 2:** Backend Stabilization & Bug Fixes (**PASS**, 9/9 regression tests)
> - **Phase 3:** Candidate Dataset Audit & Quarantined Extraction (**PASS**)
> - **Phase 4:** Candidate Dataset Adaptation & Extra Domains (**PASS**, 87/87 tests)
> - **Phase 5:** Model Fitting & Validation Infrastructure (**PASS**)
> - **Phase 6:** Independent Holdout TEST Evaluation & Controlled Trial (**PASS**, DT-01 Promoted; DT-02..04 Gated)
> - **Phase 7:** Multi-Dataset Cutover & Fallback Mechanism (**PASS**, bidirectional rollback verified)
> - **Phase 8:** Frontend/Backend Integration & Telemetry Honesty (**PASS**, 81/81 targeted tests, Docker e2e)  
> For the complete chronological log with verified SHA-256 hashes, consult [`docs/execution/GRIDPULSE_EXECUTION_LOG.md`](docs/execution/GRIDPULSE_EXECUTION_LOG.md).

**Purpose:** Single source of execution order for PR integration, backend stabilization, candidate dataset adaptation, domain enhancements, model qualification, frontend/backend integration, and final verification.

---

# 1. Project State and Non-Negotiable Rules

## 1.1 Current dataset status

- The active baseline is the existing CPRI dataset, believed to be `cpri_datasetv.1.2`. Verify its exact identity from repository configuration, manifests, and artifacts.
- The new candidate archive is exactly **`gridpulse_synthetic_v1.zip`**.
- The name `dataset_syn` was a typo and is not part of the plan. Do not create a dataset workflow under that name.
- Keep the current CPRI dataset, model/checkpoint artifacts, configuration, hashes, and evaluation results intact while the candidate is being adapted and evaluated.
- Do not activate or promote the new dataset merely because it extracts, parses, trains, or passes software tests.
- Promotion and active-dataset cutover require the promotion criteria in Phase 6 and explicit human approval.
- Once a candidate has been approved and cutover verified, retire the prior dataset from active use but preserve it as an immutable archive and rollback baseline.
- Tripura is no longer part of the active execution plan. Do not treat it as the current dataset, migration target, or active calibration source.

## 1.2 Architecture and governance

Read and follow the current repository versions of:

- `FINAL_ARCHITECTURE_DECISIONS.md`
- `PRINCIPLES.md`
- `CODING_RULES.md`
- `SRS.md`
- `MVP.md`
- `IMPLEMENTATION_PLAN.md`
- `BACKEND_STABILIZATION_PROPOSALS.md`
- `GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md`

If a filename differs slightly, locate the matching document and record the exact name. Do not create duplicate files merely because a name differs.

Authority:
1. `FINAL_ARCHITECTURE_DECISIONS.md` governs frozen architecture decisions.
2. `PRINCIPLES.md` and `CODING_RULES.md` govern engineering and scientific discipline.
3. `BACKEND_STABILIZATION_PROPOSALS.md` specifies proposed existing-backend fixes, after verification against current source.
4. `GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md` specifies candidate-dataset and additional domain work, subject to the frozen architecture.
5. This document defines the overall phase order. It does not silently override the documents above.

If documents conflict, identify the exact conflict and its consequences. Ask for a human decision before changing a frozen architecture choice.

## 1.3 Execution rules

- This is an existing project. Do not rewrite the platform or introduce an unrelated architecture.
- Inspect the current repository before applying old audit claims or line references.
- Preserve user changes and uncommitted work. Never use destructive cleanup commands to force a clean tree.
- Do not delete, overwrite, or silently regenerate the active dataset, candidate archive, checkpoints, models, evaluation outputs, or user files.
- Keep dataset-specific mappings in adapters and asset profiles rather than scattering special cases throughout analytics.
- Preserve canonical schemas and frontend-facing API contracts unless a change is necessary and explicitly justified.
- Never invent sensor semantics, physical thresholds, equipment specifications, validation results, or test outcomes.
- Distinguish observations, assumptions, synthetic ground truth, model-derived evidence, and validated conclusions.
- Do not use TEST results to tune the same model and then claim independent validation.
- Do not weaken or delete tests just to obtain a green build.
- Do not commit, push, publish, release, or merge into shared `main` unless explicitly authorized.
- At each phase gate, report actual evidence rather than merely saying the phase is complete.
- Routine implementation should continue through the authorized phases without repeatedly asking for permission. Stop only at the specified gates or when a real ambiguity prevents safe progress.

---

# PHASE 1 — PR INTEGRATION AND BASELINE

**Authorized in the current run.**

## 1.1 Inspect Git and workspace state

Record:

- Repository root and active branch.
- Current HEAD SHA and working-tree status.
- Configured remotes.
- Latest local and remote `main` SHAs.
- Incoming PR number, source branch, target branch, head SHA, and status.
- Uncommitted changes, untracked files, stashes, and possible conflicts.
- Existing backend/frontend test and build commands.
- Presence and exact names of the project instruction files and candidate ZIP.

Preserve existing user changes. If the current state could be overwritten, take a safe non-destructive path before continuing.

## 1.2 Fetch and inspect the incoming PR

Fetch the latest remote metadata and PR using the configured hosting provider's supported workflow. Verify the repository and target branch.

Review the complete diff for:

- Frontend implementation and routing.
- API clients, schemas, and response assumptions.
- Authentication, configuration, and CORS.
- Dependencies and lockfiles.
- Tests and build configuration.
- File deletions, migrations, secrets, unrelated changes, and architecture conflicts.

## 1.3 Synchronize with the latest `main`

Integrate the PR into an appropriate working branch based on the repository's existing workflow.

- Ensure the working branch contains the latest intended target `main` and the PR changes.
- Safely update a stale PR branch if necessary.
- Do not rewrite shared history without authorization.
- Resolve clear conflicts while preserving intended behavior.
- If a conflict requires an ambiguous architecture/product decision, document it and avoid silently choosing.
- Verify the resulting branch ancestry and file state.

Do not complete the PR or push any branch without authorization.

## 1.4 Establish pre-fix baseline

Before modifying application code:

- Run existing relevant tests and builds where the environment permits.
- Record existing failures separately from new failures.
- Verify startup/health-check behavior and inspect Docker Compose, dependencies, API schemas, and frontend API clients.
- Identify the exact active CPRI dataset, paths, hashes, checkpoint/model artifacts, and configuration selecting them. The expected identifier is `cpri_datasetv.1.2`, but verify rather than assume.
- Do not extract or activate `gridpulse_synthetic_v1.zip` in this phase.
- Record SHAs, commands, results, and notable baseline issues in the repository's existing execution log or create `docs/execution/GRIDPULSE_EXECUTION_LOG.md` if appropriate.

### Phase 1 exit criteria

- PR and latest target `main` are integrated in the working branch.
- No unresolved merge conflict remains that blocks safe implementation.
- Baseline test results and dataset identity are recorded.
- The active CPRI baseline and artifacts remain intact.

**Do not stop after Phase 1 in the current run. Proceed directly to Phase 2.**

---

# PHASE 2 — BACKEND STABILIZATION

**Authorized in the current run.**

Read `BACKEND_STABILIZATION_PROPOSALS.md` completely. Verify every proposed defect against the current code. Historical line numbers, test counts, and claims are not automatically current facts.

Implement fixes incrementally and add regression tests.

## 2.1 Thermal residual evidence wiring

- Verify thermal model output is passed from the reducer into the anomaly engine.
- Restore the connection if missing.
- Preserve the distinction between direct physical thermal-limit evidence and model-derived residual/deviation evidence.
- Qualified models may produce appropriately qualified residual evidence.
- Unqualified models remain descriptive/shadow-only according to the frozen architecture.
- Add tests for qualified and unqualified cases.

## 2.2 Protection-trip lifecycle

- Preserve immediate critical handling for a valid direct protection trip.
- Prevent a historical trip from forcing every later state to remain critical indefinitely.
- Do not clear a trip merely because a breaker recloses or a signal returns to normal.
- Implement auditable resolution/reset semantics consistent with existing architecture and authorization.
- Preserve historical trip evidence.
- Test activation, persistence, valid reset/resolution, recovery, and deterministic replay.

## 2.3 Direct thermal limits versus model qualification

- Valid direct physical thermal-limit evidence must not be suppressed solely because a predictive model is unqualified.
- Separate direct-limit advisory handling from model-derived residual handling where necessary.
- Preserve applicable verified limits and signal-quality checks.
- Do not invent thresholds.
- Test direct-limit advisories on unqualified assets while model-derived claims remain gated.

## 2.4 Advisory and feedback lifecycle

- Verify distinct behavior for `ACKNOWLEDGE`, `DISMISS`, and `RESOLVE`.
- Acknowledgement must not imply resolution.
- Do not retain advisories forever after underlying evidence genuinely clears.
- Follow existing episode persistence, recovery, and closure rules.
- Preserve history.
- Test active evidence, condition clearing, resolution, recurrence, and replay.

## 2.5 Canonical signal mappings

Audit adapter outputs and downstream consumers. Verify reported mismatches, including:

- `oil_level_pct` versus `oil_level_percent`.
- Phase-current naming.
- Phase-voltage naming.
- Domain freshness and OTHI mappings.

Fix confirmed mismatches at the appropriate adapter/canonical boundary. Verify units, phase semantics, timestamps, quality, provenance, and stale/missing handling. Missing or stale data must not become healthy data.

## 2.6 Asset-specific voltage configuration

- Use verified asset-profile nominal voltage and correct phase-to-neutral versus line-to-line semantics.
- Do not blindly replace one global voltage constant with another.
- Preserve current CPRI compatibility.
- Prepare the architecture to accept candidate voltage semantics through the adapter and asset profile.
- Test normal, under/overvoltage, missing metadata, and unsupported semantics.

## 2.7 Sensor plausibility

- Make flatline detection aware of measurement resolution, signal type, cadence, gaps, and operating conditions.
- Do not flag ordinary quantized temperature equilibrium as a stuck sensor.
- Ensure long intervals do not hide implausible measurement jumps.
- Do not treat a proposed absolute step threshold such as 10°C as a universal physical constant. Justify and test any retained threshold.
- Test normal flat periods, actual stuck sensors, gaps, missing samples, and abrupt implausible values.

## 2.8 Pressure capability boundary

The stabilization report says pressure monitoring is currently absent. Do not claim this capability is implemented as part of unrelated bug fixes. Keep pressure-domain implementation for Phase 5. During Phase 2, ensure unsupported pressure fields do not break existing event/schema handling.

## 2.9 Regression verification

After each logical fix, run targeted tests. After all fixes:

- Run the full backend suite.
- Run frontend tests and production build.
- Run configured lint/type/static checks.
- Verify startup and health checks.
- Verify API/OpenAPI contracts and frontend compatibility.
- Inspect the final diff for accidental deletions, weakened tests, unrelated refactors, and unintended contract changes.

Report actual commands and counts. If failures occur, identify whether they were pre-existing or introduced by the changes, fix regressions, and rerun relevant suites. Do not conceal environmental blockers.

### Phase 2 exit criteria

- Each stabilization proposal is marked `confirmed and fixed`, `not reproduced`, or `blocked`, with evidence.
- Regression tests exist for confirmed fixes.
- Relevant backend/frontend checks have been run.
- Remaining failures and blockers are documented.
- No unauthorized push/commit occurred.
- The active CPRI dataset, checkpoint, and model artifacts remain intact.

## CURRENT RUN STOP GATE

Complete **both Phase 1 and Phase 2** in the same run. Then produce the Phase 1/2 handoff report and stop for human review.

Do not execute Phases 3 onward in this run.

---

# PHASE 3 — CANDIDATE ARCHIVE AUDIT AND SAFE EXTRACTION

**Future phase — requires explicit authorization after review of Phase 1/2.**

The candidate is exactly `gridpulse_synthetic_v1.zip`. Do not use the erroneous name `dataset_syn`.

Before extraction:

1. Confirm and record the active CPRI dataset identity, file hashes, checkpoint/model artifacts, configuration, and evaluation results.
2. Verify the candidate ZIP hash and inspect its file listing.
3. Inspect nested archives, paths, manifests, methodology, scenario reports, source register, generator, licenses, and data dictionaries.
4. Reject unsafe archive paths and preserve the original ZIP unchanged.
5. Extract to an isolated candidate directory following repository conventions, for example `data/candidates/gridpulse_synthetic_v1/`.
6. Never overwrite the active processed-data directory or existing checkpoint.
7. Verify actual row/column counts, timestamps, cadence, asset IDs, units, missing values, duplicates, scenario labels, and split boundaries against the package documentation.
8. Investigate hash discrepancies and conflicting packaged/generated artifacts without silently regenerating or replacing files.
9. Record prior exposure to TEST labels, plots, metrics, and scenarios.

### Phase 3 gate

The candidate is safely extracted, its identity and semantics are documented, and the current CPRI baseline is unchanged.

---

# PHASE 4 — ADAPT `gridpulse_synthetic_v1.zip` TO THE CANONICAL PIPELINE

**Future phase — requires explicit authorization.**

Use the existing adapter architecture; do not create a separate analytics pipeline.

- Map actual source columns to canonical events and measurements.
- Preserve timestamps, units, quality, provenance, ordering, and asset identity.
- Use existing unit canonicalization.
- Keep source-specific names inside the adapter.
- Verify construction metadata and sensor applicability.
- Preserve the CPRI adapter and behavior.
- Test sorting, duplicates, gaps, invalid values, asset isolation, replay determinism, stable state hashes, and checkpoint/restart behavior.
- Ensure candidate processing cannot contaminate active CPRI state.

### Phase 4 gate

Both datasets can be ingested through the same canonical architecture, and candidate replay is deterministic without switching the active dataset.

---

# PHASE 5 — IMPLEMENT EXTRA DOMAIN CAPABILITIES

**Future phase — requires explicit authorization.**

Follow `GRIDPULSE_DATASET_SYN_ADAPTATION_AND_EXTRA_DOMAIN_SCOPE.md` and verify every field against the actual candidate package.

## 5.1 Oil-level trend and suspected-leak monitoring

- Map raw oil level, reference level/temperature, corrected level, trend, tank construction, and gauge type where present.
- Distinguish observed readings from supplied derived values and trends; preserve derivation provenance.
- Implement sensor- and construction-aware trend monitoring for applicable assets.
- Detect persistent declining corrected-level trends as suspected oil loss requiring review, with quality, freshness, persistence, and intervention handling.
- Distinguish low-level alarms, suspected trends, maintenance top-ups, stuck gauges, and missing/stale data.
- Do not interpret a top-up as unexplained recovery.
- Do not treat a flat gauge as proof of no leak.
- Emit traceable evidence and route it through the existing episode/review/advisory lifecycle.
- Test normal temperature-related movement, slow leak, top-up, stuck gauge, missing data, and false-positive controls.

A declining trend does not prove a physical leak. Synthetic labels are evaluation truth, not runtime detector inputs.

## 5.2 Tank-pressure monitoring

- Map the actual pressure signal and verify gauge versus absolute pressure semantics and units.
- Enable pressure monitoring only for assets with a verified applicable sensor and construction.
- Implement configured pressure plausibility/condition checks only where semantics and limits are defensible.
- Treat pressure-relief contact as a separate direct event if its schema is verified.
- Keep pressure and oil-level evidence separate unless an explicit corroboration rule is justified.
- Test normal/abnormal pressure, contact activation, missing/stale values, out-of-range readings, and unsupported asset designs.

Never apply sealed-tank thresholds to conservator designs. Pressure deviation alone does not prove a leak or internal fault. If semantics or limits are not defensible, keep the capability descriptive/review-only and expose the reason.

## 5.3 Electrical stress and protection parameters

- Validate asset ratings, voltage semantics, impedance, electrical side, units, and provenance.
- Implement deterministic prospective short-circuit reference calculations only when necessary inputs are verified.
- Keep measurements, derived values, and scenario assumptions distinct.
- Integrate simulated protection/breaker events through the existing event/evidence lifecycle.
- Test missing/invalid inputs, asset-specific parameters, activation, and recovery.

Do not claim a complete IEC 60909 study, protection-coordination result, or proven transformer withstand capability. Thirty-minute telemetry cannot reconstruct sub-cycle fault waveforms.

## 5.4 Construction-aware capability and evidence

- Extend asset profiles/capability manifests for construction, sensor applicability, and per-domain availability.
- Use existing capability states and reason codes.
- Missing sensors must mean unavailable/unknown, not healthy.
- Preserve the frozen OTHI formula and evidence/persistence rules unless explicitly approved.
- Route new outputs through the shared versioned `FactBundle`.
- Do not duplicate analytics in the frontend or reports.

### Phase 5 gate

Oil, pressure, electrical-stress, protection-event, and construction-aware behavior is implemented to the defensible level, with positive and negative tests.

---

# PHASE 6 — FIT, CALIBRATE, EVALUATE, AND REQUEST PROMOTION

**Future phase — requires explicit authorization.**

Respect the frozen chronological FIT → CAL → FREEZE → TEST discipline and embargo rules.

- FIT: model/driver/parameter fitting using permitted FIT data.
- CAL: threshold and uncertainty calibration using permitted CAL data.
- FREEZE: freeze model, thresholds, adapter, rules, configuration, software/artifact hashes.
- TEST: one evaluation of the frozen configuration; no tuning against TEST.

Do not change frozen model families, OTHI formula/weights, or CUSUM limits without explicit approval. CUSUM must remain disabled for operational warnings unless the established independent validation criteria are satisfied.

Report, where applicable:

- Forecast performance versus baseline.
- Per-asset and aggregate metrics.
- Residual bias and stability.
- Detector precision/recall where labels support it.
- False warning episodes per eligible asset-day.
- Detection delay and scenario coverage.
- Missing-data behavior and capability abstention.
- Deterministic replay and reproducibility hashes.
- TEST exposure status and limitations.

If promotion criteria are not already defined, propose defensible criteria and request approval before using them as a gate.

Produce a report recommending `PROMOTE`, `DO_NOT_PROMOTE`, or `INSUFFICIENT_EVIDENCE`. Do not automatically switch the active dataset.

### Phase 6 gate

Promotion evidence is reproducible and documented. Explicit human approval is obtained before active-dataset cutover.

---

# PHASE 7 — APPROVED DATASET CUTOVER AND FALLBACK

**Future phase — requires explicit promotion approval.**

After criteria pass and approval is granted:

- Switch active configuration to the promoted candidate.
- Verify model/checkpoint compatibility with the promoted dataset and configuration.
- Preserve the old CPRI data, checkpoint, configuration, hashes, and evaluation results.
- Document and test rollback.
- Verify candidate activation and restoration of the prior baseline.

Retire the old dataset from active use only after successful cutover verification. Preserve its archive; do not delete it.

---

# PHASE 8 — FRONTEND/BACKEND INTEGRATION

**Future phase — requires explicit authorization after backend contracts and capabilities stabilize.**

- Verify API base URLs, authentication, CORS, request/response schemas, and error handling.
- Ensure the dashboard uses the backend's actual `FactBundle`, evidence, episodes, recommendations, and capability manifest.
- Display capability-disabled reason codes instead of pretending unsupported functionality is available.
- Show oil/pressure fields only for applicable assets, including missing/stale states.
- Label electrical-stress outputs as derived reference calculations with assumptions.
- Verify distinct acknowledgement, dismissal, and resolution behavior.
- Ensure UI and generated reports display the same underlying facts.
- Update generated API types and contract tests according to repository conventions.
- Do not hardcode demo telemetry or duplicate backend analytics in frontend code.

---

# PHASE 9 — FULL-SYSTEM VERIFICATION

**Future phase — requires explicit authorization.**

Run and document:

## Backend
- Unit/regression and API/contract tests.
- Adapter/schema/unit tests.
- Oil, pressure, electrical-stress, and protection-event tests.
- Capability qualification and OTHI invariants.
- Episode/advisory/feedback lifecycle.
- Missing/stale/invalid telemetry.
- FIT/CAL/TEST leakage controls.
- Deterministic replay and checkpoint/restart.

## Frontend
- Tests, lint/type checks, and production build.
- API integration and capability rendering.
- Loading/error/empty/stale states.
- Operator feedback workflows.

## End-to-end
- Start using the documented local/container workflow.
- Verify health/readiness and frontend/backend connectivity.
- Exercise normal and supported abnormal scenarios.
- Verify construction-aware oil/pressure availability.
- Confirm missing sensors are not represented as healthy.
- Confirm dashboard/report facts match.
- Verify replay determinism and candidate-to-baseline rollback.
- Inspect logs for exceptions, schema errors, missing artifacts, and unintended fallbacks.

Do not destroy Docker volumes as a shortcut. Fix regressions and rerun relevant suites. Report genuine environment blockers without masking them.

---

# PHASE 10 — FINAL HANDOFF

When all explicitly authorized phases are complete, report:

1. Git branches, SHAs, PR integration method, and unresolved conflicts.
2. Active dataset identity and preserved fallback artifacts.
3. Stabilization findings confirmed/fixed/not reproduced/blocked.
4. Files changed and regression tests added.
5. Candidate adapter and schema details.
6. Oil, pressure, electrical-stress, and construction-aware capability results.
7. FIT/CAL/TEST methodology, metrics, frozen hashes, and promotion status.
8. Frontend/backend contracts and workflows verified.
9. Exact test commands and pass/fail results.
10. Rollback procedure and confirmation.
11. Remaining blockers and risks.
12. Final Git status and confirmation that no unauthorized commit/push occurred.

Update the execution log and relevant documentation with actual results, not merely planned work.

---

# EXECUTION INSTRUCTION FOR THE CURRENT RUN

**Execute Phase 1 and Phase 2 now, in the same run.**

Do not stop after Phase 1. Do not extract or train on `gridpulse_synthetic_v1.zip` yet. Do not begin Phases 3–10 until I review the Phase 1/2 handoff and explicitly authorize the next stage.

Continue through both authorized phases, perform testing, fix regressions, and then return the evidence-based report. If one fix is genuinely blocked, continue other safe stabilization work and clearly document the blocker rather than abandoning the phase.
