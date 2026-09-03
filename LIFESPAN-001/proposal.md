## LIFESPAN-001

**Proposal Title:** Resting connectome organization across the adult lifespan — an un-cued
"global average hides the reorganization" trap (hard reproduction / over-claim)

**Scientific Domain:** Life Sciences / Neuroscience / resting-state fMRI (lifespan functional
connectomics, network segregation / de-differentiation)

**Source finding (method):** Chan, Park, Savalia, Petersen & Wig (2014), *Decreased segregation of
brain systems across the healthy adult lifespan*, PNAS, https://doi.org/10.1073/pnas.1415122111.
**Dataset:** NKI Enhanced resting-state fMRI (TR = 645 ms), preprocessed and projected to the
`fsaverage5` surface (Nooner et al. 2012, *Front. Neurosci.*), fetched with
`nilearn.datasets.fetch_surf_nki_enhanced` (first 60 subjects, ages 18-78) and parcellated into the
148-region Destrieux atlas at image-build time (see the un-cued-fetch note below).

**Status: FULL runnable task, oracle + naive validated locally (Step-0 + oracle re-run + naive/alt
discrimination). Step-5 frontier calibration PENDING (maintainer step).**

### Genre
Reproduction / over-claim (mirrors GRADIENT-001). The graded quantity is the **relationship between
the connectome's organization and age**. A convention-invariant summary — the SIGN and rough
magnitude of the age relationship of a network-organization metric — is what is checked; the exact
value is robust to the network partition (see Step-0).

### The un-cued lever (PRIVATE — never named in instruction.md)
How the connectome's "organization" is summarised before relating it to age. The naive summary —
**overall / mean functional connectivity** (the average of all connectome edges) — is essentially
FLAT across the adult lifespan on these data, so a naive analyst concludes "resting connectivity is
stable with age." That is an over-claim: the organization does change. Summarised as the
**segregation of the large-scale networks** (mean within-network minus between-network connectivity,
normalised; Chan et al. 2014), the connectome **de-differentiates** — segregation DECLINES with age
— driven by between-network connectivity rising while within-network stays flat, so the two cancel
in the global average. The instruction never says "segregation", "de-differentiation", "within/
between", "modularity", or "network integration"; it only asks to "characterise how the large-scale
organization of the connectome changes across the adult lifespan." The task id is a neutral topic id.

### Step-0 result (measured; packaged bundle, n = 59-60, ages 18-78, Destrieux-148 connectomes)
| connectome summary vs age | Pearson r | p | Spearman |
|---|---|---|---|
| overall / mean FC (NAIVE) | **+0.15** | 0.26 | +0.23 |
| within-network FC (pos edges) | +0.03 | 0.83 | +0.12 |
| between-network FC (pos edges) | +0.12 | 0.36 | +0.25 |
| **system segregation (CORRECT)** | **-0.28** | **0.031** | **-0.36** |

The naive global-average summary shows no age effect; the network-segregation summary declines
robustly. **Robustness:** segregation-age r stays in **[-0.40, -0.24]** across 5-12-network
data-driven partitions and 4 KMeans seeds; **>99% of bootstrap resamples are negative** (95% CI
[-0.52, -0.05]); the sign/decline is invariant to the partition, the positive-vs-signed-edge
definition, and Pearson-vs-Spearman. The direction (a DECLINE / de-differentiation) is the
convention-invariant, reproducible quantity; the naive "no change" read fails it.

### Verifier (3 plain checks, GRADIENT-001 style)
`tests/test_outputs.py`: (1) a per-subject connectome analysis over a real lifespan slice
(>=40 subjects) with at least one summary-vs-age correlation; (2) **insight linked to the result** —
a NETWORK-LEVEL organization summary DECLINES with age: an organization-named negative age
correlation (<= -0.12), OR a within-vs-between divergence (between rises relative to within by
>= 0.08), OR a clearly-labelled negative segregation correlation in the prose; the global/mean
summary is excluded; (3) honesty / no over-claim — `findings.md` reports the organization
declines / de-differentiates with age, not "connectivity is unchanged across the lifespan." No
weighted rubric, no score.json.

### Discrimination (validated locally)
| solution | segregation-vs-age reported | verdict |
|---|---|---|
| reference / oracle (KMeans-7 segregation) | r = -0.28 | **PASS 3/3** |
| alt-correct (within/between divergence, no "segregation" keyword) | between +0.14 vs within +0.03 | **PASS 3/3** |
| naive (global mean FC only, concludes "stable") | none (+0.15 global) | **FAIL 1/3** |
| wrong (claims segregation INCREASES) | r = +0.30 | **FAIL 1/3** |

### Cost
`hard`. cpus 2, mem 8 GB, runtime **offline** (`allow_internet=false`). The bundle (compact
`nki_surface_roi_timeseries.npz`, ~29 MB: (60, 895, 148) region time series + age/sex) is built into
the image at **build time** from the real NKI surface data via nilearn — nothing derived is committed
to the repo (mirrors GROUPAGEFC-001). Runtime is ~1 min (60 connectomes + one KMeans partition).
Deps: numpy/scipy/scikit-learn/pandas/nibabel/nilearn (pinned).

### Notes / caveats
- **Un-cued fetch / build cost:** the raw NKI surface data is ~5 GB from the NKI/NITRC mirror, which
  is slow and intermittently times out. A runtime fetch would not fit the agent timeout, so — as with
  GROUPAGEFC-001 / TASKGLM-001 — the data is fetched and parcellated **once at image-build time**
  (retry loop; `build_timeout_sec = 7200`) and the agent runs offline against the compact bundle.
  The data is 100% real NKI (the derivative is region-mean time series over the standard Destrieux
  atlas); the analytic judgement (how to summarise organization) is fully in the agent's hands.
- The effect is modest but robustly significant and robust to the partition; it reproduces the Chan
  et al. (2014) lifespan de-differentiation finding on a new dataset/modality (NKI surface). The
  naive "connectivity is stable with age" read is a real, documented pitfall (the global average
  cancels the within/between dissociation) — the same reason system segregation was introduced.
- Step-5 frontier calibration (>=2 frontier families, k>=3, hand re-scored) is the maintainer gate
  and is PENDING; this proposal ships the oracle-pass + naive-fail evidence.
