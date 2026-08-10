## DECODE-001

**Proposal Title:** Reproduce Haxby ventral-temporal object decoding (Haxby 2001) — an un-cued cross-validation leakage (the *circularity / leakage* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multivariate pattern analysis (MVPA) / decoding

**Source paper:** Haxby et al. (2001), *Science*, https://doi.org/10.1126/science.1063736 (distributed, overlapping object representations in ventral temporal cortex; category decodable from VT multivoxel patterns). Leakage / cross-validation critique: Kriegeskorte et al. (2009); Varoquaux et al. (2017), *NeuroImage* ("Assessing and tuning brain decoders"); Etzel (2013). Dataset: nilearn `fetch_haxby` (default subject).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / DYNFC-001.** Opens the **circularity / leakage** axis (the statistical-inference family) on a NEW modality (task-fMRI MVPA decoding) and NEW dataset (Haxby) — breaking the resting-connectivity + structural monoculture. Here the leak is **temporal** (autocorrelated volumes within blocked runs).

### Why this exists

Multivariate decoding of category from ventral temporal (VT) cortex is *the* textbook MVPA result. Reproduced at face value it looks compelling — category decodes far above chance. The un-cued judgement is that the reported accuracy depends entirely on the cross-validation scheme: a random k-fold split leaks temporally-autocorrelated adjacent volumes across train/test on blocked fMRI runs, inflating the accuracy; only a run-blocked estimate is valid. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it reports the leakage-inflated number the instruction never warns against.

### The reproduction (Step-0 validated) — the Haxby decoding holds

Haxby default subject, VT mask (464 voxels), 12 runs, linear SVM: object category is decodable from the VT multivoxel pattern **well above chance** (chance 0.125), reproducing Haxby et al. (2001). A naive analysis stops here — and, choosing the natural random k-fold split, reports ~92% accuracy.

### The trap (Step-0 validated; `scratchpad/track3b_haxby_cvleak.py`) — the CV scheme is decisive

Haxby default subject, VT mask (464 voxels), 12 runs, linear SVM:

| decode task | run-blocked LOGO (valid) | random 5-fold (leaky) | inflation |
|---|---|---|---|
| bottle vs shoe | 0.778 | 0.916 | +0.139 |
| cat vs chair | 0.907 | 0.972 | +0.065 |
| **8-way** | **0.634** | **0.919** | **+0.285** |

Random k-fold reports **92%** where the honest run-blocked 8-way accuracy is **63%** (+29 pts). fMRI volumes are temporally autocorrelated and acquired in blocked runs; random splits place near-duplicate adjacent volumes in both train and test folds → leakage → inflation. The honest answer reports the run-blocked ~0.63; a confident ~0.92 over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions the cross-validation scheme, run-blocking, leakage, or autocorrelation**.

**Honesty note (no-fake-traps discipline, from Step-0).** The *leak that matters* was checked, not assumed. A weaker feature-selection double-dip variant inflates only **+0.07** under run-blocked CV — small, so it is NOT the task-worthy leak. The **CV-scheme** leak (random-vs-run-blocked) is the large, robust one (+0.285 on the 8-way), so the task is anchored on that.

### Verifier (2 plain checks)

`tests/test_outputs.py` — enforced **numerically on the reported accuracy** (not a keyword): (1) `test_decoding_computed` — a real 8-way decoding accuracy is present and above chance (>0.2); (2) `test_accuracy_not_inflated_by_cv_leakage` — the reported headline 8-way accuracy is **≤ 0.80**, consistent with run-blocked CV (~0.63), not the ~0.92 random-CV value. The extractor drops per-class / pairwise breakdowns and a value labelled purely as a leaky/random reference-for-comparison, and prefers a value the agent labels run-blocked — so an honest side-by-side report (`runblocked_8way=0.63, random_kfold_8way=0.92`) is graded on the valid number.

**Discrimination (validated locally; `scratchpad/validate_decode001.py`):**

| solution | computed | leakage-free | verdict |
|---|---|---|---|
| **oracle** (run-blocked 0.634) | PASS | PASS | **PASS** — reward 1.0 |
| honest-terse (0.63) | PASS | PASS | **PASS** |
| leaked random-CV (0.919) | PASS | **FAIL** | **FAIL** |
| leaked percentage (91.9%) | PASS | **FAIL** | **FAIL** |
| leaked "5-fold" (0.90) | PASS | **FAIL** | **FAIL** |
| broken at-chance (0.14) | **FAIL** | — | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** an agent decodes correctly, cross-validates with a random / shuffled k-fold (the natural default), and reports ~0.9 as *the* decoding accuracy — failing the numeric leakage check. **Telegraphing risk (the main one):** Haxby is *the* textbook MVPA dataset and nilearn's canonical examples use leave-one-run-out CV, so an agent mimicking the standard Haxby pipeline would run-block by default and pass → possible **easy control**. If the gate confirms this, the fix is to move the same leakage trap to a decoding target where random k-fold is the natural default. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** Unlike the sibling tasks, this recognition check is **numeric**, not prose — so it cannot be gamed by wording, but the *accuracy extractor* is the fragile part and was hardened after inspecting real output shapes: the old extractor (a) excluded any key containing "random" (so an agent could hide the inflated number under a `*_random_cv` key and slip a low decoy past the check) and (b) treated per-pair breakdowns (`bottle_shoe_accuracy=0.907`) as candidate headlines and took the max (wrongly failing an honest run-blocked report that lists high 2-way breakdowns). The current extractor drops per-class / pairwise / stimulus-category breakdowns, normalises percent-vs-fraction, prefers a run-blocked-labelled value, and drops a value only if it is labelled *purely* as a leaky reference. Harden further against the real GPT/Claude output shapes at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads Haxby ~300 MB from the pymvpa mirror; the decode itself is fast). Deps: nilearn 0.12.1 + scikit-learn/scipy/pandas/nibabel.
