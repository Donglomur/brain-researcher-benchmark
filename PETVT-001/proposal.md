## PETVT-001

**Proposal Title:** Estimate the TSPO distribution volume V_T from dynamic [18F]SF51 PET with an invasive (arterial-input) kinetic model — an un-cued input-construction judgement (robustness / reporting-quality axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular imaging / PET pharmacokinetic modelling

**Source finding:** first-in-human evaluation of [18F]SF51, a candidate TSPO (18 kDa translocator protein) radioligand (OpenNeuro **ds005619**, CC0; Yan et al.; monkey precursor Yan et al. 2023 *EJNMMI* 50:2962). Invasive kinetics: Logan et al. 1990 (graphical V_T); Ichise et al. 2002 (MA1); 2TCM. Dataset ships **PETPrep-extracted regional TACs** + **arterial blood** (plasma activity, HPLC parent fraction, whole blood), fetched at runtime from OpenNeuro (open, no credentials, snapshot 1.1.0).

**Status: FULL runnable task — DE-CUED this revision; grader re-validated on real data.** Second real-data PET task (after PETREF-001) and the first **invasive / arterial-input** one. New on three axes vs PETREF: **dataset** (ds005619, not ds001420), **tracer/target** (TSPO [18F]SF51, not SERT [11C]DASB), and **quantification family** (arterial-input **V_T**, not reference-tissue **BP_ND**). Genre: **reproduction** with an un-cued input-construction judgement.

### De-cue (why this revision exists)

The input-construction judgement was partly **cued**: the instruction enumerated the blood column `metabolite_parent_fraction` and glossed it as "the intact-parent fraction of plasma radioactivity, from HPLC" — handing the agent the exact correction to apply — and the `findings.md` requirement asked it to justify its input "and why." This revision **withholds that cue**: the instruction no longer names or glosses the parent-fraction column (it points the agent to inspect the blood file's own header) and drops the "and why." The agent must now discover from the header that the input is metabolite-corrected parent-in-plasma, so the judgement is genuinely un-cued. The write-up check (`test_input_construction_justified`) was tightened to require the metabolite/parent concept to **co-occur** with an input/plasma/bias context — a bare column-name echo no longer passes.

### Why this exists (new axis: invasive input)

PETREF-001 is a *reference-tissue* PET task (no blood). Many important tracers — TSPO among them — have **no reference region** and must be quantified against a **metabolite-corrected arterial plasma** input. Building that input from a raw blood recording is the central, easily-mishandled step of invasive PET quantification, and it is genuinely off the critical path: an agent can produce a plausible-looking V_T from the wrong input and never notice.

### Step-0 (validated, real — reproduces on obtainable data)

Fetched the 7 participants' PETPrep TACs + arterial blood (no credentials) and estimated **cerebral-cortex V_T** with Logan (Ichise MA1 as cross-check), input = metabolite-corrected, decay-referenced arterial plasma (`plasma × parent_fraction × exp(+λt)`, λ for 18F):

| sub | Logan V_T | MA1 V_T |
|---|---|---|
| sf02 | 1.067 | 1.060 |
| sf05 | 0.628 | 0.627 |
| sf06 | 0.999 | 0.993 |
| sf07 | 0.781 | 0.778 |
| sf08 | 0.456 | 0.455 |
| sf09 | 0.523 | 0.523 |
| sf10 | 1.127 | 1.117 |

Cohort-mean cortical **V_T = 0.797 mL·cm⁻³** (< 1), **max/min = 2.47×**, Logan≈MA1 to ~1%. This reproduces the source study's two headline findings: [18F]SF51 has **notably low brain V_T (< 1)** yet **remains sensitive to the rs6971 polymorphism** (~2× V_T range across affinity genotypes). Estimator- and window-invariance confirmed: Logan V_T over t* = 20/30/40/60 min gives cohort means 0.782/0.797/0.809/0.820 (a 5 % drift — at equilibrium over the full ~120-min scan). Units cross-checked against the paper (cortex peak SUV ≈ 1.47 at 3 min vs the reported "SUV 1.4 at 3 min").

### The un-cued lever (Step-0 measured — LARGE, and adversarially "confirming")

The input to an arterial-input V_T is the **metabolite-corrected arterial plasma of the intact parent**. The blood file ships three columns from which a plausible input can be built; only one is correct. Measured cohort-mean cortical V_T under each:

| model input | cohort-mean V_T | vs correct |
|---|---|---|
| **metabolite-corrected plasma, decay-referenced** (correct) | **0.797** | — |
| plasma **without** parent-fraction (metabolite) correction | 0.514 | **−35 %** |
| **whole-blood** instead of plasma | 0.448 | **−44 %** |
| plasma left on a different **decay** footing than the TACs | 1.011 | **+27 %** (Logan also fails to plateau: 16 % t* drift) |

The decay convention is proven, not assumed: Logan V_T drift over t* is minimised at **exactly one** decay-correction of the raw blood (+16 % at N=0, **+5 % at N=1**, −6 % at N=2), i.e. the samples are stored un-decay-corrected and must be brought onto the TACs' injection-time footing. The instruction states only the neutral data facts (samples recorded at draw time; radioactivity in Bq/mL) and points the agent to the blood file header; the **plasma-vs-whole-blood and parent-fraction corrections are now fully un-cued** (the parent-fraction column is no longer named or glossed) — those carry the −35 %/−44 % gaps.

**Adversarial property:** the two naive inputs push V_T **lower** (0.45–0.51) — *even more* consistent with the paper's "V_T < 1" headline than the correct 0.80. An agent that skips the parent-fraction correction or grabs whole-blood gets a number that *feels confirmed*. This is the trap.

**Honesty note (no-fake-traps discipline):** the numeric lever is genuinely large (−35 % to −44 %), unlike PETREF-001's ~3 % reference-region lever. The graphical **t\*/scan-window** choice, by contrast, is *weak* here (Logan V_T stable to ~5 % across t* 20–60 min; a 0–60 min truncation only −8 %), because [18F]SF51 equilibrates fast — so this task is **not** framed around the window lever the original PATLAKKI/SUVR briefs anticipated; the honest, large lever on this dataset is **input construction**, and that is what is gated.

### Verifier (3 plain checks, human-looking pytest)

`tests/test_outputs.py`: (1) cortical V_T present for the ~7-participant cohort, physiologically plausible, and an invasive V_T estimator actually named; (2) **reproduction** — cohort-mean cortical V_T in the validated band **[0.68, 0.92]** AND a ≥1.6× per-participant spread (the ~2× genotype range); (3) **input justified** — `findings.md` articulates the model input as a considered choice, with the metabolite/parent-correction concept **co-occurring** with an input/plasma or a bias/choice context (or an explicit statement that V_T depends on the input construction), not merely "we used the arterial input" and not a bare column-name echo (the same pipeline-vocabulary false-positive class guarded against in SOCIALBRAIN/DEVCONN). Check 2 is the mechanical discriminator: you cannot land in [0.68, 0.92] without the correct input construction; check 3 additionally requires the agent to have *volunteered* the judgement now that the cue is withheld.

**Offline discrimination (re-validated on real data, this revision):**

| output | check1 | check2 (reproduce) | check3 (justify) | verdict |
|---|---|---|---|---|
| reference solution (Logan, metabolite-corrected plasma, full reasoning) | PASS | PASS (0.797) | PASS | **PASS** |
| whole-blood input | PASS | **FAIL** (0.448) | **FAIL** | **FAIL** |
| plasma, no metabolite correction | PASS | **FAIL** (0.514) | — | **FAIL** |
| correct V_T but terse "arterial input" report (no volunteered judgement) | PASS | PASS (0.797) | **FAIL** | **FAIL** |

### Difficulty — NOT yet gated (frontier runs pending)

Oracle passes (reward 1.0 offline on live-fetched real data this revision; the reference `compute.py` fetches live OpenNeuro and writes the three artefacts; `harbor -a oracle` to confirm in-container). Adversarial input choices fail as tabulated. The **≥2-frontier-family, k≥3 difficulty gate has not been run** (no Harbor/agent access in this authoring session). **Honest expectation:** the input-construction judgement is now genuinely un-cued (the parent-fraction column is withheld from the instruction) and the naive shortcuts return an *even more paper-consistent* number, so this is a plausible **hard** candidate; but until the gate runs it is recorded as **untested difficulty**. If agents still pass, the remaining ratchet is to also withhold the decay-footing note (adding a third input trap) rather than adding rigor.

### Data provenance / reliability caveats

- Fetch is the OpenNeuro file API (`/snapshots/1.1.0/files/<colon-path>`, 302→S3); no credentials. Pinned to snapshot **1.1.0**. TACs are the `pvc-nopvc`-equivalent (uncorrected) `desc-gtmseg` extraction; a `pvc-agtm` variant also ships but PVC is not gated here.
- License **CC0** (`dataset_description.json`).
- Small cohort (n = 7, all baseline). The oracle grades the **cohort mean**, which is robust; per-participant V_T is reported for the spread check.

### Relationship to the assigned brief (PATLAKKI / SUVRWIN)

Delivered in the PATLAKKI-001 slot (graphical kinetic quantification with an off-critical-path input/window lever). The assigned *irreversible-tracer Patlak Ki* and *tau/amyloid SUVR-window* instantiations were **not buildable on obtainable, container-feasible open data** (see the campaign report): across all 36 OpenNeuro PET datasets, only ds001420 (used by PETREF-001) and ds005619 ship pre-extracted regional TAC tables; every dynamic-FDG set is 10–76 GB of raw images with no TACs and no in-container segmentation, and the tau/amyloid sets ship neither regional TACs nor reference-region masks. ds005619 (reversible TSPO, arterial input → V_T) is the one feasible new substrate, so the graphical-kinetics task is realised as a **V_T** reproduction with the input-construction lever — a different dataset, tracer and quantity from PETREF-001.

### Cost

`hard` bracket by convention; actually light (fetches 7 × ~60 KB TAC TSVs + 7 × ~1.5 KB blood TSVs; Logan/MA1 fits run in seconds). cpus 2, mem 4 GB, internet on, timeouts 1800–3000 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3.
