## NETINTEG-001

**Proposal Title:** Rank participants by functional-network integration (global efficiency) — an un-cued graph-thresholding judgement (reporting-quality / over-claim axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** fMRI functional connectomics / graph theory

**Source finding:** Global efficiency as a measure of network integration (Latora & Marchiori 2001, *PRL*; Rubinov & Sporns 2010, *NeuroImage*; Bullmore & Sporns 2009). The thresholding-convention confound: van Wijk et al. 2010, *PLoS ONE*; van den Heuvel et al. 2017, *NeuroImage* (proportional vs absolute thresholding). Dataset: nilearn's ADHD-200 resting-state subset (`fetch_adhd`, 40 participants) parcellated with **Schaefer-2018 100/17**; fetched at runtime, no credentials.

**Status: FULL runnable task.** Genre: **over-claim / reporting-quality** (mirrors GRADIENT-001), with an un-cued graph-thresholding judgement.

### Distinctness from the shipped connectivity suite

- **NETSTRENGTH-001** ranks edges (full vs partial correlation) on **HCP MegaTrawls**; different dataset, different lever (marginal vs conditional edges).
- **CORTHUBS-001 / HUBMAP-001** identify **node hubs** by weighted degree on **ABIDE** (Dosenbach-160); their levers are positive-edge handling and per-subject vs group aggregation. NETINTEG uses a **different metric** (**global efficiency**, unused in the suite), a **different dataset** (ADHD-200 via `fetch_adhd`, unused), and a **different lever** (**absolute vs density-matched thresholding/binarization**). Crucially, on these data the node-hub *identity* is robust to thresholding (I checked — the top hub is stable), so this is NOT a hub task; the thresholding lever bites on the **cross-participant** efficiency ranking, not on node ranking.
- **MODULAR-001 / NETMODULES-001** use the modularity **resolution** lever; **GROUPAGEFC-001** the ecological fallacy. Different levers.
- **GRADIENT-001** is over-claim on **development_fmri** (principal gradient identity). Same *genre*, different dataset, metric, and lever.

### Step-0 (validated, real — reproduces on obtainable data)

Built the 40 Schaefer-100 correlation connectomes and computed per-participant **global efficiency** (scipy `csgraph` shortest paths; verified identical to networkx to 1e-14) under two standard thresholding conventions. Global efficiency is a binary-graph measure, so the correlation matrix must be sparsified/binarized first:

| convention | corr(efficiency, overall connectivity strength) |
|---|---|
| fixed **absolute** cutoff (r ≥ 0.3) | **+0.86** |
| **density-matched** (proportional, integrated over densities) | **−0.57** |

- **The confound is the whole story and it is robust.** Under an absolute cutoff, a participant's graph density — hence global efficiency — is set by their **overall connectivity strength**, so "most integrated" collapses into "most strongly correlated" (r ≈ +0.86). Matching graph density across participants removes it (r ≈ −0.57). This reproduced on a second cohort too (development_fmri: +0.96 vs −0.47).
- **The two conventions give nearly disjoint rankings:** Spearman between the density-matched and absolute-cutoff participant orderings ≈ **−0.28 to −0.38**; the **top-8 most-integrated sets overlap 0–1/8**. Each convention is internally stable (within-convention Spearman ≈ 0.8–0.85 across its own parameter), so this is a genuine convention split, not noise.

### The un-cued lever (Step-0 measured — large and robust)

The instruction names the metric (global efficiency), the data, the atlas, and the deliverable ("which participants are the most integrated"), and lists graph construction / thresholding generically among the unspecified "standard choices" — but **never** says the answer depends on the absolute-vs-density-matched thresholding convention, nor that an absolute threshold confounds efficiency with overall connectivity. A naive analyst picks one absolute cutoff, ranks, and confidently names the "most integrated" participants — an ordering that is really the overall-connectivity ordering. The warranted conclusion is that the ranking is **convention/density dependent** and density must be matched to compare integration fairly.

### Verifier (4 plain checks, human-looking pytest) — hardened to a NUMERIC top-k contrast

The pre-hardening check 4 was a prose over-claim check (does `findings.md` call the ranking
convention/density dependent). As the proposal below anticipated, that is **hedge-passable**: an
agent can write "the ranking may depend on the thresholding convention / graph density" while
still reporting the naive absolute-threshold ordering as the answer. The **ratchet named in the
original difficulty note has now been applied**: check 4 is a **numeric top-k contrast** — it
grades the *reported* most-integrated set against two release ground-truth top-8 sets computed
on the pinned data (density-matched vs absolute), and passes only if the reported ranking is
**closer to the density-matched set than to the absolute one**. Reproducing the density-matched
ranking *requires actually density-matching*; prose cannot substitute.

`tests/test_outputs.py`: (1) per-participant global efficiency actually computed (≥10 participants, values in (0,1), non-constant); (2) a participant ranking / most-integrated set reported; (3) **engaged with the thresholding convention** — a ≥2-config report, prose naming both conventions / a density sweep, **or** an explicit density-matched/proportional (top-X%/edge-density) method (a submission that simply does the right thing is not failed here); (4) **numeric top-k contrast (the teeth)** — the reported most-integrated set overlaps the density-matched ground-truth top-8 by ≥2 **and** by strictly more than the absolute-threshold top-8 (a preprocessing-robust fallback, Route B, also passes a submission that numerically reports the efficiency↔strength confound with the correct sign under both conventions).

The two ground-truth top-8 sets are **essentially disjoint** (overlap 0/8; density-matched Spearman −0.28 vs absolute). The contrast — not exact identity — is graded, so it is robust: in the Step-0 probe **every** density-matched variant (5 densities × 2 preprocessings, incl. no-confound regression) landed with DM-overlap ≥2 and > ABS-overlap, while every absolute cutoff and the pure strength ranking did the reverse.

**Offline discrimination (measured on the real cached ADHD-200 connectomes, this build):**

| output | check1 | check2 | check3 | check4 (numeric top-k) | verdict |
|---|---|---|---|---|---|
| reference solution (density-matched headline, confound reported) | PASS | PASS | PASS | PASS (dm 8/8, ab 0/8) | **PASS** |
| naive single absolute-threshold confident ranking | PASS | PASS | **FAIL** | **FAIL** (dm 0/8, ab 8/8) | **FAIL** |
| **hedge** — absolute ranking as headline + prose "ranking may depend on threshold/density" | PASS | PASS | PASS | **FAIL** (dm 0/8, ab 8/8) | **FAIL** |
| defensible alternative — single-density (10%) proportional/density-matched ranking | PASS | PASS | PASS | PASS (dm 7/8, ab 1/8) | **PASS** |

The **hedge row is the point of the hardening**: prose caveats no longer pass; the reported ranking must actually be the density-matched one.

### Difficulty — Step-5 frontier calibration PENDING (maintainer gate)

Oracle passes (**reward 1.0**, re-verified this build by running the reference `compute.py` on the cached ADHD-200/Schaefer data: n=40, rank-corr prop-vs-abs −0.28, eff↔strength corr +0.86 absolute / −0.57 density-matched — matching Step-0). Naive and hedge fail as tabulated. The **≥2-frontier-family, k≥3 gate** — does GPT-5.x / Claude, un-cued, density-match and report the fair ranking, or threshold absolutely once and report a confident (strength-confounded) ordering? — is the maintainer's Step-5 step and **cannot be run here** (no Harbor/agent access this session). Note the numeric grade also means a maintainer must regenerate the two ground-truth top-8 sets if the pinned nilearn `fetch_adhd` subject list or atlas ever changes.

### Data provenance / reliability caveats

- `fetch_adhd` (ADHD-200 preprocessed subset) and `fetch_atlas_schaefer_2018` download at runtime from the nilearn-pinned sources (no credentials). Participants keyed by the numeric id in each functional filename.
- Global efficiency computed on the binary graph via `scipy.sparse.csgraph.shortest_path` (validated against networkx); no extra dependency beyond the nilearn stack.
- The confound direction and magnitude reproduced on an independent cohort (development_fmri), so it is not an ADHD-200 artifact.

### Cost

`hard` bracket. Fetches ~40 preprocessed rs-fMRI runs + the Schaefer atlas, extracts 100-region time series, builds connectomes, computes efficiency under several thresholds — a few minutes. cpus 2, mem 8 GB, internet on, timeouts 1800–3600 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3 / nibabel 5.3.2 / nilearn 0.12.1.
