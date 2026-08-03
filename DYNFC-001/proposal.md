## DYNFC-001

**Proposal Title:** Characterising dynamic functional connectivity (ABIDE) — an un-cued stationarity artifact (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Dynamic functional connectivity

**Source finding:** Hutchison et al. (2013), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2013.05.079 (dynamic FC); Allen et al. (2014). Stationarity-null critique: Laumann et al. (2017), Hindriks et al. (2016), Zalesky & Breakspear (2014). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Topic *dynamic functional connectivity*, ABIDE.

**Axis honesty:** this is the **over-claim** axis (confidently asserting a phenomenon — "dynamic states" — that does not survive a null), the same broad axis as GRADIENT-001. It is well-**differentiated**, though: a *temporal* over-claim (dynamics ≠ artifact) on a *different topic* (dynamic FC), *dataset* (ABIDE), and *method* (stationary-surrogate null) than GRADIENT's *spatial* gradient-identity over-claim on ds000228. Adds an axis×dataset×modality cell, not a duplicate. (A near-duplicate graph-hub over-claim candidate was **dropped** this session for overlapping GRADIENT + HUBMAP.)

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/tierA_dfc.py`)
ABIDE dosenbach160, n~60, 40 ROIs, 30-TR windows:

| measure | value |
|---|---|
| observed sliding-window edge-std | ~0.18 |
| stationary-null edge-std (Gaussian, same static covariance) | ~0.16 |
| ratio observed / null | **~1.14** (only ~12% excess) |

The observed "dynamics" barely exceed what a **stationary** process produces by sampling variability — so the fluctuations are largely artifact, not robust time-varying connectivity.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) a time-resolved / sliding-window connectivity measure was computed; (2) `findings.md` recognises the observed dynamics barely exceed / are largely explained by a **stationary null** (sampling artifact) — a confident "dynamic connectivity states are present" over-claims. Linked-insight + a `strong`-token guard (stationary / surrogate / sampling-noise / artifact) so a bare "noisy" mention does not pass.

Local calibration (`scratchpad/validate_dynfc.py`):

| output | dynamics_computed | recognises_stationarity |
|---|---|---|
| **oracle** | PASS | PASS — reward 1.0 |
| correct-terse (barely exceeds stationary null) | PASS | PASS |
| flat "5 dynamic states" | PASS | **FAIL** |
| vague "noisy and variable" | PASS | **FAIL** (no false positive) |
| broken (no dynamics measure) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. Telegraphing: comparing DFC to a stationary null is a known-but-often-skipped step; the gate decides whether agents volunteer it un-cued.
2. **Prose/judgement verifier** (rigor genre) — grades a written insight; linked-insight + strong-token guards mitigate false positives.
3. Modest effect (~12% excess): the honest conclusion is "largely, not entirely, artifact" — the oracle states it as such.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE dosenbach160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
