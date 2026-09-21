## SOCIALBRAIN-001

**Proposal Title:** Reproduce Richardson 2018's anti-correlation headline — an un-cued GSR-dependence trap (the *hard* reproduction)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental functional connectivity

**Source paper:** Richardson et al. (2018), *Nature Communications*, https://doi.org/10.1038/s41467-018-03399-2 (dataset: OpenNeuro ds000228, via `nilearn.fetch_development_fmri`).

**Status: FULL runnable task, validated end-to-end; DEFEATS both frontier agents.** Built with the `tb-science-task-authoring` skill.

### Why this exists

A *clean* reproduction of a robust result is authentic but **easy** — during development an easy control variant (reproduce-and-report Richardson's within-network maturation, pipeline fully pinned) was measured and **both frontier agents passed**, simply computing and reporting honestly. The finding: difficulty comes from **un-cued volunteered judgement**, not reproduction-by-computation. This task injects exactly that into the reproduction genre — reproduce the famous *headline*, whose reproducibility hinges on a preprocessing choice (GSR) the agent must volunteer to investigate. (The easy control was validated then not shipped; this is the hard task.)

### The trap (Step-0 validated, real)

Richardson's headline — ToM and pain networks become increasingly anti-correlated with age (r_s≈−0.35) — reproduces **almost exactly, but only under global-signal regression (GSR)**:

| pipeline | across-network vs age (children) | adult mean |
|---|---|---|
| standard clean (confounds, detrend, z-score, **no GSR**) | r_s = **−0.07**, p=.45 (n.s.) | −0.08 |
| **+ global-signal regression** | r_s = **−0.34**, p=1e-4 | −0.20 |
| Richardson (paper) | r_s = −0.35, p<1e-4 | −0.17 |

GSR is mathematically known to introduce/strengthen negative correlations (Murphy 2009; Saad 2012; Murphy & Fox 2017). So an anti-correlation present only under GSR is **GSR-dependent, not a robust developmental effect**. The honest answer reports that dependence. ROIs are pinned; **preprocessing is left free** and the instruction is un-cued (no mention of GSR, robustness, or sensitivity).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) connectivity computed; (2) `findings.md` recognises the **GSR-dependence** — that the anti-correlation reproduces *with* GSR and not *without* (or that GSR induces it) — **not** a flat "reproduces"/"doesn't", and not merely naming the pipeline.

### Difficulty — MEASURED (Step 5): defeats both frontier agents

| agent | reward | what it did |
|---|---|---|
| **GPT-5.5 (codex, xhigh)** | **FAIL** | one pipeline (no GSR, bandpass), across r=−0.155 (n.s.) → "supports only the direction, not a clear reproduction." Never tested GSR. |
| **Claude Opus 4.8** | **FAIL** | one pipeline (no GSR, bandpass), across r=−0.156 (n.s.) → flat "does not reproduce." Generic ROI/pipeline caveat but never tested GSR. |

Both ran a single standard pipeline, got the null, and gave a flat verdict — **neither volunteered the GSR-sensitivity analysis** that reveals the real (GSR-dependent) story. The un-cued trap works.

**Verifier-integrity note (the skill's inspect-real-outputs lesson, live):** the first verifier version *false-passed* GPT-5.5 because it wrote "no global signal regression" to describe its pipeline and a bare `no global signal` regex branch counted that as the insight. Inspecting the captured output caught it; the check now requires GSR to be *linked to the result* (re-tuned and verified against the real GPT/Claude outputs + adversarials).

### Discrimination (validated locally)

| solution | verdict |
|---|---|
| reference (runs both pipelines, reports GSR-dependence + artifact caveat) | **PASS** |
| genuine "null without GSR, −0.34 with GSR → GSR-dependent" | **PASS** |
| flat "doesn't reproduce" (never tried GSR) | **FAIL** |
| "applied GSR, got −0.35, reproduced!" (no dependence/caveat) | **FAIL** |
| real GPT-5.5 output / real Claude output | **FAIL** |

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads all 155 ds000228 subjects + whole-brain global-signal extraction for the GSR pipeline; timeouts 5400 s). Agent runtimes ~16–22 min. Deps: nilearn 0.12.1 + scipy/sklearn/pandas/nibabel.

---

## Proof-of-work rebuild (verifier hardening, 2026-09)

The prior grader **never opened `age_effects.json`** (which holds the headline r/p): it checked
only that `network_connectivity.csv` had in-range columns and that `findings.md` contained a
GSR-dependence sentence — so fabricated per-subject rows plus a keyword sentence passed. This
pass applies the suite-wide **proof-of-work** contract (`scratchpad/PROOF_OF_WORK_SPEC.md`).

**Held-out reference (`tests/reference.npz`, built from `solution/compute.py`, never shipped to
the agent).** Per-subject within-ToM, within-pain, across-network (standard clean, **no GSR**) and
across-network (**with GSR**) for the 122 children + 33 adults of the nilearn-pinned ds000228,
plus age/group. Discriminating statistics: children's Spearman(age, across-network) is
**−0.069 (p = 0.45, n.s.)** without GSR and **−0.343 (p = 1.1e-4)** with GSR — the finding
reproduces *only* under GSR. (The no-GSR↔GSR per-subject across-network correlation is 0.71,
so GSR is a large, real shift, not noise.)

**Four grading pillars** (`tests/test_outputs.py` + `tests/proof_of_work.py`):
1. **Exact subjects + per-item values** — `network_connectivity.csv` must cover ≥90 % of the real
   subjects, be non-constant, and its per-subject standard-clean across-network (and within-ToM)
   must track the held-out reference (cross-subject r ≥ 0.80, per-subject |Δ| ≤ 0.08).
2. **Recompute** — the children's Spearman(age, across-network) recomputed from the submitted rows
   must equal the standard-clean reference (−0.069) *and* the reported `age_effects.json` value.
3. **Discriminating number(s)** — the **GSR-dependence** graded as numbers: the reported
   across-network vs age correlation must be ~null without GSR (~−0.07) and clearly negative with
   GSR (~−0.34), with GSR pulling it markedly more negative. A run that did only one pipeline has
   only one number and fails.
4. **Secondary prose** — negation-aware GSR-dependence recognition; not the sole gate.

**Validation (subprocess pytest per case, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`):**

| case | result |
|---|---|
| honest (oracle reference values) | PASS |
| no `network_connectivity.csv` | FAIL |
| constant across-network table | FAIL |
| non-constant fabricated (real IDs, shuffled, right-ish headline) | FAIL |
| naive standard-clean-only (real no-GSR rows, "does not reproduce", **no GSR number**) | FAIL (pillar 3) |
| naive GSR-only (GSR across as primary, "reproduces") | FAIL (pillars 2, 3) |

Note the naive standard-clean-only case passes pillars 1–2 (its rows are the real no-GSR values)
and fails **precisely** at the discriminating GSR number — the intended teeth.

**Packaging.** Real subjects pinned via `tests/reference.npz`. The raw ds000228 derivatives exceed
GitHub's 100 MB/file limit, so `allow_internet=true` + runtime fetch are retained; baking the
derived per-subject ROI series is a maintainer follow-up. Reference built on
`fetch_development_fmri(n_subjects=155)` with the pinned ToM/pain ROIs, both pipelines.

---

## Second-pass fix (2026-09): un-guess the alternative-preprocessing arm — SEPARATE-PIPELINE 5(a)

The powfix grader still graded the discriminating conclusion (across-network vs age under the
alternative preprocessing) as a **reported scalar** in `age_effects.json`, and `instruction.md`
**quoted the paper's headline** (`r_s ≈ −0.35`, adult `−0.17`). An agent could run only the
standard pipeline, copy `−0.35` into the JSON, and pass the GSR-dependence check without ever
running the second pipeline (red-team attack C).

**This is a SEPARATE-PIPELINE task: running the alternative preprocessing IS the judgement, so the
intermediate cannot be fully neutral.** Per the second-pass brief §5 we take **option 5(a)** — require
the intermediate, framed as neutrally as possible, and recompute the discriminator from it:

- **Removed the answer from `instruction.md`.** The `−0.35` / `−0.17` headline numbers are gone.
- **Neutral intermediate.** The instruction now asks the agent to *"consider the preprocessing
  choices a careful reproduction would weigh, and for each choice you consider, compute and report
  the resulting per-subject across-network correlation"* as a separate column — **without naming
  GSR, global signal, robustness, or sensitivity**. The lever is not named.
- **Recompute, don't read.** The grader collects every across-network column, assigns **by value**
  (not by name) which submitted column is the standard-clean quantity and which is the
  alternative-preprocessing quantity (best per-subject match to `ref_across` / `ref_across_gsr`),
  validates **both** per-subject against the held-out reference (cross-subject r ≥ 0.80, |Δ| ≤ 0.08),
  and **recomputes the children's Spearman(age, across-network) for both columns from the rows**.
  The GSR-dependence is now `r_std ≈ −0.07` vs `r_alt ≈ −0.34` recomputed from validated columns.
- **Why a copy cannot fake the second column.** The standard↔alternative per-subject correlation is
  only **0.71**, below the 0.80 floor, so a monotone copy/offset of the standard column fails the
  reference match; and because a monotone transform preserves ranks, its recomputed Spearman stays
  at the ~null `−0.069`, failing the discrimination pillar. To get `−0.34` the agent must genuinely
  re-rank subjects the way GSR does — i.e. run the second pipeline.

**Residual cue (documented, accepted 5(a) tradeoff).** The neutral schema still tells the agent that
*multiple preprocessing choices matter and each choice's across-network value must be reported per
subject.* This nudges the agent to run more than one pipeline, though it does **not** identify GSR as
the discriminating lever — the agent must still discover that the anti-correlation's reproducibility
hinges specifically on global-signal regression. This is the irreducible cue-vs-guess tension of a
separate-pipeline discriminator; we accept the mild residual hint in exchange for making the
judgement **un-guessable from the paper's published number**.

**Adversarial self-validation (subprocess pytest per case, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`,
numpy-only; honest/defensible built from the exact oracle output schema):**

| case | result | teeth |
|---|---|---|
| honest oracle (both real columns) | **PASS** | — |
| defensible alternative (perturbed real columns, renamed/reordered) | **PASS** | — |
| attack A — real std column + fabricated **random** alternative column | **FAIL** | fake alt fails reference match + recompute |
| attack A — real std column + **flat constant** alternative column | **FAIL** | same |
| attack C — real no-GSR table + **guessed −0.35** scalar in JSON (one column) | **FAIL** | only one pipeline; no validated alt column |
| attack C — real no-GSR column **offset-copied** as a fake GSR column | **FAIL** | corr 0.71 < 0.80; recomputed Spearman stays ~null |

Attack C now FAILS while honest + defensible PASS, so the fix counts.
