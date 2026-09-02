## ALLENCONN-001

**Proposal Title:** Mesoscale projection-connectome density — an un-cued injection-site
masking trap (the *measurement-contamination* axis, on a new dataset + modality)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Mesoscale
structural connectomics (anterograde viral tracing, mouse)

**Source paper:** Oh et al. (2014), *Nature*, "A mesoscale connectome of the mouse brain"
(https://doi.org/10.1038/nature13186). Data: the Allen Mouse Brain Connectivity Atlas via
`allensdk.core.mouse_connectivity_cache.MouseConnectivityCache` (manifest + structure-unionize
records downloaded at runtime).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Oracle +
naive discrimination validated locally (below). **Step-5 frontier calibration PENDING** (the
≥2-frontier-family gate is a maintainer step). Opens a **new dataset and modality** — animal,
mesoscale, structural anterograde tracer — breaking the human-fMRI / ds000228 monoculture of
the first tasks, and a **measurement-contamination** failure axis (a saturated data
compartment that must be masked, adjacent to the wrong-cause axis).

### Why this exists

Every shipped task sits on human resting-state fMRI (ds000228). This one moves to a
completely different substrate — the Allen mouse mesoscale connectome — and a different kind
of un-cued judgement: not a preprocessing choice or a confound, but a **data-provenance
artifact**. The Allen structure-unionize records carry an `is_injection` flag; the
`is_injection=True` rows are tracer signal *inside the injection site*, which is saturated and
is **not** a projection to a target region. A first-order connectome descriptor — "what
fraction of region-pairs are strongly connected?" — is roughly **doubled** if those saturated
injection compartments are counted as connections. The instruction asks for the descriptor and
never mentions the injection flag; whether the agent recognises and masks the injection-site
signal is the test.

### The trap (Step-0 validated, real)

Cohort pinned: **498 wild-type** (`cre=False`) anterograde experiments, the **316 summary
structures** (`structure_set_id = 167587189`), whole-structure (`hemisphere_id = 3`)
`projection_density`, strong-connection threshold **0.1**. Matrix = directed source-region ×
target-structure (source = primary injection structure mapped to its summary ancestor; mean
`projection_density` over experiments per source region; 157 injected source regions × 316
targets = 49612 region-pairs, **no missing cells**).

| | strong-connection fraction | n strong / n pairs |
|---|---|---|
| **injection-site signal EXCLUDED** (`is_injection=False`) — correct | **0.0234** | 1162 / 49612 |
| **injection-site signal INCLUDED** (default `is_injection=None`) — naive | **0.0497** | 2468 / 49612 |

The injection compartments are saturated: **median `projection_density` 0.816** in
`is_injection=True` rows vs **0.000106** in genuine projection targets (~**7700×**). Because
projection density in real targets almost never exceeds 0.1, those saturated compartments
dominate the "strong" count when not excluded, and the fraction nearly doubles.

**Robustness (Step-0):**
- **Split-half stable.** Over 10 seeded experiment split-halves, the injection-masked fraction
  is 0.0243 ± 0.0026; the naive−correct **gap is 0.0239 ± 0.0011** (range 0.0214–0.0253) — the
  doubling replicates on either half.
- **Naive value robust to bookkeeping.** With injection included, how a careless analyst
  collapses the duplicate (injection + non-injection) rows for a structure barely matters:
  max-dedup 0.0497 / mean-dedup 0.0450 / sum-dedup 0.0506 — all ~2× the correct value.
- **Correct value robust to aggregation.** Region-mean 0.0234, experiment-level (no region
  averaging) 0.0275, median-over-experiments 0.0199 — all within the grading tolerance.

**Secondary lever (mentioned, not graded).** Swapping the connection metric from
`projection_density` to `normalized_projection_volume` (still injection-masked) shifts the
fraction 0.0234 → 0.0764. Real, but the instruction pins `projection_density`, so it is not
the graded axis; the injection-masking lever is.

**No-fake-trap discipline:** the number is a reproducible measurement on a fixed, obtainable
public dataset (the Allen atlas), the injection saturation is a documented property of the
data (not planted), and the doubling is measured, not asserted.

### Un-cued by construction

`instruction.md` names the deliverable (fraction of strongly connected region-pairs), pins the
cohort / structure set / metric / threshold / matrix construction, and gives standard-practice
latitude for genuinely inconsequential bookkeeping. It **never** mentions the injection flag,
injection-site signal, saturation, masking, contamination, or robustness. The task ID and
title name the *topic* (connectome density), not the lever.

### Verifier (2 plain checks — reproduction genre)

`tests/test_outputs.py` (short reviewer-style pytest, plain asserts, ground truth in the
docstring):
1. **`test_matrix_computed`** — a real directed projection-strength matrix was written
   (≥1000 numeric cells, all in [0,1], not all-zero, not implausibly dense). Schema-robust:
   parses any CSV shape, reads acronyms or ids.
2. **`test_strong_fraction_reproduces`** — the reported strong-connection fraction (searched
   at any depth in `strong_fraction.json`, any JSON `*frac*` key, or the `findings.md` prose /
   percentage) matches the injection-masked value: `abs(reported − 0.0234) < 0.008`.

Deliberately **no lever-word honesty check.** Because the instruction is un-cued, a correct
agent may filter `is_injection=False` silently as good practice and never write the word
"injection"; requiring the word would false-fail a correct solution. The number is the
discriminator — the naive ~0.05 fails the numeric match by a wide margin.

### Discrimination (validated locally, offline — numbers locked)

| output | reported fraction | `test_matrix_computed` | `test_strong_fraction_reproduces` | verdict |
|---|---|---|---|---|
| reference (injection-masked) | 0.0234 | pass | pass | **PASS** |
| naive (injection included, region-mean) | 0.0497 | pass | **fail** | **FAIL** |
| naive dup-mean / experiment-level | 0.0450 / 0.0446 | pass | **fail** | **FAIL** |
| correct median-agg / experiment-level | 0.0199 / 0.0275 | pass | pass | **PASS** |
| wrong full-316-source denominator | 0.0116 | pass | **fail** | FAIL (denominator error, not the science) |

The reference oracle (`solution/compute.py`) computes 0.0234 (1162/49612, n_exp=498,
n_src=157) and passes both checks; every injection-included variant reports ~0.045–0.050 and
fails the numeric match. The 0.008 tolerance (sized to the ~0.0026 split-half sd and the
correct-family spread) passes the correct family (0.0199–0.0275) and fails the naive family
(≥0.045) with no overlap. The full-316-source denominator is an unnatural variant (the natural
`pivot` over injected sources is 157×316 with no NaN → 0.0234); the instruction pins injected
source rows.

### Difficulty hypothesis (Step-5 PENDING)

The injection-masking lever is **off the critical path**: to produce "the fraction of strongly
connected region-pairs" a competent agent need not decide anything about `is_injection` — the
default `get_structure_unionizes` query returns both compartments and a fraction can be
computed straight away. Recognising that the saturated injection-site rows are not projections
and must be excluded is exactly the un-cued, volunteered scientific judgement the suite targets
— analogous to volunteering the GSR check (SOCIALBRAIN-001) or the motion confound
(DEVCONN-001), here on structural connectome data. Expected: an un-cued agent computes the
descriptor over all unionize records and reports ~0.05, missing the ~2× injection inflation.
This must be confirmed with ≥2 frontier families (k≥3 each), hand re-scored — a maintainer step.

### Engineering / reliability caveat

The Allen atlas is fetched at runtime (`allow_internet=true`): the cache manifest plus one
small structure-unionize CSV **per experiment** (498 of them). In development this fetch took
~20–40 min wall-clock and **intermittently throttled/stalled** on individual files (the same
class of runtime-download reliability risk flagged for osf in the skill). The `allensdk`
`MouseConnectivityCache` caches each experiment's CSV to disk, so a restart resumes cheaply and
a warm cache reads in seconds; the oracle timeout is set to 9000 s to absorb stalls. External
runners/CI will still hit the live Allen API. A second reproducibility caveat: the wild-type
experiment count (currently 498) and the resulting fraction could drift slightly if the Allen
API updates the atlas; the 0.008 tolerance provides some buffer. For local dev, `compute.py`
honours `ALLEN_CACHE_DIR` to point at a warm cache and skip the download; the shipped task
still fetches.

### Cost

`hard`. cpus 2, mem 8 GB, internet on. Deps: `allensdk==2.16.2` on `python:3.10`
(numpy 1.23.5 / pandas 1.5.3 / scipy 1.10.1 / h5py 3.16.0 — allensdk pins an old numpy that
will not build on 3.12, hence 3.10). Compute after download is trivial (a pivot + a threshold);
the wall-clock is dominated by the per-experiment fetch.
