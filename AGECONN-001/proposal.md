## AGECONN-001

**Proposal Title:** Characterise the developmental age–connectivity effect (Supekar 2009) — an un-cued specification-curve instability (the *point-estimate / no-multiverse* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental functional connectivity / analytic robustness

**Source paper:** Supekar et al. (2009), *PLoS Biology*, https://doi.org/10.1371/journal.pbio.1000157 ("Development of Large-Scale Brain Networks in Children" — resting-state functional connectivity changes systematically with age across development); related developmental-FC primaries: Fair et al. (2009), Dosenbach et al. (2010). Multiverse critique (the hidden check): Steegen et al. (2016) (specification-curve / multiverse analysis). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, quality-checked, controls).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; rigor genre (test a widely-cited primary claim, find it is not robust), modelled on the shipped GRADIENT-001.** Failure axis **point-estimate / no-multiverse** (statistical-inference family), topic *developmental FC / specification curve*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists

The developmental age–connectivity effect is real enough to appear under one standard pipeline, but its sign and significance are decided by the parcellation choice. Characterised at face value it reproduces the widely-reported developmental integration account. The un-cued judgement is to report the **specification curve** — that the effect is choice-dependent — rather than a single point estimate. Exactly the shipped GRADIENT pattern: take a widely-cited primary claim, test whether it robustly reproduces, and find it does not.

### The reproduction and the trap (validated) — held privately

The validated numbers (the standard-pipeline point estimate, the full specification-curve r-range and which specs are significant, the cc200-vs-dosenbach160 means, and n) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4: the repo is public). In brief: under a standard single pipeline (Craddock-200, band-pass, no GSR, mean absolute connectivity, mean-FD partialled out) the age–connectivity correlation is a weak, non-significant positive — the developmental-integration reading, taken at face value. But across a specification curve over defensible choices (**parcellation × temporal filtering × how connectivity strength is summarised**) on the SAME quality-checked controls with mean-FD partialled out, the correlation **flips sign** and only a minority of specs are significant — and the **parcellation alone decides the sign** (Craddock-200 positive/n.s., Dosenbach-160 negative/several significant). The honest answer volunteers this choice-dependence; a single-pipeline point estimate over-claims robustness. The instruction is un-cued: it names the standard Craddock-200 pipeline and leaves the other choices to "common practice," but **never mentions a multiverse, a specification curve, a second parcellation, or robustness across analytic choices**.

**Route-a (fetch at runtime).** Deliberately not packaged offline: bundling both parcellations would telegraph "compare atlases" and defeat the un-cued trap, so the agent is told only about the standard Craddock-200 pipeline and fetching a *second* atlas is the un-cued initiative. `allow_internet = true`; rule-4 via private grading.

**Repair applied (#9):** the filtered vs unfiltered specs are the actual `band_pass_filtering=True` vs `False` ABIDE derivatives — no in-code re-filtering, so the filtering axis is a genuine pipeline difference (the old "double-filtering" bug is gone).

**Honesty note (no-fake-traps discipline).** An earlier draft claimed the Craddock-200 effect was significantly POSITIVE and Dosenbach-160 NULL. On QC'd controls with mean-FD partialled out that exact pattern does not reproduce; what robustly reproduces — across four connectivity-strength definitions and both filterings — is the atlas-driven SIGN FLIP (cc200 positive n.s., dos160 negative significant). The scientific point (the conclusion is choice-dependent) is unchanged and, if anything, stronger (a sign flip, not merely a significance flip). A still-earlier draft's larger range (|r| ≈ 0.5) came from non-quality-checked, unfiltered, mixed ASD+control data — dropped.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_effect_computed` — an age–connectivity correlation is present in `*.json`; (2) `test_reports_choice_dependence` — the submission either reports a multiverse of ≥4 specifications (a structured list of spec dicts) OR `findings.md` recognises the effect is **choice-dependent** (the result depends on / the parcellation alone decides / the sign flips across atlases). A single point estimate with a flat yes/no fails; a name-dropped multiverse that then affirms robustness fails. The recognition must LINK the variability to the RESULT, not merely name the pipeline components.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the cc200 point estimate, then the specification curve → sign flips, only a minority significant, parcellation decides it) | **PASS** |
| genuine "positive/n.s. under cc200, negative/significant under the other atlas → no single defensible point estimate" | **PASS** |
| reports a structured ≥4-spec multiverse list with genuine spread | **PASS** |
| flat "connectivity shows a weak positive relationship with age" (one pipeline) | **FAIL** |
| flat "no age effect" (one pipeline) | **FAIL** |
| "ran a multiverse, effect robustly positive" (name-drop, no coupled downgrade) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run one pipeline, get a single age–connectivity point estimate (positive or null), and report it as the answer, but — un-cued — do **not** volunteer the specification curve showing the sign and significance are decided by the parcellation choice. This mirrors the measured behaviour on GRADIENT-001, where both frontier families computed correctly yet asserted a single confident result without the across-choice robustness check. **Modest-magnitude note:** the demonstration rests on the *sign flip across atlases*, not effect size (modest |r|, ≲ 0.15); this is honest — the earlier draft's larger range was an artifact of bad specs.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it passes on a reported ≥4-spec multiverse OR the RESULT coupled to the analytic choice (e.g. "the effect depends on the parcellation," "positive under one atlas, null under another," "the sign flips with atlas"), and treats an all-positive cc200 range dressed as "robust" or a bare pipeline-component list as NOT a downgrade — so a name-drop-then-affirm dismissal fails WITHOUT a fragile "robust"-veto, and the honest oracle passes even where it notes the effect IS detectable under one pipeline (a CONTRAST condition). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 + Dosenbach-160 ROI time series — small, reliable S3 host; the second parcellation is fetched only by the oracle's volunteered multiverse, not required of the agent). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
