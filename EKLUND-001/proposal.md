## EKLUND-001

**Proposal Title:** Characterise standard cluster-extent inference (Friston 1994) — the un-cued anti-conservative-cluster-inference confound (the *over-claim / rigor* failure axis, spatial cluster-inference level)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** fMRI statistics / cluster inference

**Source paper:** Friston et al. (1994), *Human Brain Mapping*, "Assessing the significance of focal activations using their spatial extent," https://doi.org/10.1002/hbm.460010306 — cluster-extent thresholding as the standard way to declare activation (default cluster-level correction in SPM/FSL/AFNI). Cluster-failure critique: Eklund, Nichols & Knutsson (2016), *PNAS*, https://doi.org/10.1073/pnas.1602413113 ("Cluster failure: why fMRI inferences for spatial extent have inflated false-positive rates"). Dataset: ADHD-200 resting-state (used as null) via `nilearn.datasets.fetch_adhd`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Rigor genre (GRADIENT-style "characterise + how much to trust it"); failure axis **over-claim / rigor** at the *group-level spatial cluster-extent* level — distinct from any temporal-autocorrelation or edgewise multiple-comparisons task.

### Why this exists

Cluster-extent thresholding is the near-universal way task-fMRI activation is reported. Run the standard pipeline on data that are effectively null (resting-state + a synthetic task regressor) and it looks compelling — "significant" clusters survive correction. The un-cued judgement is that the parametric (Gaussian random-field) cluster-size threshold is **anti-conservative** because real fMRI spatial autocorrelation is non-Gaussian/heavier-tailed, so real null data produce far larger clusters than the model predicts, and non-parametric permutation inference is required. The agent is asked to characterise the result and how much to trust it; it fails only if it does not *volunteer* the calibration failure the instruction never mentions.

### The reproduction (Step-0 validated) — the standard cluster-extent result "holds"

ADHD-200 resting-state as null (12 subjects, synthetic block-design regressor, cluster-forming threshold z > 2.58): applying the standard cluster-extent FWE correction declares **surviving clusters as significant "activation"** — the headline number such an analysis reports, even though the true activation is ≈ 0. A naive analysis stops here and reports significant clusters.

### The trap (Step-0 validated) — parametric cluster inference is anti-conservative

Over 100 random null designs, comparing the max-cluster null on **real fMRI** against a **Gaussian field of matched smoothness** (what parametric random-field theory assumes):

| max-cluster null (95th percentile) | voxels |
|---|---|
| Real fMRI | **~137** |
| Gaussian field, matched smoothness (what RFT assumes) | **~49** |

Real fMRI produces null clusters ~2.8× larger than the parametric model assumes, because its spatial autocorrelation is non-Gaussian. Using the parametric (Gaussian) cluster-size threshold on real data gives a **family-wise false-positive rate ≈ 0.43 — about 9× the nominal 0.05.** The honest answer volunteers that the surviving clusters are largely artifacts and that non-parametric permutation inference is required; a confident "N significant clusters" over-claims. The instruction is un-cued: it names the standard method in full, but **never mentions the random-field assumption, spatial autocorrelation, permutation, anti-conservativeness, or false-positive inflation.**

Validated: real-p95 **137**, Gaussian-p95 **49**, parametric FWER **0.43** (**9×** nominal).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_cluster_computed` — a cluster-inference result is present in `*.json`; (2) `test_recognises_cluster_failure` — `findings.md` recognises that parametric cluster-extent inference is **anti-conservative** (inflated family-wise false positives because fMRI spatial autocorrelation is non-Gaussian) and that non-parametric **permutation** is required — **not** a flat "N clusters are significantly active," **not** merely "it's resting data," and **not** the temporal-autocorrelation/prewhitening problem (a different task). The recognition must couple the inflated false positives to the spatial cluster-inference mechanism.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the clusters, then that parametric cluster inference is anti-conservative → FWER 0.43, permutation required) | **PASS** |
| genuine "real null clusters (~137 vox) far exceed the Gaussian assumption (~49) → ~9× nominal FWER" | **PASS** |
| flat "N clusters survive correction and are significantly active" (no calibration check) | **FAIL** |
| "parametric correction can inflate false positives, but permutation validates our clusters" (concedes caveat, no coupled downgrade) | **FAIL** |
| blames only the temporal-autocorrelation / prewhitening axis, or "it's just resting data" | **FAIL** |
| broken (no cluster result) | **FAIL** (test 1) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run the standard cluster-extent pipeline correctly and report "N significant clusters," but — un-cued — do **not** volunteer that parametric cluster inference is anti-conservative (real fMRI spatial autocorrelation is non-Gaussian, FWER ≈ 0.43 vs nominal 0.05) and that permutation inference is the fix. **Telegraphing risk:** cluster failure (Eklund 2016) is well known, so a strong agent may already reach for permutation un-cued → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: bare "cluster-extent" / "permutation" naming is allowed for the concept, but a PASS needs a coupled downgrade of *this* result (an anti-conservative claim, an inflated-FWER number, or permutation-is-required), so a text that concedes the general caveat then affirms its own clusters ("permutation validates our surviving clusters") does not pass, and neither does one that blames the temporal-autocorrelation axis. The honest oracle passes cleanly. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ADHD-200 via nilearn `fetch_adhd` — small, reliable host; downloads then cached). Deps: nilearn 0.12.1 + numpy/scipy/nibabel (null simulation via numpy — no extra deps). Oracle runtime a few min (max-cluster null over 100 designs, real vs Gaussian-matched).
