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
