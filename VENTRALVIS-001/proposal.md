## VENTRALVIS-001

**Proposal Title:** Object-category decoding in ventral temporal cortex (Haxby 2001) — un-cued cross-validation leakage (the *circularity / leakage* failure axis), task-fMRI MVPA modality (answer + numbers in private calibration.md)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multivariate pattern analysis (MVPA) / decoding

**Source paper:** Haxby et al. (2001), *Science*, https://doi.org/10.1126/science.1063736 (distributed, overlapping object representations in ventral temporal cortex; category decodable from VT multivoxel patterns). Leakage / cross-validation critique: Kriegeskorte et al. (2009); Varoquaux et al. (2017), *NeuroImage* ("Assessing and tuning brain decoders"); Etzel (2013). The un-cued lever is a **cross-validation-scheme** one: fMRI volumes are temporally autocorrelated and acquired in **blocked runs**, so a random k-fold split leaks near-duplicate within-run volumes across train/test and inflates the accuracy; only a **run-blocked (leave-one-run-out)** estimate is valid — and this is **kept out of the instruction**. Data: `nilearn.datasets.fetch_haxby` (default subject).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill**, rebuilt to the maintainer's validity standard (route-a: voxel data fetched + cached at runtime; oracle reproduces the naive result AND volunteers the hidden check; per-fold structured data emitted and checked; answer/numbers in the git-ignored `calibration.md`). Modelled on GMATROPHY-001 / TOPEDGES-001. Opens the **circularity / leakage** axis (statistical-inference family) on a NEW modality (task-fMRI MVPA decoding) and NEW dataset (Haxby); here the leak is **temporal** (autocorrelated volumes within blocked runs).

### Why this exists

Multivariate decoding of object category from ventral temporal (VT) cortex is *the* textbook MVPA result, and reproduced at face value it looks compelling — category decodes far above chance (1/8 = 0.125). The un-cued judgement is that the reported accuracy depends on the cross-validation scheme: a random / shuffled k-fold split leaks temporally-autocorrelated adjacent volumes from the same run across train/test, inflating the estimate; only a **run-blocked** cross-validation (leave-one-run-out over the Haxby `chunks` run index) is a valid estimate of generalisation. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it reports the leakage-inflated number the instruction never warns against.

### The face-value result and the trap (validated) — held privately

The specific run-blocked vs random-k-fold accuracies, the inflation, the per-class breakdown, and the validated counts (n_samples, n_runs, VT voxels) are in the **private, git-ignored `calibration.md`** (rule 4: public repo + agents have internet). In brief: a single-pipeline decode with the *natural* random k-fold split returns one confident, high 8-way accuracy, but that figure is **inflated by within-run temporal leakage**; blocking the cross-validation by run drops it substantially to the valid estimate. The instruction is un-cued — it names the reproduction and the method (VT mask, 8 categories, linear SVM, cross-validated accuracy) in full, but **never mentions the cross-validation scheme, run-blocking, leakage, or temporal autocorrelation**.

**Honesty note (no-fake-traps discipline, from Step-0).** The *leak that matters* was checked, not assumed. A weaker feature-selection double-dip variant inflates only marginally under run-blocked CV — too small to be task-worthy. The **CV-scheme** leak (random-vs-run-blocked) is the large, robust one (validated numbers in `calibration.md`), so the task is anchored on that.

### Verifier (2 plain checks — validate the actual DATA, not keywords)

`tests/test_outputs.py`:

1. `test_decoding_computed` — validates the actual data: a real above-chance 8-way accuracy is present; the reported class labels are the **real Haxby categories** (fake labels fail); every reported accuracy is a valid fraction in [0,1] and the sample/run counts are sane (implausible values fail); and — where both are reported — the random/leaky reference accuracy is genuinely **higher** than the run-blocked headline (a backwards hidden-check fails).
2. `test_cross_validation_run_blocked` — the reported headline 8-way accuracy must fall in the **valid run-blocked band** rather than the **inflated random-k-fold band** (a numeric floor between the two; exact values in `calibration.md`), AND run-blocking must be **evidenced**: the emitted leave-one-run-out fold structure is genuinely run-blocked (**recomputed from the run ids — no run crosses train/test**; a fabricated leaky-fold structure fails), OR `findings.md` recognises the CV leakage (negation-aware, downgrade-driven), OR the CV scheme is labelled run-blocked. The oracle emits `cv_folds.json` (per-fold held-out run + training runs) as the structured proof; it is **not** listed in the instruction's Required Outputs, so the check does not cue the trap.

**Discrimination (validated locally; `scratchpad/gen_fix.py` + per-test pytest):**

| output | computed | run_blocked | verdict |
|---|---|---|---|
| **oracle** (run-blocked headline + folds + recognition) | PASS | PASS | **PASS** — reward 1.0 |
| honest-terse (run-blocked number, labelled scheme) | PASS | PASS | **PASS** |
| honest side-by-side (run-blocked + volunteered leaky ref) | PASS | PASS | **PASS** |
| empty | FAIL | FAIL | **FAIL** |
| naive random-k-fold headline (no recognition) | PASS | **FAIL** | **FAIL** |
| naive hiding the inflated number under a mislabelled key | PASS | **FAIL** | **FAIL** |
| fabricated fake labels / implausible values / backwards check | **FAIL** | — | **FAIL** |
| fabricated leaky-fold structure (runs cross train/test) | PASS | **FAIL** | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (validated locally on cached Haxby; to be re-run in-container by the maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** an agent decodes correctly, cross-validates with a random / shuffled k-fold (the natural default), and reports the leakage-inflated accuracy as *the* decoding accuracy — failing the numeric leakage check. **Telegraphing risk (the main one):** Haxby is *the* textbook MVPA dataset and nilearn's canonical examples use leave-one-run-out CV, so an agent mimicking the standard Haxby pipeline would run-block by default and pass → possible **easy control**. If the gate confirms this, the fix is to move the same leakage trap to a decoding target where random k-fold is the natural default. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The leakage check is enforced **numerically on the reported headline accuracy** (a floor separating the valid run-blocked band from the inflated random band; exact threshold in `calibration.md`), not on wording, so it cannot be gamed by prose; the *accuracy extractor* is the fragile part and is hardened: it normalises dotted/camel/underscore key paths to tokens, drops per-class / pairwise / **per-fold** / stimulus-category breakdowns, normalises percent-vs-fraction, **prefers a run-blocked-labelled value** (so an honest side-by-side report that lists both the run-blocked and the random-k-fold accuracy is graded on the valid one), and shelves a value only if it is labelled *purely* as a leaky reference. On top of the number, the verifier validates the emitted **fold structure** (recomputes run-blocking from the run ids, not a self-reported flag) and the **hidden-check direction** (the random reference must not be below the run-blocked estimate). Harden further against the real GPT/Claude output shapes at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads Haxby ~300 MB from the pymvpa mirror on first run, cached thereafter; the decode itself is fast — the cached oracle runs in ~7 s). Deps: nilearn 0.12.1 + scikit-learn/scipy/pandas/nibabel.
