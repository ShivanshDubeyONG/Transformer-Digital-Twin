# Coding Rules & Implementation Protocol

**Project:** POWERNext-AI Hackathon 2026 — Track 2: Digital Twin for Distribution Transformer Health Monitoring  
**Team:** SKY HIGH  
**Companion Document:** [`docs/PRINCIPLES.md`](PRINCIPLES.md)  
**Governance Hierarchy:** [`docs/FINAL_ARCHITECTURE_DECISIONS.md`](FINAL_ARCHITECTURE_DECISIONS.md) $\rightarrow$ [`docs/SRS.md`](SRS.md) $\rightarrow$ [`docs/MVP.md`](MVP.md) $\rightarrow$ [`docs/IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)

This document establishes the practical, operational rules that all implementation agents and human developers must follow when writing code, configuring tools, running tests, or performing workspace operations.

---

## 1. Manual Control of Large Downloads

If an implementation step requires downloading a large dataset, model archive, Docker image, or substantial external artifact:
- Do **NOT** initiate the large download automatically.
- Stop and provide the exact command(s) required.
- State clearly what is being downloaded, approximate size if known, and the target storage path.
- The user will execute the command manually in their terminal.
- Once the user confirms completion, verify the artifact and continue.
- Small standard package installations during development (`pip install`, `npm install`) may proceed normally unless unusually large.
- Do not repeatedly attempt a failed large download automatically.

---

## 2. Manual Control of Model Training & Expensive Computation

If implementation reaches an operation where a model needs to be trained, calibrated, fitted, benchmarked, or an expensive computational experiment must run:
- Prepare the code, configuration, scripts, and inputs necessary for the operation.
- Do **NOT** automatically start the expensive training/calibration job in the background.
- Provide the user with the exact command to run.
- Clearly state what the command does, approximate runtime, and what output artifacts are expected.
- The user will execute the job manually to monitor progress, resource utilization, logs, and any runtime exceptions.
- After user confirmation, inspect the generated artifacts/metrics and continue.
- This applies specifically to:
  - Thermal model parameter fitting ($\beta_0, \beta_1, \tau$)
  - Baseline model evaluations
  - CUSUM decision limit grid searches
  - Conformal empirical uncertainty calibration
  - Large dataset batch replay and evaluation runs
  - Any future computationally intensive analytical jobs

---

## 3. GitHub Actions & Remote CI Control

All GitHub repository initialization, remote configuration, GitHub Actions setup, secrets configuration, and remote administrative operations remain under manual user control.
- When such an operation is required, prepare the necessary configuration files (e.g., workflow YAMLs), commit messages, or terminal commands.
- Explain exactly what the user needs to execute.
- Do not make assumptions regarding GitHub authentication, repository ownership, remote URLs, secrets, or branch protections.
- Do not push commits or tags to remote repositories without explicit user instruction.
- Local Git operations (staging, committing locally, checking diffs) are permitted when appropriate.

---

## 4. Keep Implementation Simple

Prefer the simplest implementation that strictly satisfies the locked requirements.
- Do **NOT** introduce:
  - Unnecessary abstractions or speculative generic frameworks
  - Excessive design patterns, wrappers, or helper layers
  - Over-engineered interfaces for single-implementation classes
  - Premature performance optimizations
  - Unapproved third-party libraries or technologies
- Follow the exact architecture already defined in the project documents.
- Every component should be immediately understandable by another engineer reading it for the first time.

---

## 5. Consistent Patterns

Once an architectural or engineering pattern is established in the codebase, reuse it consistently.
- Standardized naming conventions (snake_case for Python, camelCase/PascalCase for TypeScript).
- Uniform file and directory layout matching the 10-phase plan.
- Standardized Pydantic validation and error-handling hierarchies.
- Consistent API response envelopes and error codes.
- Structured logging with explicit context and timestamps.
- Uniform test structures (arrange, act, assert) using PyTest fixtures.
- If an existing project pattern works, extend it rather than inventing a competing style.

---

## 6. Organization & Workspace Hygiene

Maintain a clean, logically organized workspace throughout all implementation phases.
- Place all files strictly in their intended module directories (`app/core`, `app/engine`, `app/adapters`, `app/api`, `app/reports`, `tests/`).
- Remove genuinely redundant code, dead functions, and obsolete imports when refactoring safely.
- Avoid duplicate or competing implementations of the same business logic.
- Prevent temporary scratch scripts from leaking into permanent production trees.
- Before authoring a new utility, verify whether an existing module already provides the capability.
- Do not leave abandoned experiments inside the main repository tree.

---

## 7. Comments & Documentation Style

Keep inline comments focused and minimal.
- Write comments **only** when explaining non-obvious engineering logic:
  - Complex mathematical derivations or ODE discretization
  - Physics-based assumptions and unit boundaries
  - Specific numerical stability considerations (e.g., numerical floors)
  - Critical safety, claim, or gating constraints
  - Intentionally unusual edge-case handling
- Do **NOT** comment obvious lines or restate what clean code already expresses.
- Prefer self-describing variable and function names over explanatory comment blocks.

---

## 8. No Silent Invention

Never fabricate or silently invent:
- Dataset measurements or sensor readings
- Transformer nameplate ratings (kVA, voltage, cooling class)
- Sensor semantics or physical units
- Physical constants or insulation classes
- Model parameters without calibration records
- Fault labels or diagnostic ground truth
- Protection limits or standard thresholds
- API contracts or config defaults
- If a value is genuinely unknown, use the approved fallback/unavailable representation (`null`, `UNKNOWN`, `UNVERIFIED`) or halt and request a decision.

---

## 9. No Silent Architecture Changes

If an implementation detail exposes a conflict with the locked architecture:
- **STOP.** Do not silently modify the design.
- Report:
  1. The exact conflict discovered
  2. The affected document and section
  3. The proposed resolution and its engineering justification
- Await explicit human approval before altering any locked architectural decision.
- Follow the strict source-of-truth hierarchy:  
  `FINAL_ARCHITECTURE_DECISIONS.md` $\rightarrow$ `SRS.md` $\rightarrow$ `MVP.md` $\rightarrow$ `IMPLEMENTATION_PLAN.md`.

---

## 10. Development Data vs. Runtime Data Separation & Evaluation Discipline

Strictly preserve the separation between different data classes:
- **Historical Development Data (Tripura):** Tripura telemetry (`tripura_dt_01`) is used for development, calibration, and regression testing under a 60/20/20 chronological partition (`FIT` $\to$ `CAL` $\to$ `TEST`). Due to earlier exploratory analysis during methodology development, the Tripura TEST partition is documented as a development evaluation set, not a pristine final scientific lockbox.
- **Held-Out Replay Telemetry:** Telemetry from the held-out/test period is explicitly authorized for live runtime simulation and interactive operator demonstration via deterministic replay (`POST /v1/replay`), because replay executes the runtime state engine without fitting or modifying model parameters.
- **Synthetic Scenario Data:** Controlled anomaly injections, strictly labeled with `SYNTHETIC_SCENARIO`.
- **Runtime Telemetry:** Incoming canonical events received via REST endpoints (`POST /v1/telemetry`).
- **Reference / Commissioning Data:** `Draft Data for Condition Monitoring.xlsx` used purely as an adapter/tolerance reference, never as telemetry training data or asset rating source.
- Never mix or leak data between these partitions.

**Rules for Future CPRI / Hackathon Holdout Datasets:**
1. *Freeze Before TEST:* Freeze all model families, load drivers, parameter bounds, optimization grids, forecasting horizons, evaluation metrics, anomaly thresholds, uncertainty interval algorithms, data exclusions, and promotion criteria prior to evaluating the holdout TEST partition.
2. *No Tuning Against TEST:* Never use TEST performance to select or change model families, load drivers, parameters, bounds, horizons, metrics, thresholds, uncertainty intervals, exclusions, or promotion criteria.
3. *Accept Model Weaknesses:* If TEST reveals a genuine model weakness, accept the result and allow capability qualification / fallback to activate honestly, rather than tuning against TEST.
4. *Software Defect Remediation:* If a verified software defect invalidates TEST (e.g., CLI crash, logging exception, indexing bug, reporting key mismatch), document the invalid run, fix the software defect with the smallest possible code change, and rerun the *exact same* frozen methodology. Do NOT redesign or retune the methodology based on the TEST result.
5. *Burned TEST Policy:* If TEST results are ever used to redesign, tune, or select the methodology, that TEST partition is considered burned and an unseen holdout dataset is mandatory for final scientific evaluation.

---

## 11. Determinism & Reproducibility

Enforce deterministic execution across all system layers:
- Use explicit, fixed random seeds for synthetic test generators and conformal samplers.
- Version all configuration files, AssetProfiles, and maintenance rule sets.
- Maintain deterministic event-time sorting and tie-breaking in temporal reductions.
- Record SHA-256 hashes of input datasets, adapter maps, and generated model states.
- Replaying the identical ordered stream against the same model version must produce byte-identical `TwinState` and output hashes.

---

## 12. Numerical & Physical Integrity

Never compromise physical correctness for visual appeal or artificial precision.
- Preserve explicit UCUM physical units ($V, A, W, \text{var}, VA, \text{Cel}, \text{s}, \text{h}$) across all interfaces.
- Validate physical input bounds and flag impossible states ($T_o < T_a - 10^{\circ}\text{C}$).
- Explicitly distinguish data classes: *Observed*, *Derived*, *Estimated*, *Configured*, *Latent*, and *Decision*.
- Propagate data quality flags (`GOOD`, `UNCERTAIN`, `BAD`, `STALE`) honestly.
- Preserve approved fallback behavior rather than guessing missing inputs.

---

## 13. Testing Before Declaring Completion

No feature or phase is complete until backed by verifiable automated tests.
- Unit tests for pure mathematical functions, feature transforms, and ODE integration.
- Property-based tests (Hypothesis) for physical invariants ($S \ge P, S \ge Q, 0 \le \text{PF} \le 1.0$).
- Static fixture regression tests for edge cases (scale errors, gaps, duplicates, protection trips).
- Dynamic injector tests verifying anomaly detection within $\le 2$ cycles.
- API contract tests for all 12 endpoints.
- Integration and E2E Playwright tests for full user workflows.
- Use the Definition of Done (DoD) checklist in `IMPLEMENTATION_PLAN.md` as the true completion criteria.

---

## 14. Dependency Discipline

Avoid adding unnecessary external dependencies.
- Before adding a library, verify whether standard library modules (`math`, `dataclasses`, `datetime`, `typing`) or existing approved dependencies (`numpy`, `scipy`, `pydantic`, `fastapi`, `duckdb`, `pint`) already solve the requirement.
- Add third-party packages only when they provide indispensable domain value (e.g., WeasyPrint for PDF rendering).
- Do not add heavy frameworks for trivial utility functions.

---

## 15. Fail Clearly & Explicitly

System errors and data invalidities must fail fast with clear, actionable diagnostics.
- Never swallow exceptions or silently ignore validation errors.
- Never continue pipeline calculations on corrupted or quarantined inputs.
- Never silently downgrade capability tiers without recording the exact reason code in `CapabilityManifest`.
- Never return misleading HTTP 200 responses for failed state transitions.
- Use structured error envelopes with unambiguous error codes and timestamps.

---

## 16. Agent Execution Discipline

Implementation agents must operate with disciplined, incremental execution:
- Work in small, self-contained, reviewable increments.
- Prior to editing, inspect existing files, contracts, and relevant tests.
- Implement the minimal coherent modification required for the active task.
- Run the affected test suite to prove correctness before proceeding.
- Report exact diffs and outcomes without touching unrelated files.
- Never perform broad stylistic "cleanups" across files outside the active task scope.

---

## 17. User Visibility for Expensive or Consequential Operations

The user must remain in control of all high-impact actions:
- Downloading large datasets, Docker base images, or pre-trained artifacts.
- Initiating long-running CPU/GPU calibration or search jobs.
- Executing destructive file deletions or directory overwrites.
- Performing remote Git pushes, branch resets, or release tagging.
- Prepare clear commands and explanations first; do not hide consequential operations behind silent background scripts.

---

## 18. Code Quality Hierarchy

Implementation decisions are prioritized strictly according to this quality hierarchy:

$$\text{SIMPLE} \longrightarrow \text{CORRECT} \longrightarrow \text{CONSISTENT} \longrightarrow \text{TESTED} \longrightarrow \text{TRACEABLE}$$

A clean, transparent, well-tested implementation that is easy to inspect and defend is always preferred over an intricate, complex design.
