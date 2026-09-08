## FCSTAB-001

**Proposal Title:** Within-run stability of the strongest resting-state functional connections — an un-cued regression-to-the-mean / selection-on-extremes artefact

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state functional connectivity / statistical rigor

**Methodological basis:** Galton (1886); Barnett, van der Pols & Dobson (2005), *Int J Epidemiol*, https://doi.org/10.1093/ije/dyh299 ("Regression to the mean: what it is and how to deal with it"). Context on within-scan FC reliability: Laumann et al. (2015), *Neuron*; Noble et al. (2019), *NeuroImage*. Dataset: **ABIDE Preprocessed** via `nilearn.datasets.fetch_abide_pcp` (pipeline `cpac`, band-pass, no GSR, `quality_checked=True`), **Craddock-200 (CC200)** pre-extracted ROI time series.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Replaces the retired MEGAEF-001 (PR #171). Opens a new failure axis — **selection on extremes / regression to the mean** (Step 2 lane D, "top-responders selected, then decline") — not covered by any shipped task, on a **new dataset+atlas** (ABIDE / CC200) distinct from the ds000228, ADHD/MSDL, Schaefer, and language-localizer tasks (anti-monoculture on axis × dataset × atlas).

### Why this exists

The un-cued judgement axes shipped so far are robustness (GRADIENT), confident-refutation (SOCIALBRAIN), and wrong-cause confound (DEVCONN). None probes the **data/sample** family: when units are selected because they are *extreme* on one measurement, their "change" on a second, independent measurement is regression to the mean, not a real effect. This is the single most common way a selection-then-change analysis fools an analyst (Galton; Barnett 2005). The task casts it as a natural resting-state question — are the brain's strongest functional connections stable within a run, or do they weaken as the scan proceeds (a plausible real hypothesis: vigilance drops over an eyes-open rest). The naive analysis (select the top-decile edges on the first half, report their change on the second half) *guarantees* an apparent decline that is pure regression to the mean.

### The lever (Step-0 validated, real, robust)

Two independent measurements are the two contiguous halves of a single resting run (measurement-1 = first-half edge connectivity, measurement-2 = second-half). Select the top decile of edges by first-half connectivity; look at the same edges in the second half. On the first 40 ABIDE subjects (CC200, Fisher-z edges, equal halves ~98 TRs each, 19,900 edges/subject):

| edge set (selected on first half) | first-half z | second-half z | change | reads as |
|---|---|---|---|---|
| **TOP decile** (strongest) | **0.892** | **0.680** | **−0.212 (−23.7%)** | "strong connections weaken over the run" |
| size-matched **RANDOM** set | — | — | **+0.004** | no change (48× smaller; slightly *up*) |
| **WEAKEST** decile (most negative) | −0.159 | +0.110 | **+0.269** | rises symmetrically toward the mean |

38/40 subjects show the top-decile decline; paired *t* (top-change vs random-change) = **−24.5, p = 3e-25**. Robust across the top **1% / 5% / 10%** selection, split point (0.4 / 0.5), atlas (**CC200** and **Dosenbach-160**), and N (40 / 120). The random set does **not** decline and the weakest edges **rise** by a comparable amount — the two-sided convergence toward the grand mean is the unambiguous signature of regression to the mean, and rules out a genuine "connections weaken over the scan" process (which would drag an unselected set down too, and could never make the most-negative edges strengthen).

**No-fake-traps discipline:** the "decline" is real and reproduces; what is wrong is the naive *interpretation*. There is no genuine within-run weakening to punish a correct solver for — the honest answer reports the same top-decile numbers and reads them correctly. The controls (random set ≈ 0, weakest-decile symmetric rise) are not required outputs; they are what an honest analyst volunteers.

### Un-cued / off-critical-path

The instruction asks only to split the run, compute per-half connectivity, take the top-decile-by-first-half edges, and report their first-half mean, second-half mean, and change. It never says regression to the mean, selection, bias, artefact, "independent", "control", "random", or "weakest". Producing the required numbers (`stability.csv`, `summary.json`) fully satisfies the deliverable **without** recognising the artefact — so recognition is a *volunteered* judgement in `findings.md`, not a step on the path to the answer. The naive/default analysis — the one a competent-but-uncareful agent actually runs — yields the −24% decline and the wrong conclusion.

### Verifier (2 plain checks, schema-robust)

`tests/test_outputs.py`: (1) `test_stability_computed` — a real per-subject CSV over ~40 subjects, the selected set is genuinely strong (group first-half z > 0.3) and does drop on the second half (reads `summary.json` group means or aggregates the CSV; fuzzy column/key match). (2) `test_recognises_regression_to_the_mean` — the v2 negation-aware, downgrade-driven recognition grader: `findings.md` must recognise the decline as **regression to the mean / a selection effect**, either **by name** (regression/reversion to the mean, winner's curse, or selection coupled to an artefact/cause — a bare name only counts when it sits next to a downgrade/selection/noise token, so a name-drop-then-dismiss answer fails) or **operationally** (a random/unselected control that does not decline, the weakest edges symmetrically rising, "would appear even without a real change", or "no genuine within-run weakening"). A conclusive un-negated affirmation that the strong edges *genuinely* weaken vetoes the name/selection routes (guarded against hypotheticals and refuted setups); the operational demonstration always passes.

**Offline discrimination (locked; real grader vs 11 fixtures rendered from the analysis):**

| answer | recognition |
|---|---|
| reference oracle (names RTM + shows both controls) | **PASS** |
| operational only — random control ≈ 0, no RTM name | **PASS** |
| operational only — weakest edges rise symmetrically | **PASS** |
| minimal "…is regression to the mean: selected on a noisy first half" | **PASS** |
| "…would appear even without a real change… ranked on the first half" | **PASS** |
| naive "the strongest connections weaken over the run" | **FAIL** |
| naive + pipeline vocab (regressed nuisance, test-retest reliability) | **FAIL** |
| generic caution hedge ("edges are noisy, interpret cautiously") | **FAIL** |
| confident-refutation hedge ("not perfectly stable") | **FAIL** |
| name-drop "regression to the mean", then assert a genuine weakening | **FAIL** |
| "could this be a selection effect? no — it's a real decline" | **FAIL** |

The recognition grader reuses the project-standard v2 helper (`_NEG` / `_neg_before` / `_unnegated`, as in APERIODIC-001) plus a coupling-window check so a bare mechanism name cannot pass on the phrase alone — hardened against the pipeline-vocabulary false-positive class (`regress` → "regressed nuisance"; `reliability`, `noise`) documented in SOCIALBRAIN/DEVCONN.

### Difficulty status

Oracle **reward 1.0** in-container path validated (reference `compute.py` writes all deliverables; grader passes both checks). The construction bar is met: un-cued, off-critical-path, naive-default-is-wrong, big robust Step-0 gap (48× top-vs-random; p = 3e-25), guarded fair grader (oracle passes, naive/hedge/dismissal fail, multiple defensible-correct variants pass), no training-recall giveaway (not the headline of any dataset tutorial). **The live ≥2-family frontier gate (k≥3) is the maintainer's Step-5 and has not been run here** — this proposal claims the construction bar, not a measured frontier failure rate.

### Cost & reliability

`hard`. cpus 2, mem 8 GB, `allow_internet=true`. Runtime fetch is the ABIDE CC200 **pre-extracted ROI time series** for 40 subjects + phenotypic CSV (~10 MB of small `.1D` text files) — far lighter than the nifti/masking tasks; compute is trivial (per-subject 200-ROI correlations). Timeouts 3600 s agent / 1800 s verifier are generous. Deps: nilearn 0.12.1 + numpy/scipy/sklearn/pandas/nibabel (pinned, matches DEVCONN). Dev/agent runs may mount the host `nilearn_data` cache to skip the download (local flag only, never committed); external runners/CI still fetch from the ABIDE derivatives server, which can throttle — flagged as the usual reliability caveat.
