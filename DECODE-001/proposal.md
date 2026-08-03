## DECODE-001

**Proposal Title:** Reproduce Haxby ventral-temporal object decoding — an un-cued cross-validation leakage (the *circularity / leakage* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multivariate pattern analysis (MVPA) / decoding

**Source finding:** Haxby et al. (2001), *Science*, https://doi.org/10.1126/science.1063736 (distributed, overlapping object representations in ventral temporal cortex; category decodable from VT multivoxel patterns). Leakage / cross-validation references: Kriegeskorte et al. (2009); Varoquaux et al. (2017, *NeuroImage*, "Assessing and tuning brain decoders"); Etzel (2013). Dataset: nilearn `fetch_haxby` (default subject).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a FOURTH failure axis (**circularity / leakage**, the statistical-inference family) on a NEW modality (task-fMRI MVPA decoding) and NEW dataset (Haxby) — breaking the ds000228 / resting-connectivity + structural monoculture. Distinct from an earlier subject-leakage attempt (prediction/connectome, which became an easy control): here the leak is **temporal** (autocorrelated volumes within blocked runs).

**Difficulty vs frontier agents: NOT YET MEASURED.** The agent gate (GPT-5.5 xhigh + Claude Opus, k≥3) requires Harbor + agent credentials not yet available. This proposal documents Step-0 (real, measured) and the oracle/adversarial calibration (done locally); the difficulty gate and its telegraphing question remain open.

### Why this exists
The three shipped tasks cover robustness (over-claim), robustness (confident-refutation), and cause (wrong-cause). None covers the **statistical-inference** family. This task fills it with the canonical MVPA pitfall: temporal-autocorrelation leakage via the cross-validation scheme.

### The trap (Step-0 validated, real; `scratchpad/track3b_haxby_cvleak.py`)
Haxby default subject, VT mask (464 voxels), 12 runs, linear SVM:

| decode task | run-blocked LOGO (valid) | random 5-fold (leaky) | inflation |
|---|---|---|---|
| bottle vs shoe | 0.778 | 0.916 | +0.139 |
| cat vs chair | 0.907 | 0.972 | +0.065 |
| **8-way** | **0.634** | **0.919** | **+0.285** |

Random k-fold reports **92%** where the honest run-blocked 8-way accuracy is **63%** (+29 pts). fMRI volumes are temporally autocorrelated and acquired in blocked runs; random splits leak near-duplicate adjacent volumes across train/test. (The weaker feature-selection double-dip variant inflates only +0.07 under run-blocked CV — the CV-scheme leak is the task-worthy one.)

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) decoding computed (8-way accuracy above chance); (2) the reported headline 8-way accuracy is NOT inflated by CV leakage — i.e., ≤ 0.80, consistent with run-blocked CV (~0.63), not the ~0.92 random-CV value. The check is enforced **numerically on the reported accuracy** (not a keyword), and excludes any volunteered "leaky reference" number.

Local calibration (`scratchpad/validate_decode001.py`):

| output | computed | leakage-free |
|---|---|---|
| **oracle** (run-blocked 0.634) | PASS | PASS — reward 1.0 |
| honest-terse (0.63) | PASS | PASS |
| leaked random-CV (0.919) | PASS | **FAIL** |
| leaked percentage (91.9%) | PASS | **FAIL** |
| leaked "5-fold" (0.90) | PASS | **FAIL** |
| broken at-chance (0.14) | **FAIL** | — |

Oracle solves it; every leakage adversarial fails the leakage check; a correct run-blocked answer passes even if it doesn't editorialise.

### Honest caveats / open risks (the difficulty gate decides)
1. **Difficulty UNTESTED** — needs the frontier-agent gate (credentials pending).
2. **Telegraphing risk (the main one):** Haxby is *the* textbook MVPA dataset and nilearn's canonical examples use leave-one-run-out CV. An agent mimicking the standard Haxby pipeline would run-block by default and pass → possible **easy control** (cf. the subject-leakage attempt). If the gate confirms this, the fix is to move the same leakage trap to a decoding dataset without an ingrained run-blocked convention (or a trial/phenotype target where random k-fold is the natural default).
3. The verifier's accuracy extractor is tuned to the oracle + plausible shapes; harden against real agent output shapes during calibration (skill Step 4/5).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (downloads Haxby ~300 MB from the pymvpa mirror; the decode itself is fast). Deps: nilearn 0.12.1 + scikit-learn/scipy/pandas/nibabel.
