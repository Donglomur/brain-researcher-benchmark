## STEINMETZ-001

**Proposal Title:** Reproduce the population choice-decoding accuracy on a Steinmetz Neuropixels session — two un-cued off-critical-path errors (movement-window contamination + CV leakage)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems neuroscience / population decoding

**Source finding:** Steinmetz, Zatka-Haas, Carandini & Harris (2019), *Nature*, https://doi.org/10.1038/s41586-019-1787-x ("Distributed coding of choice, action and engagement across the mouse brain"). **Dataset:** DANDI dandiset **`000017`** (the NWB conversion of the Steinmetz data), real mouse Neuropixels recordings, fetched at runtime. Pinned session: **`sub-Cori/sub-Cori_ses-20161214T120000.nwb`** (~311 MB, one session).

**Status: FULL runnable task** (real-data, runtime single-asset DANDI fetch, `allow_internet=true`). Reproduction genre (numeric match), on animal Neuropixels electrophysiology.

### The measurement and the two un-cued levers

The brief pins the non-lever machinery — session, dataset-`included` left/right trials, all recorded units, a 250 ms per-unit spike-count feature, a standardized linear classifier, 5-fold CV — and asks for the **cross-validated accuracy of decoding the mouse's UPCOMING choice**. It never says "pre-movement", "motor", "leakage", "blocked", or "contamination".

Two off-critical-path choices both inflate the estimate, and a careless agent takes both:

1. **Movement-window contamination.** A window placed AROUND the response (peri-movement) reads out motor-execution activity, so the classifier decodes the movement already underway, not the *upcoming* choice. The honest window is strictly **pre-movement**, aligned to visual-stimulus onset and ending before the wheel turn.
2. **Cross-validation leakage.** Trials are temporally structured (session drift, stimulus blocks), so **random** k-fold puts correlated neighbouring trials in train and test at once, optimistically biasing accuracy. **Blocked** (contiguous) folds respect trial order.

### The trap (Step-0 validated, real data)

Pinned config (dataset-`included` L/R trials = 134, all 1085 units, 250 ms window, standardized logistic regression, 5-fold; chance = majority = 0.515):

| window | CV | accuracy | reading |
|---|---|---|---|
| **peri-movement** (resp ±0.1 s) | **random** | **0.95** | naive — motor execution + leakage |
| peri-movement (resp ±0.1 s) | blocked | 0.94 | motor signal so strong CV barely matters |
| pre-movement (stim..+0.25 s) | random | 0.76 | right window, leaky CV |
| **pre-movement** (stim..+0.25 s) | **blocked** | **0.72** | honest upcoming-choice decoder ← reported |

The dominant lever is the **movement window**: a peri-movement window reports ~0.95, a strictly pre-movement window ~0.72–0.76 — a ~0.23 gap. CV leakage adds on top within the pre-movement window (0.76 → 0.72). The honest answer (pre-movement + blocked) is **0.72**, well above chance but far below the ~0.95 a contaminated pipeline reports.

**Robustness (Step-0):** the correct value is stable across regularization (C ∈ 0.1–5 → 0.72 ± 0.01) and the naive value is stable across C and CV seed (0.95–0.97). The graded tolerance (±0.06 around 0.72 → [0.66, 0.78]) cleanly fails both peri-movement combos (0.94/0.95) with a ~0.16 margin while accepting any correct pre-movement estimate; the lower bound also fails a broken/at-chance pipeline (0.51).

### The failure mode (un-cued, reproduction)

The agent, told to decode "choice", grabs the window around the response (where the choice is defined) and sklearn's default random k-fold, and reports ~0.95 — decoding the movement already in progress, with CV leakage. Only a strictly pre-movement window scored with non-leaky (blocked) CV reproduces the honest ~0.72. A reported ~0.95 fails the numeric match.

### Verifier (3 plain checks, reproduction genre)

`tests/test_outputs.py`: (1) a real decoding run — plausible n_trials (~134), n_units (≥200), and a stated chance level ~0.51; (2) **numeric reproduction** — the headline `cross_validated_accuracy` (a value the submission labelled peri/motor/random is never taken as the headline) matches **0.72 ± 0.06**, which fails the naive ~0.95; (3) light honesty check — findings.md states the chance/baseline and the headline is the honest value. Accepts accuracy given as a fraction or a percentage. Offline discrimination (locked): reference oracle **3/3 PASS**; naive peri-movement + random-CV baseline (reports 0.955) **FAILS 2/3**.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; naive baseline **reward 0** (validated locally with the pinned DANDI asset; runtime content-URL streaming fetch verified — HDF5 signature over an S3 range request). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is a maintainer step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 12 GB, internet on (fetches one ~311 MB NWB asset at runtime — the single pinned session's S3 blob, not the whole dandiset; note DANDI/S3 can throttle). Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.1 / numpy / scipy / pandas / h5py / scikit-learn (pinned in the Dockerfile).

### Proof-of-work verifier (added)

The grader is now proof-of-work (see `PROOF_OF_WORK_SPEC.md`): a submission cannot pass without
running the real decoding on the real session.

- **Held-out reference** `tests/reference.npz` (built from `solution/compute.py`, never shipped to
  the agent): the honest per-fold blocked-CV accuracies `[0.704, 0.741, 0.778, 0.667, 0.731]`
  (mean 0.724) + `ref_stats` (naive peri+random 0.955, pre+random 0.762, peri+blocked 0.941,
  chance 0.515, n_trials 134, n_units 1085).
- **Neutral per-item table** `folds.csv` (per-fold CV accuracies) — produced by any 5-fold CV,
  naive or honest, so requiring it does not cue the window / CV-scheme levers.
- **Pillars:** (1) `folds.csv` well-formed + non-constant + its sorted per-fold values track the
  held-out reference; (2) `mean(folds) == reported cross_validated_accuracy == honest reference`
  and lands in the held-out band `[0.64, 0.80]` that only a strictly pre-movement, non-leaky
  decoder reaches (the naive peri+random ~0.95 fails by a wide margin); (3) a volunteered
  peri-movement / random-CV accuracy, if present, must be the inflated ~0.95.
- **Validation matrix (subprocess pytest):** honest PASS; no-table FAIL; constant-table FAIL;
  non-constant-fabricated (wrong per-fold spread) FAIL; naive peri+random over-claim FAIL.

**Data pin (reference build):** DANDI `000017` (draft), asset
`sub-Cori/sub-Cori_ses-20161214T120000.nwb`, asset-id `92694e6e-84fd-4198-a7e3-64e764f8e086`,
size 311814662 B, `dandi:sha2-256 = d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236`.
The dandiset uses the mutable **draft** version; the asset path + this content hash pin the exact
blob the reference was built from. Data is fetched at runtime (`allow_internet=true`); baking is a
maintainer follow-up (>100 MB/file GitHub limit).

## Second-pass fix (2026-09): stop the failure-message leak, add a spread check, tighten tol

The red-team found three issues with the proof-of-work grader: (1) the per-fold match tolerance was
loose (0.06 over 5 folds, 80% match), (2) the honest headline ~0.72 is guessable/published, and
(3) **the failure message LEAKED the reference folds** — it printed
`sorted reference folds = [...]` (and the inflated ~0.95 reference value), handing the answer to
any agent that could see the verifier output.

Fixes (single-value reproduction task; the un-cued judgement is the window (pre- vs peri-movement)
and CV scheme (blocked vs random), and the instruction pins 5-fold, so the fold count was kept):
- **Stop the leak.** No held-out reference value — the reference fold accuracies, the honest mean,
  or the inflated ~0.95 — is printed in ANY assertion message any more. Verified: the per-fold-match
  failure now reads "…match the held-out reference cross-validation within tolerance…" with no
  numbers; the band-failure and naive-value messages print no reference value. (Considered adding
  folds to 10-fold for a stronger fingerprint and rebuilt/measured it, but the instruction pins
  5-fold and 10-fold on 134 trials gives noisy per-fold values (SD ~0.10) that make per-fold
  matching fragile to defensible window/C variation — so tol-tightening + a spread check was the
  cleaner choice.)
- **Tightened tol + added a per-fold spread-realism check.** `PER_FOLD_TOL` 0.06 → 0.05; a new
  `FOLD_STD` band [0.015, 0.10] rejects a table **clustered at the guessable headline** (SD ~0) —
  the laziest fabrication — while admitting a real 5-fold CV (reference SD ~0.037). The headline is
  still recomputed as the mean of the submitted folds and must land in the honest band and match
  the held-out reference mean.

**HONEST-LIMITATION (flagged).** This is a single-value reproduction task and the headline (~0.72)
is guessable/published. The per-fold table raises the floor — a bare guessed scalar, a real naive
(~0.95) fold table, a clustered fake, and a headline/fold-mean mismatch all FAIL — but a
sufficiently knowledgeable agent who **fabricates a realistically-spread per-fold table around
0.72** still passes (validated: `RESIDUAL_realistic_fake` PASSES). Fully blocking that would need a
finer per-trial fingerprint; it relies on the frontier gate.

**Adversarial self-validation (subprocess pytest per case; honest = the exact 5-fold reference):**

| case | result | teeth |
|---|---|---|
| honest oracle (reference folds + mean headline) | **PASS** | — |
| defensible (folds perturbed ±0.02, headline = their mean) | **PASS** | — |
| attack C — **real naive folds (~0.95)** + guessed 0.72 headline | **FAIL** | fold mean out of band; headline ≠ mean |
| attack — naive run reported truthfully (headline 0.95) | **FAIL** | fold mean out of band |
| attack A — **clustered** fold table at 0.72 (SD ~0) | **FAIL** | fold SD below the realism floor |
| attack — per-fold table not matching the reference distribution | **FAIL** | < 80% of folds match (no leak in message) |
| (residual) realistically-spread **fabricated** 0.72 table | PASS | HONEST-LIMITATION — relies on the frontier gate |

The brief's attack C (real naive per-item table + guessed number) now FAILS, and the failure-message
leak is closed, while honest + defensible PASS.
