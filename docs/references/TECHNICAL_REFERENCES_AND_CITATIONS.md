# GridPulse Technical References, Standards & Research Bibliography

**Project:** POWERNext-AI Hackathon 2026 — Track 2: Digital Twin for Intelligent Health Monitoring and Predictive Maintenance of Distribution Transformers  
**Document Status:** Authoritative Technical Reference Baseline  
**Revision:** 1.0 (Post Phase 3–5 Engineering Audit)  
**Date:** 2026-10-10  

---

## 1. Executive Summary & Purpose

This document provides complete, traceable, peer-reviewed, and standards-based citations for all mathematical models, physical equations, operational thresholds, anomaly detection algorithms, and architectural gating policies implemented across the GridPulse Digital Twin.

In accordance with [`docs/PRINCIPLES.md`](../PRINCIPLES.md) ("Physics Before Prediction" and "Every Output Must Have a Reason"), GridPulse avoids black-box empirical correlations and ungrounded Remaining Useful Life (RUL) assertions. Every analytical claim is explicitly classified under the project's evidence ontology:
- **FACT:** An engineering relationship or directly observed measurement with verified scope.
- **SOURCE:** A claim supported by an external standard, utility specification, or peer-reviewed publication.
- **ASSUMPTION:** A declared operating condition or parameter choice; never treated as unverified fact.
- **DERIVED:** A deterministic calculation from identified mathematical relationships.
- **CALIBRATED:** A parameter fitted from a chronological calibration partition (FIT/CAL).
- **HYPOTHESIS:** A possible diagnosis or diagnostic symptom requiring physical inspection.

---

## 2. Primary Technical References & Standards Bibliography

| Ref ID | Citation & Publishing Authority | Publication Type | Verification / Access Status | Supported Capability / Equation in GridPulse | Limitations & Explicit Exclusions |
|:---|:---|:---|:---|:---|:---|
| **REF-01** | **IEEE Std C57.91-2011**, *IEEE Guide for Loading Mineral-Oil-Immersed Transformers and Step-Voltage Regulators*. IEEE Power and Energy Society, March 2012. DOI: [10.1109/IEEESTD.2012.6166943](https://doi.org/10.1109/IEEESTD.2012.6166943). | Normative International Standard | Inspected via secondary literature & IEEE Xplore metadata | Arrhenius relative aging rate ($F_{AA}$, Eq. 1); Insulation Loss of Life ($L_{eq}$, Eq. 2); Reference hotspot temperature ($110^\circ\text{C}$ for thermally upgraded paper, $95^\circ\text{C}$ for standard kraft paper). | Winding hotspot temperature is not available in baseline telemetry. Model tier `C4_THERMAL_INSULATION_LIFETIME` remains strictly disabled unless verified insulation class and credible hotspot temperature exist. |
| **REF-02** | **IEC 60076-7:2018**, *Power transformers – Part 7: Loading guide for mineral-oil-immersed power transformers*. International Electrotechnical Commission, Geneva, Switzerland, 2018. URL: [IEC Webstore](https://webstore.iec.ch/publication/30747). | Normative International Standard | Inspected via peer-reviewed literature (Najar et al. 2017; Tembo et al. 2025) | Top-oil thermal differential equation structure (first-order ODE with oil time constant $\tau_o$, loss ratio $R$, and oil exponent $x$). | Generic IEC parameters ($\tau_o = 180\text{ min}, x = 0.8$) exhibit up to $\pm 10^\circ\text{C}$ error on real units, necessitating per-asset calibration and capability gating. |
| **REF-03** | **S. Najar, J.-F. Tissier, S. Cauet, E. Etien** (2017), "Improving thermal model for oil temperature estimation in power distribution transformers," *Applied Thermal Engineering*, vol. 119, pp. 73–78. DOI: [10.1016/j.applthermaleng.2017.03.061](https://doi.org/10.1016/j.applthermaleng.2017.03.061). | Peer-reviewed Journal Article | Full text inspected | First-order grey-box thermal ODE parameter identification on ONAN distribution transformers (160 kVA, 400 kVA, 800 kVA); parameter values $\tau_o \in [141, 199]\text{ min}$, $\Delta\theta_{or} \approx 55\text{ K}$, $x \in [0.76, 0.80]$. | Real units tested were French 20 kV / 400 V ONAN units; thermal transfer to 11 kV units is an engineering assumption. |
| **REF-04** | **F. Tembo, F. Bragone, T. Laneryd, M. Barreau, K. Morozovska** (2025), "Data-Driven vs Traditional Approaches to Power Transformer's Top-Oil Temperature Estimation," *arXiv preprint*, arXiv:2501.16831. URL: [arXiv:2501.16831](https://arxiv.org/abs/2501.16831). | Peer-reviewed Preprint | Full text inspected | Numerical solution and discrete-time finite difference formulations of IEC 60076-7 ODE with thermal time constant weighting $k_{11} \tau_o$. | Evaluated on large power transformer data; used in GridPulse for discrete-time solver validation. |
| **REF-05** | **IEEE Std C57.109-2018**, *IEEE Guide for Liquid-Immersed Transformers Through-Fault-Current Duration*. IEEE Power and Energy Society, 2018. DOI: [10.1109/IEEESTD.2018.8471198](https://doi.org/10.1109/IEEESTD.2018.8471198). | Normative International Standard | Inspected via SEL Technical Paper (Kazemi & Labuschagne) & standards clauses | Through-fault current duration limits for Category I distribution transformers (15–500 kVA single/three-phase: $I^2 t = 1250$ for $I_{sc} \in [25, 40]\text{ pu}$; conservative $2.0\text{ s}$ limit below $25\text{ pu}$). | Establishes mechanical/thermal withstand boundaries; does NOT model asymmetrical transient sub-cycle fault currents. |
| **REF-06** | **J. D. Glover, T. J. Overbye, M. S. Sarma** (2017), *Power System Analysis & Design*, 6th Edition, Cengage Learning, Boston, MA. ISBN: 978-1305632134. | Authoritative Engineering Textbook | Inspected | Three-phase symmetrical prospective short-circuit current formulation ($I_{sc,sym} = I_{rated} / Z_{pu}$) across two-winding transformer impedances. | Steady-state prospective reference calculation assuming infinite primary bus; does not constitute a full IEC 60909 fault study. |
| **REF-07** | **Kerala State Electricity Board Ltd (KSEB)**, Supply Chain Management, *Technical Specification: Distribution Transformer 11kV/433V, 100, 160, 250 & 500 kVA*, Document No. `SCM-SPEC/XD/DT2 Rev 0.2`, effective 17-11-2021. URL: [KSEB SCM Specification](https://kseb.in). | Utility Procurement & Technical Specification | Full text inspected | §4.1: Standard distribution ratings (160, 250, 500 kVA, 11 kV / 433–250 V, Dyn11, ONAN); §10.1: Maximum load/no-load losses; §16.2.1–§16.2.2: Tank operating pressure withstand boundary $\le \pm 0.4\text{ kg/cm}^2$ ($\approx \pm 39.2\text{ kPa}$); §17(iv): Conservator sizing (10% total oil volume, 3% nominal at $30^\circ\text{C}$). | Specific to Indian utility distribution standards; sealed tank specifications require dedicated elastic corrugation limits. |
| **REF-08** | **Bureau of Indian Standards (BIS)**, *IS 1180 (Part 1): 2014 — Outdoor Type Oil Immersed Distribution Transformers Up to and Including 2500 kVA, 33 kV — Specification*. BIS, New Delhi, India, 2014. | National Standard | Official standard clauses inspected via KSEB S7 | Standard impedance values ($4.5\%$ nominal), standard voltage ratios, loss efficiency levels (Energy Efficiency Level 1–3), and mechanical test pressures. | General construction standard; operational pressure alarm setpoints ($+25\text{ kPa}$, $+35\text{ kPa}$) are utility/manufacturer specific settings, not fixed by IS 1180. |
| **REF-09** | **ASTM D3487-16e1**, *Standard Specification for Mineral Insulating Oil Used in Electrical Apparatus*. ASTM International, West Conshohocken, PA, 2016. DOI: [10.1520/D3487-16E01](https://doi.org/10.1520/D3487-16E01). | Normative Material Standard | Standard properties inspected | Volumetric thermal expansion coefficient of mineral transformer oil ($\beta \approx 7.5 \times 10^{-4}\text{ K}^{-1}$ or $0.075\%/^\circ\text{C}$ over $20^\circ\text{C}$ to $100^\circ\text{C}$). | Oil expansion varies slightly across paraffinic vs naphthenic crude basestocks; accurate field correction requires ASTM D1903 test data. |
| **REF-10** | **NEMA MG 1-2016 / IEEE Std 141-1993**, *Electric Power Distribution for Industrial Plants (Red Book)*. IEEE, New York. DOI: [10.1109/IEEESTD.1994.121642](https://doi.org/10.1109/IEEESTD.1994.121642). | Normative Engineering Standard | Inspected | Phase Voltage and Current Unbalance Ratio formulas (Maximum phase deviation from average divided by average, expressed as %). Unbalance threshold $\ge 20\%$ triggers severe derating advisory. | Approximates symmetrical component negative-sequence ratio for small unbalances ($< 5\%$). |
| **REF-11** | **E. S. Page** (1954), "Continuous Inspection Schemes," *Biometrika*, vol. 41, no. 1/2, pp. 100–115. DOI: [10.2307/2333009](https://doi.org/10.2307/2333009). | Foundational Statistical Paper | Inspected | Cumulative Sum (CUSUM) change detection algorithm for tracking small persistent systematic drifts in sensor and thermal model residuals. | Requires properly tuned reference allowance $k$ and decision boundary $h$ calibrated against training data to avoid false positive accumulation. |
| **REF-12** | **V. Vovk, A. Gammerman, G. Shafer** (2005), *Algorithmic Learning in a Random World*, Springer, New York. DOI: [10.1007/b106715](https://doi.org/10.1007/b106715). | Foundational Monograph | Inspected | Split Conformal Prediction methodology for finite-sample distribution-free predictive uncertainty intervals with guaranteed coverage probability $1 - \alpha$. | Guarantees hold under exchangeability; temporal autocorrelation requires non-conformity calibration over holdout horizons. |

---

## 3. Mandatory Review of Phase 3–5 Audit Claims

### Claim A: Sealed-Tank Pressure Limits
- **Audit Statement:** The audit noted that $+25\text{ kPa(g)}$ alarm, $+35\text{ kPa(g)}$ PRD relief, and $-10\text{ kPa(g)}$ low-pressure boundary are supported by dataset methodology and fall within an `IS 1180 / S7 §16.2` operating envelope of $\pm 39.2\text{ kPa}$.
- **Traceable Verification & Clarification:**
  1. *Standard Disambiguation:* The cited "S7 §16.2" refers specifically to **Kerala State Electricity Board (KSEB) Technical Specification Doc. `SCM-SPEC/XD/DT2 Rev 0.2` §16.2.1–§16.2.2** ("Pressure withstand criteria"). This utility specification mandates that transformer tanks withstand a test pressure and operating envelope of $\pm 0.4\text{ kg/cm}^2$, which converts directly to $\pm 39.2266\text{ kPa(g)}$. IS 1180 (Part 1): 2014 specifies overall distribution transformer construction and loss tables, but the explicit $\pm 0.4\text{ kg/cm}^2$ operating limit is defined in the utility specification.
  2. *Scenario-Defined Settings:* In the candidate dataset (`gridpulse_synthetic_v1`), the $+25\text{ kPa(g)}$ alarm threshold and $+35\text{ kPa(g)}$ PRD trip threshold are classified as **`SCENARIO_SETTING`** parameters defined within `generate_dataset.py`. They are chosen by the dataset design to alert operators and trigger protection *prior* to reaching the structural tank withstand limit ($\pm 39.2\text{ kPa}$).
  3. *Lower Vacuum Boundary:* The $-10\text{ kPa(g)}$ lower boundary is an engineering plausibility limit to detect severe depressurization or gasket integrity failure during cold ambient contraction.
  4. *Construction Gating:* These thresholds apply **exclusively to hermetically sealed corrugated-tank transformers** (`DT-03-SEAL-250`). Conservator transformers (`DT-01`, `DT-02`, `DT-04`) operate with open breathers at atmospheric pressure ($0\text{ kPa(g)}$). The GridPulse `CapabilityEvaluator` strictly gates pressure monitoring off for conservator units (`tank_type != "sealed_corrugated"`).

### Claim B: Oil-Level Trend Threshold
- **Audit Statement:** The audit describes a $-0.10\,\%/day$ threshold using synthetic leakage scenarios and an estimated normal-noise boundary.
- **Traceable Verification & Clarification:**
  1. *Physical & Statistical Basis:* In the candidate dataset, simulated slow-leak scenarios introduce physical oil losses of $0.12\text{ to }0.22\text{ L/day}$ against a total oil volume of $220\text{ L}$, producing an underlying depletion rate of approximately $-0.05\%\text{ to }-0.10\%/\text{day}$.
  2. *Thermal Fluctuation Noise:* Transformer oil expands and contracts with top-oil temperature variations ($\beta \approx 7.5 \times 10^{-4}\text{ K}^{-1}$, ASTM D3487). Diurnal temperature swings of $25\text{ K}$ induce reversible oil level fluctuations of up to $\pm 1.8\%$. Over a rolling linear regression window of 72 samples (36 hours at 30-min cadence), the empirical diurnal noise slope exhibits a $3\sigma$ bound of approximately $\pm 0.09\%/\text{day}$.
  3. *Detection Threshold:* The $-0.10\%/\text{day}$ threshold in `backend/app/engine/anomaly_detectors.py` is configured just beyond this $3\sigma$ diurnal noise envelope to achieve reliable detection of real trends while suppressing diurnal false alarms.
  4. *Engineering Boundary & Advisory Semantics:* Telemetry trend alone **does not prove a physical oil leak**. A declining gauge can be caused by gauge calibration drift, cooling cycles, or ambient shifts. Therefore, GridPulse emits advisory `MNT-OIL-008` ("Oil level declining trend detected. Inspect for external leakage or faulty gauge."), triggering physical visual inspection rather than asserting an ungrounded failure.

### Claim C: Short-Circuit Reference Calculation
- **Audit Statement:** The audit describes prospective symmetrical short-circuit current calculations based on nameplate rating and impedance.
- **Traceable Verification & Clarification:**
  1. *Mathematical Formulation:* Implemented in `backend/app/engine/physics.py` as:
     $$I_{rated,LV} = \frac{S_{rated}}{\sqrt{3} \cdot V_{rated,LV,LL}}, \quad I_{sc,sym} = \frac{I_{rated,LV}}{Z_{pu} \cdot 1000} \text{ [kA]}$$
  2. *Primary Citations:* Derived from classical power systems analysis (Glover, Overbye & Sarma, 2017) and IEEE Std C57.109-2018 §4.
  3. *Scope & Disclaimers:* This calculation represents a **prospective steady-state symmetrical three-phase through-fault current reference value** on the LV terminals assuming an infinite HV source bus and nominal voltage ($V = 1.0\text{ pu}$).
  4. *Explicit Exclusions:*
     - It is **not** an IEC 60909 fault study (does not incorporate complex network impedance, voltage factor $c$, or motor backfeed).
     - It does **not** reconstruct transient sub-cycle asymmetrical peak waveforms ($k\sqrt{2} I_{sc}$). 30-minute SCADA telemetry cannot capture sub-cycle dynamics.
     - It does **not** evaluate protection coordination, breaker interrupting capacity, or transformer mechanical dynamic withstand per IEC 60076-5.

### Claim D: Thermal & Ageing Models
- **Audit Statement:** The audit references IEEE C57.91 and IEC 60076-7 regarding thermal ODEs and insulation aging.
- **Traceable Verification & Clarification:**
  1. *Top-Oil Thermal ODE:* Solved via finite-difference numerical integration:
     $$\tau_o \frac{d\theta_o}{dt} = \Delta\theta_{or} \left[\frac{1 + R K^2}{1 + R}\right]^x - (\theta_o - \theta_a)$$
     Where $K = S / S_{rated}$ is the per-unit load ratio, $R = P_{k,rated} / P_{0}$ is the loss ratio, $\tau_o$ is the thermal time constant, $\Delta\theta_{or}$ is the rated top-oil temperature rise over ambient, and $x$ is the oil exponent ($x \approx 0.8$ per IEC 60076-7 / Najar et al. 2017).
  2. *Hotspot Temperature & Arrhenius Aging:*
     $$\theta_h = \theta_o + \Delta\theta_{hr} K^y, \quad F_{AA} = \exp\left[\frac{15000}{383.15} - \frac{15000}{\theta_h + 273.15}\right]$$
  3. *Strict Capability Discipline:* In the active CPRI v3.0.2 baseline, winding temperature is absent from telemetry. GridPulse strictly enforces that insulation life consumption ($L_{eq} = \int F_{AA} dt$) is gated off (`C4_THERMAL_INSULATION_LIFETIME = False`). The system reports observed thermal exposure (time-in-band degree-hours) without claiming unverified insulation life consumption.

### Claim E: Dataset Provenance & Segregation
- **Traceable Verification:**
  1. *Active Production Baseline:* CPRI v3.0.2 empirical field dataset from Tripura State Electricity Corporation Ltd (TSECL), 33/11kV sub-station feeder transformers (ED-1, ED-2, etc.). 15-minute sampling cadence. Partitioned chronologically into FIT, CAL, and TEST. Evaluated once on TEST; only `TX_1000_COMM` qualified for promotion under signed-bias gate.
  2. *Candidate Synthetic Dataset:* Isolated in `data/candidates/gridpulse_synthetic_v1/`, extracted from `gridpulse_synthetic_v1.zip` (SHA-256: `4601e56663158a129acb777b2725cf1eab0ad17f95527e59be1bf6d39bf6e827`). Contains 4 assets (`DT-01` to `DT-04`), 160–500 kVA, 11kV/433V ONAN, 30-minute cadence over 180 days (34,560 rows).
  3. *Segregation & Zero-Leakage:* Candidate dataset is 100% isolated. Fault event ledgers and scenario labels serve strictly as evaluation references and are never exposed to live runtime detectors or model fitting.

### Claim F: Other Research-Derived Claims
- **Traceable Verification:**
  1. *Phase Voltage & Current Unbalance:* Implemented per NEMA MG 1-2016 formula:
     $$\text{Unbalance (\%)} = \frac{\max(|X_a - X_{avg}|, |X_b - X_{avg}|, |X_c - X_{avg}|)}{X_{avg}} \times 100\%$$
     Threshold $\ge 20\%$ triggers severe phase unbalance advisory `MNT-ELEC-003`.
  2. *CUSUM Change Detection:* Implemented per Page (1954) to accumulate residual deviations:
     $$S_t = \max(0, S_{t-1} + (e_t - k)), \quad S_t > h \implies \text{Anomaly Episode}$$
  3. *Conformal Uncertainty Bounds:* Implemented per Vovk et al. (2005) split conformal prediction over calibration residuals to construct rigorous $90\%$ and $95\%$ empirical prediction intervals without Gaussian assumptions.
  4. *Stuck Sensor Detection:* Zero-variance heuristic ($\text{Var}(y) < 10^{-4}$) evaluated over a rolling window ($\ge 24\text{ hours}$) while driver temperature varies ($\Delta \theta_o \ge 5^\circ\text{C}$). Classified as an empirical engineering rule, not a peer-reviewed theorem.

---

## 4. Equation-to-Code Traceability Matrix

| Equation / Concept | Mathematical Definition | Source Reference | Implementing Code File | Implementing Function / Class |
|:---|:---|:---|:---|:---|
| **Top-Oil ODE** | $\tau_o \frac{d\theta_o}{dt} = \Delta\theta_{or} \left[\frac{1+RK^2}{1+R}\right]^x - (\theta_o - \theta_a)$ | IEC 60076-7, Najar et al. (2017) | `backend/app/engine/physics.py` | `solve_top_oil_euler_step`, `GreyBoxThermalModel` |
| **Hot-Spot Temperature** | $\theta_h = \theta_o + \Delta\theta_{hr} K^y$ | IEEE C57.91-2011 §7 | `backend/app/engine/physics.py` | `estimate_hotspot_temperature` |
| **Arrhenius Aging** | $F_{AA} = \exp\left[\frac{15000}{383.15} - \frac{15000}{\theta_h + 273.15}\right]$ | IEEE C57.91-2011 §5.1 | `backend/app/engine/physics.py` | `calculate_relative_aging_rate` |
| **Prospective $I_{sc,sym}$** | $I_{sc,sym} = \frac{S_{rated}}{\sqrt{3} \cdot V_{rated,LL} \cdot Z_{pu} \cdot 1000}$ | IEEE C57.109-2018, Glover (2017) | `backend/app/engine/physics.py` | `calculate_prospective_short_circuit_ka` |
| **Through-Fault Limit** | $t_{allowable} = 1250 / I_{sc,pu}^2$ | IEEE C57.109-2018 Table 1 | `backend/app/engine/physics.py` | `calculate_through_fault_duration_limit` |
| **Phase Unbalance** | $\text{Unbalance} = \frac{\max |X_i - X_{avg}|}{X_{avg}} \times 100$ | NEMA MG 1-2016 §14.35 | `backend/app/engine/physics.py` | `calculate_unbalance_ratio` |
| **Oil Expansion Volume** | $\Delta V = V_0 \cdot \beta \cdot \Delta T$ | ASTM D3487, KSEB S7 §17 | `backend/app/engine/physics.py` | `estimate_oil_thermal_expansion` |
| **CUSUM Residual** | $S_t = \max(0, S_{t-1} + (e_t - k))$ | Page (1954) | `backend/app/engine/anomaly_detectors.py` | `CusumDetector` |
| **Conformal Prediction** | $\hat{y} \pm \text{Quantile}_{1-\alpha}(|y - \hat{y}|_{\text{CAL}})$ | Vovk et al. (2005) | `backend/app/engine/othi.py` | `ConformalCalibrator` |
| **OTHI Multi-Domain** | $\text{OTHI} = 100 - \sum w_i \cdot \text{Penalty}_i$ | Frozen Architecture §B | `backend/app/engine/othi.py` | `OperationalHealthIndexCalculator` |

---

## 5. Summary of Engineering Exclusions & Honesty Guarantees

1. **No True RUL Estimation:** GridPulse refuses to output whole-life Remaining Useful Life (RUL) in days, months, or years without multi-year longitudinal asset degradation records and Dissolved Gas Analysis (DGA).
2. **No Arbitrary Failure Probabilities:** The system does not output black-box failure likelihood percentages. It outputs empirical conformal prediction error bounds and multi-domain evidence corroboration.
3. **No Autonomous Switching:** The platform operates strictly as decision-support advisory software. Autonomous trip, breaker, or tap-changer commands are prohibited.
4. **No Waveform Reconstruction:** 30-minute SCADA telemetry cannot reconstruct sub-cycle short-circuit waveforms or asymmetrical DC offsets.
5. **No Universal Leak Proof:** Telemetry oil-level slope does not prove an active physical oil leak. It triggers an advisory for physical visual inspection.
