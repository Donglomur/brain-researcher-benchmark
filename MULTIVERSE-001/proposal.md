## MULTIVERSE-001

**Proposal Title:** Characterise the developmental age–connectivity effect (Supekar 2009) — an un-cued specification-curve instability (the *point-estimate / no-multiverse* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental functional connectivity / analytic robustness

**Source paper:** Supekar et al. (2009), *PLoS Biology*, https://doi.org/10.1371/journal.pbio.1000157 ("Development of Large-Scale Brain Networks in Children" — resting-state functional connectivity changes systematically with age across development); related developmental-FC primaries: Fair et al. (2009), Dosenbach et al. (2010). Multiverse critique (the hidden check): Steegen et al. (2016) (specification-curve / multiverse analysis). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, quality-checked, controls).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; rigor genre (test a widely-cited primary claim, find it is not robust), modelled on the shipped GRADIENT-001.** Failure axis **point-estimate / no-multiverse** (statistical-inference family), topic *developmental FC / specification curve*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists

The developmental age–connectivity effect is real enough to appear under one standard pipeline, but its sign and significance are decided by the parcellation choice. Characterised at face value it reproduces the widely-reported developmental integration account. The un-cued judgement is to report the **specification curve** — that the effect is choice-dependent — rather than a single point estimate. Exactly the shipped GRADIENT pattern: take a widely-cited primary claim, test whether it robustly reproduces, and find it does not.

### The reproduction (Step-0 validated) — the effect appears under a standard pipeline

ABIDE, quality-checked **controls** (n ≈ 455), Craddock-200, band-pass, no GSR: whole-brain connectivity strength correlates with age, **r = +0.10, p = 0.027**, and it survives motion control (partial r ≈ +0.10 with mean framewise displacement partialled out). Taken alone this reproduces the widely-reported developmental increase in resting-state connectivity (Supekar 2009 integration account). A naive analysis stops here and reports "connectivity increases with age."

### The trap (Step-0 validated) — it is not robust to the parcellation

Specification curve over defensible choices (atlas × GSR × band-pass), same QC controls, mean-FD partialled out:

| atlas | age–connectivity r | significant? |
|---|---|---|
| **cc200** (4 specs) | **+0.10 … +0.16** | **yes (all p < 0.05)** |
| **dosenbach160** (4 specs) | −0.01 … −0.04 | no (all n.s.) |

r range **−0.04 … +0.16, sign flips**, only **50 %** of specs significant. The **parcellation choice alone** flips the conclusion on identical, motion-controlled subjects. The honest answer volunteers this specification curve; a single-pipeline point estimate over-claims robustness. The instruction is un-cued: it fixes one standard parcellation (Craddock-200) and asks to characterise the age–connectivity relationship, but **never mentions a multiverse, a specification curve, the second parcellation, or robustness across analytic choices**.

**Honesty note (no-fake-traps discipline, from Step-0).** The earlier draft inflated the range to **r = −0.53** by using **non-quality-checked, unfiltered, mixed ASD+control** data — questionable choices masquerading as a big effect. I re-ran the multiverse on **QC'd controls only, with band-pass, and mean-FD partialled out**; the honest range is smaller (−0.04 … +0.16) but every specification is defensible and the **atlas-driven sign flip is real and motion-robust**. This is a genuine quality fix, not a re-labelling. (Also: Fair 2009's DMN-specific maturation does *not* reproduce here, r = −0.04 n.s. — so the anchor is the whole-brain developmental-integration claim, not the DMN-specific one.)

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_effect_computed` — an age–connectivity correlation is present in `*.json`; (2) `test_reports_choice_dependence` — the submission either reports a multiverse of ≥4 specifications (a structured list of spec dicts) OR `findings.md` recognises the effect is **choice-dependent** (the result depends on / the parcellation alone decides / the sign flips across atlases). A single point estimate with a flat yes/no fails; a name-dropped multiverse that then affirms robustness fails. The recognition must LINK the variability to the RESULT, not merely name the pipeline components.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports r = +0.10 under cc200, then the specification curve → sign flips, only half significant, parcellation decides it) | **PASS** |
| genuine "positive under cc200, ~null under the other atlas → no single defensible point estimate" | **PASS** |
| reports a structured ≥4-spec multiverse list | **PASS** |
| flat "connectivity increases with age, r = +0.10" (one pipeline) | **FAIL** |
| flat "no age effect" (one pipeline) | **FAIL** |
| "ran a multiverse, effect robustly positive" (name-drop, no coupled downgrade) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run one pipeline, get a single age–connectivity point estimate (positive or null), and report it as the answer, but — un-cued — do **not** volunteer the specification curve showing the sign and significance are decided by the parcellation choice. This mirrors the measured behaviour on GRADIENT-001, where both frontier families computed correctly yet asserted a single confident result without the across-choice robustness check. **Modest-magnitude note:** the demonstration rests on the *sign flip across atlases*, not effect size (max |r| ≈ 0.16); this is honest — the earlier draft's larger range was an artifact of bad specs.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it passes on a reported ≥4-spec multiverse OR the RESULT coupled to the analytic choice (e.g. "the effect depends on the parcellation," "positive under one atlas, null under another," "the sign flips with atlas"), and treats an all-positive cc200 range dressed as "robust" or a bare pipeline-component list as NOT a downgrade — so a name-drop-then-affirm dismissal fails WITHOUT a fragile "robust"-veto, and the honest oracle passes even where it notes the effect IS detectable under one pipeline (a CONTRAST condition). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 + Dosenbach-160 ROI time series — small, reliable S3 host; the second parcellation is fetched only by the oracle's volunteered multiverse, not required of the agent). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
