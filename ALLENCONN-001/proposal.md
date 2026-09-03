## ALLENCONN-001

**Proposal Title:** Self-referential strongest projections in the mouse mesoscale connectome — an un-cued injection-site masking trap on a per-source argmax descriptor (the *measurement-contamination* axis, on a new dataset + modality)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Mesoscale structural connectomics (anterograde viral tracing, mouse)

**Source paper:** Oh et al. (2014), *Nature*, "A mesoscale connectome of the mouse brain" (https://doi.org/10.1038/nature13186). Data: the Allen Mouse Brain Connectivity Atlas via `allensdk.core.mouse_connectivity_cache.MouseConnectivityCache` (manifest + structure-unionize records downloaded at runtime).

**Status: FULL runnable task, built + hardened with the `tb-science-task-authoring` skill.** Oracle + naive discrimination re-validated on the real streamed data (below). **Step-5 frontier calibration PENDING** (the ≥2-frontier-family gate is a maintainer step). Opens a **new dataset and modality** — animal, mesoscale, structural anterograde tracer — and a **measurement-contamination** failure axis (a saturated data compartment that must be masked).

### Hardening (2026-09) — why the descriptor changed

The task originally graded the **strong-connection density** ("fraction of region-pairs with projection_density > 0.1"). Its one lever — masking the injection-site compartment via `is_injection=False` — is the **standard, documented unionize query**, so it is too in-prior *alone*. I searched, on the real streamed data, for a fair second lever and found none for that descriptor:

| candidate 2nd lever (projection_density, hemi=3) | effect on the density | verdict |
|---|---|---|
| exclude self-loops (matrix diagonal) | 0.0234 → 0.0217 (Δ 0.0017) | **too weak** (< the 0.0026 split-half noise) — cannot gate |
| metric projection_density → normalized_projection_volume | 0.0234 → 0.0764 | strong but a **genuinely contested choice** — must stay pinned (unfair to grade one) |
| hemisphere ipsi / contra / whole | 0.043 / 0.009 / 0.023 | strong but **contested** — must stay pinned |

`is_injection=False` is a **query-level** fix, so no change of descriptor makes the mask itself less known. The one contamination it does **not** remove is the **self / home-region signal** — and that has real signal only in an **argmax** descriptor, not a density. So the descriptor was switched to a per-source argmax statistic where the injection artifact is dramatic and self-concentrated (spec option: *grade a descriptor where injection-masking is less of a documented default*).

### The descriptor and the un-cued lever

**"What fraction of injected source regions have their STRONGEST projection to their own summary structure?"** For each source region take its row of the directed source × target `projection_density` matrix (mean over the experiments sharing that source, whole structure), find the largest entry over all 316 targets (the source's own structure included), and report the fraction whose argmax is the self structure. The brief pins the cohort (498 wild-type `cre=False`), the 316 summary structures (`167587189`), the metric (`projection_density`), the hemisphere (`3`), and the matrix construction. It **never** mentions the injection flag, injection-site signal, saturation, masking, or self-loops.

The off-critical-path choice: the Allen structure-unionize records carry an `is_injection` flag; the `is_injection=True` rows are tracer signal *inside the injection site*, which is **saturated** (median `projection_density` ~0.82). Because the injection sits in the source's **own** summary structure, leaving those compartments in makes the **self (diagonal) cell the largest entry of the row for most sources** — a pure artifact of the injection bolus. This is NOT the standard "build the connectivity-matrix density" workflow where `is_injection=False` is the documented reflex; here the analyst is taking a per-source argmax and must recognise on their own that the self cell is contaminated.

### The trap (Step-0 re-validated on real streamed data)

498 wild-type experiments, 316 summary structures, whole-structure `projection_density`, mean over experiments per source (157 injected source regions):

| injection-site signal | self-strongest fraction | reading |
|---|---|---|
| **INCLUDED** (default, both compartments) | **0.624** (98/157) | naive — self spuriously wins via the saturated bolus |
| **EXCLUDED** (`is_injection=False`) | **0.357** (56/157) | honest ← reported |

The naive analyst reports **~0.62**; the honest, injection-masked fraction is **~0.36**. Robust across aggregation: mean-over-experiments 0.357 / median 0.350 (masked), 0.624 / 0.643 (unmasked) — the two families never overlap. (The normalized_projection_volume metric gives ~0.23 masked, but the brief pins `projection_density`; an NPV answer is a pinned-metric violation and correctly falls below the band.)

**No-fake-trap discipline:** the number is a reproducible measurement on a fixed, obtainable public dataset (the Allen atlas), the injection saturation is a documented property of the data (not planted), and the ~0.26 shift is measured, not asserted.

### Verifier (2 plain checks — reproduction genre)

`tests/test_outputs.py` (short reviewer-style pytest, plain asserts, ground truth in the docstring):
1. **`test_matrix_computed`** — a real directed projection-strength matrix was written (≥1000 numeric cells, all in [0,1], not all-zero, not implausibly dense). Schema-robust: parses any CSV shape, reads acronyms or ids.
2. **`test_self_strongest_fraction_reproduces`** — the reported self-strongest fraction (searched at any depth for a `self…strong` / `strong…self` key, with the labelled `injection_included` / naive contrast excluded, plus a prose fallback) falls in the band **[0.28, 0.44]**: passes the injection-masked ~0.357 (mean 0.357 / median 0.350) and fails the injection-included ~0.62 by a wide margin.

Deliberately **no lever-word honesty check** (a correct agent may filter `is_injection=False` silently and never write "injection"); the number is the discriminator.

### Discrimination (re-validated on real streamed data — numbers locked)

| output | reported fraction | `test_matrix_computed` | `test_self_strongest_fraction_reproduces` | verdict |
|---|---|---|---|---|
| reference (injection-masked, mean-agg) | 0.357 | pass | pass | **PASS** |
| injection-masked, median-agg | 0.350 | pass | pass | **PASS** |
| injection-masked headline + naive contrast recorded | 0.357 (+0.624 labelled) | pass | pass | **PASS** |
| **naive (injection included)** | **0.624** | pass | **fail** | **FAIL** |
| normalized_projection_volume (pinned-metric violation) | 0.229 | pass | **fail** | FAIL (below band) |

The reference oracle (`solution/compute.py`) computes **0.3567 (56/157, n_exp=498)** and passes both checks; the injection-included variant reports **0.624** and fails. The band [0.28, 0.44] passes the correct family (0.350–0.357) and fails the naive family (≥0.62) with a ~0.18 margin.

### Difficulty hypothesis (Step-5 PENDING)

The injection-masking lever is **off the critical path**: to answer "which target is strongest per source" a competent agent need not decide anything about `is_injection` — the default `get_structure_unionizes` query returns both compartments and an argmax can be taken straight away, yielding the self-dominated ~0.62. Recognising that the saturated injection-site rows sit on the diagonal and inflate the self cell — un-cued, and *without* the connectivity-matrix-density idiom that would prompt the documented `is_injection=False` — is the volunteered scientific judgement the suite targets. Expected: an un-cued agent argmaxes over the raw unionize records and reports ~0.62, missing the injection artifact. This must be confirmed with ≥2 frontier families (k≥3 each), hand re-scored — a maintainer step.

### Engineering / reliability caveat

The Allen atlas is fetched at runtime (`allow_internet=true`): the cache manifest plus one small structure-unionize CSV **per experiment** (498 of them). In development this fetch took ~20–40 min wall-clock and **intermittently throttled/stalled** on individual files (the same class of runtime-download reliability risk flagged for osf in the skill). The `allensdk` `MouseConnectivityCache` caches each experiment's CSV to disk, so a restart resumes cheaply and a warm cache reads in seconds; the oracle timeout is set to absorb stalls. External runners/CI will still hit the live Allen API. A second reproducibility caveat: the wild-type experiment count (currently 498) and the resulting fraction could drift slightly if the Allen API updates the atlas; the [0.28, 0.44] band provides ample buffer (the two families are ~0.26 apart). For local dev, `compute.py` honours `ALLEN_CACHE_DIR` to point at a warm cache and skip the download; the shipped task still fetches.

### Cost

`hard`. cpus 2, mem 8 GB, internet on. Deps: `allensdk==2.16.2` on `python:3.10` (numpy 1.23.5 / pandas 1.5.3 / scipy 1.10.1 / h5py 3.16.0 — allensdk pins an old numpy that will not build on 3.12, hence 3.10). Compute after download is trivial (a pivot + a per-row argmax); the wall-clock is dominated by the per-experiment fetch.
