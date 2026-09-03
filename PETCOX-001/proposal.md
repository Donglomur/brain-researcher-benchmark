## PETCOX-001

**Proposal Title:** Estimate the cerebral distribution volume V_T of a COX-2 radioligand from dynamic [11C]MC1 PET with an arterial-input kinetic model — an un-cued **model-order** judgement (robustness / reporting-quality axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular imaging / PET pharmacokinetic modelling

**Source finding:** first-in-human evaluation of **[11C]MC1**, a radioligand for cyclo-oxygenase-2 (COX-2), a neuroinflammation target (OpenNeuro **ds004869**, CC0; Kim et al.). Invasive kinetics: Logan et al. 1990 (graphical V_T); Ichise et al. 2002 (MA1); 2TCM; Innis et al. 2007 (V_T consensus nomenclature). The dataset ships **petfit-extracted regional TACs** (`derivatives/petfit/desc-combinedregions_tacs.tsv`), **arterial blood** per scan (plasma activity, HPLC parent fraction, whole blood), and a petfit reference of per-region V_T from 2TCM/Logan/MA1 — all fetched at runtime from OpenNeuro (open, no credentials, snapshot 1.4.0).

**Status: FULL runnable task.** New on three axes vs the shipped real-data PET set (PETREF-001 ds001420, PETVT-001 ds005619, PETDVR-001 ds001420): **dataset** (ds004869), **tracer/target** (COX-2 [11C]MC1), and — critically — the **un-cued lever** (kinetic **model order**, not PETVT's input construction and not PETDVR's Logan linear-segment t*). Genre: **reproduction** with an un-cued model-order judgement.

> Note on feasibility: PETVT-001's proposal recorded that, at its build time, "only ds001420 and ds005619 ship pre-extracted regional TAC tables" across the OpenNeuro PET catalogue. **ds004869 now ships a full `petfit` derivative** (combined-region TACs + per-model kinparameters) plus per-scan `bloodstream`/manual arterial blood, so it is a genuinely new container-feasible substrate.

### Why this exists (new axis: model order)

For a reversible arterial-input tracer, V_T is well-posed and **estimator-invariant when the model is adequate**. On ds004869 the three reference estimators agree tightly — cohort-mean cortical V_T from 2TCM (~2.14), Logan (2.17), MA1 (2.16) — so neither the **input construction** (PETVT's lever) nor the **graphical t\*** (PETDVR's lever) is the discriminator here (see the "levers considered" table). The one large, robust analytic choice this dataset exposes is the **number of tissue compartments**: [11C]MC1 cortical TACs have an early peak and a slow tail that a single tissue compartment cannot follow. A 1-tissue-compartment (1TCM) fit converges, looks reasonable (it is a common default for "fit a kinetic model"), and **under-estimates V_T by ~a third** — off the critical path, because the fit still returns a plausible number.

### Step-0 (validated, real — reproduces on obtainable data)

Fetched all 27 participants' petfit cortical TACs + manual arterial blood (no credentials) and estimated **cerebral-cortex V_T** (mean of Frontal/Temporal/Parietal/Occipital/ACC/PCC/Insula) with Logan (t* = 20 min) and MA1. Input = metabolite-corrected arterial plasma (`plasma × parent_fraction`); the ds004869 blood samples are **already decay-referenced to injection** (verified: using plasma as-is reproduces the petfit reference V_T; applying an extra decay correction gives nonsense ~0.3), so — unlike ds005619 — no decay handling is applied.

Cohort-mean cortical **V_T ≈ 2.17 mL·cm⁻³** (n = 27), per-participant range ~1.6–2.9 (max/min ~2.0). Cross-checks: **MA1 2.156** (Logan≈MA1 to ~1%), petfit-reference **2TCM ~2.14** — i.e. estimator-invariant once the model order is right.

### The un-cued lever (Step-0 measured — LARGE and robust)

Cohort-mean cortical V_T under each analytic choice (27 scans):

| analysis choice | cohort-mean V_T | vs correct |
|---|---|---|
| **2-tissue / graphical Logan / MA1** (adequate model — correct) | **2.14 – 2.24** | — |
| **1-tissue-compartment (1TCM)** fit | **1.45** | **−33 %** (ratio 0.68 ± 0.07, robust across all 27 scans) |
| Logan regressed over **all frames from t = 0** | 1.86 | −14 % (secondary; PETDVR's lever, weaker here) |

The 1TCM under-estimate is **mechanical and consistent** (0.68 ± 0.07 across every scan), because a single exponential impulse response cannot represent the tracer's two-phase tissue kinetics — the fit's early frames are pulled up and the tail is pulled down, lowering K1/k2. This is the classic model-order failure and is genuinely off-critical-path: the 1TCM fit "succeeds" for all participants.

### Levers considered and rejected (no-fake-traps discipline)

* **Input construction (PETVT's lever):** available here (blood has whole-blood / plasma / parent-fraction columns) and would give a large gap — but that is *exactly* PETVT-001's mechanism, so the input is **pinned in `instruction.md`** (stated as the metabolite-corrected plasma, already decay-referenced) to remove it as a second trap and isolate the model-order judgement.
* **Graphical t\* / linear-segment (PETDVR's lever):** only −14 % here (V_T is fairly t*-stable for a slow reversible tracer), and it duplicates PETDVR-001's mechanism — not the framing.
* **Occupancy / blocking:** the dataset has a baseline+blocked cohort (10 subjects), but blocked/baseline V_T is 0.80–1.07 (weak, inconsistent COX-2 displacement in healthy brain) — no well-posed occupancy, so not used.

The honest, large, **distinct** lever on this dataset is **model order**, and that is what is gated.

### Verifier (3 plain checks, human-looking pytest)

`tests/test_outputs.py`: (1) cortical V_T present for the ~27-participant cohort, plausible range, and an arterial-input kinetic estimator actually named; (2) **reproduction** — cohort-mean cortical V_T in the validated band **[1.90, 2.60]** AND a ≥1.4× per-participant spread; (3) a kinetic estimator/model is reported alongside a V_T result (guards against a bare number / SUV / tissue ratio). Check 2 is the mechanical discriminator: a 1TCM fit (~1.45) and an all-frames Logan (~1.86) both fall below the band; only a model adequate to the tracer (2TCM / Logan / MA1, ~2.15) lands inside it.

**Offline discrimination (measured, this build):**

| output | check1 | check2 (reproduce) | check3 | verdict |
|---|---|---|---|---|
| reference solution (Logan + MA1, adequate model) | PASS | PASS (2.174) | PASS | **PASS** |
| 1-tissue-compartment fit | PASS | **FAIL** (1.452) | PASS | **FAIL** |
| all-frames Logan (t*=0) | PASS | **FAIL** (~1.86) | PASS | **FAIL** |

### Difficulty — NOT yet gated (frontier runs pending)

Oracle passes (reward 1.0 offline; `compute.py` fetches live OpenNeuro and writes the three artefacts). The 1TCM naive output fails as tabulated. The **≥2-frontier-family, k≥3 difficulty gate has not been run** (no Harbor/agent access in this authoring session) — recorded as **untested difficulty**. Honest expectation: an agent that reaches for the simplest compartmental model (1TCM) for "fit a kinetic model" gets a plausible but ~33%-low V_T; agents that use a graphical estimator or check model adequacy pass. If frontier agents pass easily, the ratchet is to also withhold the input-construction note (re-adding PETVT's trap on top) rather than adding rigor.

### Data provenance / reliability caveats

- Fetch is the OpenNeuro file API (`/snapshots/1.4.0/files/<colon-path>`, 302→S3); no credentials; pinned to snapshot **1.4.0**. License **CC0**.
- One combined-regions TAC file holds all participants; per-scan blood files are fetched individually (27 × ~1 KB).
- n = 27 (baseline/drug-free scan per participant). The oracle grades the **cohort mean**, robust to which subset (baseline-cohort mean ~2.14, test-cohort mean ~2.28 both in band); per-participant V_T is reported for the spread check.

### Cost

`hard` bracket by convention; light in practice (fetches one ~3 MB TAC table + 27 tiny blood TSVs; Logan/MA1 fits run in seconds; a per-scan 1TCM cortical fit is computed only to document the pitfall). cpus 2, mem 4 GB, internet on, timeouts 1800–3000 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3.
