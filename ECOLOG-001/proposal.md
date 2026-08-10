## ECOLOG-001

**Proposal Title:** Characterise the connectivity–age relationship across ABIDE sites — an un-cued ecological-fallacy / aggregation-inflation trap (the *wrong-level inference* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site functional connectivity / developmental neuroimaging

**Source paper (naive narrative):** Dosenbach et al. (2010), *Science*, https://doi.org/10.1126/science.1194144 (resting-state functional connectivity tracks brain maturation) — the established connectivity–age link. Aggregation critique: Robinson (1950), *Am. Sociol. Rev.* ("Ecological correlations and the behavior of individuals") — the foundational ecological-fallacy paper, which recurs in multi-site/aggregated neuroimaging correlations. Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; the rigor genre (characterise the across-site relationship → the honest answer volunteers that the aggregate does not license individual inference), modelled on GRADIENT-001.** No naive-narrative paper reports the *site-level* number, so a faithful "reproduce paper X's headline number" framing is not available; the task is the characterise/rigor shape, and the individual-level comparison is the hidden check the brief does not spell out.

### Why this exists

Across ABIDE's ~20 sites, which differ in mean age, correlating a site's mean connectivity with its mean age is the natural group-level question — and it gives a sizeable correlation. The un-cued judgement is that this aggregated (site-mean) correlation is **~5× the individual-level one**, because between-site means are a lower-noise signal than the noisy individual data — so it does not describe how connectivity relates to age within people (the ecological fallacy, Robinson 1950). The agent is asked to characterise the across-site relationship; it fails only if it does not *volunteer* that the aggregate over-states the individual association. Failure axis **wrong-level inference / aggregation** — a distinct cell from HUBMAP (group hub identity ≠ individual ranking), GMVOL (correction-method sign flip), BWAS (genuinely tiny effect), and RANGE (sampling-range attenuation).

### The reproduction (Step-0 validated) — the aggregated relationship holds at face value

ABIDE, Craddock-200, 1035 subjects / 20 sites: correlating each site's mean connectivity with its mean age gives r = **+0.35** (n = 20 sites) — a clean, positive connectivity–age relationship at the level the task asks about. A naive analysis stops here and reports "connectivity increases with age, r = 0.35."

### The trap (Step-0 validated) — the individual-level effect is ~5× smaller

| level | connectivity–age r |
|---|---|
| **site-mean (ecological)**, n = 20 sites | **+0.35** |
| **individual**, n = 1035 | **+0.07** |

The site-level correlation is ~**4.9×** the individual one; the same pattern holds for mean-FC ~ FIQ (**0.27** vs **0.07**, ~4.2×). Aggregating to site means inflates the correlation, so the large site-level number does not license inference about individuals. The honest answer volunteers this; a flat "connectivity increases with age, r = 0.35" over-states it. The instruction is un-cued: it names the across-site method in full, but **never mentions the ecological fallacy, aggregation-vs-individual, the individual level, or Robinson**.

**Honesty note (no-fake-traps discipline, from Step-0).** The effect is real at both levels and the inflation is measured, not contrived: the individual-level r ≈ 0.07 is a genuine (small) association, and the ~5× gap replicates on a second phenotype (FIQ). The trap is not "the effect is fake" but "the aggregate over-states the within-person relationship" — the ecological fallacy, quantified.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_correlation_computed` — a connectivity–age correlation result is present in `*.json`; (2) `test_recognises_ecological_fallacy` — `findings.md` recognises that the site-mean (aggregated) correlation over-states / does not license the individual association (aggregation inflates; the within-person effect is much smaller) — **not** a flat "connectivity increases with age, r = 0.35," and **not** a name-drop-then-affirm dismissal ("this is not the ecological fallacy; the site-mean genuinely reflects individuals"). The recognition must LINK the aggregation/group level to over-stating the individual relationship.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (site r ≈ 0.35 but individual r ≈ 0.07 → ecological fallacy, aggregate over-states) | **PASS** |
| genuine "aggregating to site means inflates the correlation; person-by-person it nearly vanishes" | **PASS** |
| flat "connectivity increases with age, r = 0.35" (no individual check) | **FAIL** |
| "this isn't the ecological fallacy; the site-mean reflects individuals" (dismissal, no coupled downgrade) | **FAIL** |
| "correlations can differ across scales generally" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the site-level correlation (~0.35), report it as *the* connectivity–age relationship, and — un-cued — do **not** volunteer the individual-level comparison that shows the aggregate is ~5× inflated. This mirrors the measured behaviour on DEVCONN-001 and GRADIENT-001, where frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it avoids a bare "ecological fallacy" trigger (a dismisser name-drops it) and a bare "site correlation is inflated" trigger (dismissers negate it at a distance); the coupled downgrades assert the honest mechanism (aggregating over-states; between-site means are lower-noise; person-by-person the effect vanishes) that dismissers do not assert, and there is **no** fragile "genuine"-veto so the honest oracle passes. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads ABIDE cc200 ROI time series — small, cached after first run). Deps: nilearn 0.12.1 + scipy/numpy/pandas. One connectome extraction per subject then two correlations; timeouts generous.
