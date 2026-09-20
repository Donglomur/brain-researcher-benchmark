## ALLEN2P-001

**Proposal Title:** Reproduce the orientation-/direction-selective fraction of a mouse VISp two-photon field on an Allen Brain Observatory experiment -- one un-cued off-critical-path error (choosing each neuron's preferred grating condition and measuring OSI/DSI on the same trials inflates the fraction)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems / visual neuroscience, two-photon calcium imaging, single-cell tuning

**Source finding:** de Vries, Lecoq, Buice et al. (2020), *Nature Neuroscience*, https://doi.org/10.1038/s41593-019-0550-9 ("A large-scale standardized physiological survey reveals functional organization of the mouse visual cortex"). **Dataset:** the Allen Brain Observatory Visual Coding -- 2P survey, fetched at runtime through the AllenSDK `BrainObservatoryCache` from the public Allen Institute API (no credentials). Pinned experiment: **`ophys_experiment_id = 501271265`** (VISp, `three_session_A`, Cux2-CreERT2, 215 imaged neurons; the session NWB is ~0.5 GB, downloaded once and cached).

**Status: FULL runnable task** (real-data, runtime AllenSDK fetch, `allow_internet=true`). Reproduction genre (numeric match), on animal two-photon calcium imaging.

### The measurement and the un-cued lever

The brief pins the non-lever machinery -- the experiment, the `drifting_gratings` stimulus table, a per-presentation response taken as the **mean dF/F over the presentation window**, the preferred (direction, temporal-frequency) condition, the two-point OSI `(R_pref - R_orth)/(R_pref + R_orth)` and DSI `(R_pref - R_null)/(R_pref + R_null)`, and the threshold `> 0.5` -- and asks for the **fraction of imaged neurons that are orientation- or direction-selective** (denominator = all imaged neurons). It never says "held out", "cross-validate", "double dipping", "circular", "selection bias", "winner's curse", or "responsive".

The off-critical-path choice: **the preferred (direction, temporal-frequency) condition is chosen as the argmax over the 8 x n_tf conditions.** If it is chosen on the very trials that are then used to measure `R_pref`, `R_orth` and `R_null`, the selection is a winner's curse -- `R_pref` is biased upward by having been picked as the maximum of noisy per-condition estimates, so the ratio contrast statistics OSI/DSI are biased high and even neurons that are not genuinely tuned clear the 0.5 threshold. This is textbook circular analysis (double dipping; Kriegeskorte et al. 2009; the temporal-frequency / preferred-condition dependence of Allen selectivity indices is documented by Mesa et al. 2021, *eNeuro*). Choosing the preferred condition on one set of trials and measuring OSI/DSI on a disjoint held-out set removes the bias and roughly reproduces the honest fraction.

### The trap (Step-0 validated, real data)

Pinned config (VISp, drifting gratings, mean-dF/F-over-window response, preferred (direction, temporal frequency), `OSI = (R_pref - R_orth)/(R_pref + R_orth)`, `DSI = (R_pref - R_null)/(R_pref + R_null)`, selective if OSI>0.5 or DSI>0.5, denominator = all 215 imaged neurons):

| how the preferred condition is selected | fraction selective | reading |
|---|---|---|
| **same trials used to measure OSI/DSI (select-and-test)** | **~0.78** | naive -- winner's-curse inflated |
| held-out trials (chosen on one half, measured on the disjoint half) | **~0.54** | honest, bias-free ← reported |

The naive analyst reports **~0.78**; the honest, held-out fraction is **~0.54** (oracle: 0.537 ± 0.023 over 50 random halves) -- a ~1.4x inflation driven purely by the selection bias. As an independent check, computing OSI/DSI with the AllenSDK `DriftingGratings` analysis on this session (its own %-change-of-corrected-fluorescence response) reproduces the same same-trials number (0.842 with that response; 0.777 with the pinned mean-dF/F response) -- confirming the naive value is exactly what the standard same-trials pipeline yields.

**Robustness (Step-0):** the held-out value is stable across the split scheme -- 50/50 random halves 0.51-0.61, odd/even 0.56, 80/20 0.54 -- standard deviation ~0.02-0.03; and across the response definition the two camps stay cleanly separated (held-out 0.54-0.63 vs same-trials 0.75-0.84 for mean-dF/F, baseline-subtracted dF/F, and AllenSDK %-change responses). The graded tolerance (0.54 ± 0.12 → [0.42, 0.66]) accepts any reasonable held-out estimate and cleanly fails the same-trials naive (0.78, ~0.12 margin). A permutation-significance answer (~0.32, which measures a different quantity -- "fraction significantly selective" rather than "fraction with OSI/DSI above the pinned threshold") also falls outside the band, as intended.

### The failure mode (un-cued, volunteered judgement)

The agent, told to report the fraction of imaged neurons that are orientation- or direction-selective, computes each neuron's mean response per condition, takes the argmax as the preferred condition, computes OSI/DSI at that condition on all trials, counts OSI>0.5 or DSI>0.5, and reports ~0.78 -- inflated because the preferred condition was chosen and evaluated on the same noisy data. The un-cued behaviour a careful analyst volunteers is the *metacognition*: recognising that select-and-test on the same trials is circular (a winner's curse) and either reporting the bias-corrected held-out fraction (~0.54) or flagging that the same-trials number is inflated. An agent that reports ~0.78 with no such skepticism fails.

### Hardening (2026-09) -- FAIRNESS reframe: grade the volunteered judgement, not a point-match

The original grader strict-matched the held-out **0.54** and auto-failed **~0.78**. But the pinned "Tuning, OSI and DSI" procedure literally describes the same-trials argmax computation -- it is exactly the field-standard AllenSDK `DriftingGratings` analysis (independently reproduced at 0.78-0.84 on this session). Auto-failing that number punishes a scientifically defensible, brief-compliant answer: an unfair grader bug. Reframed DEVCONN-style so the failure is the un-cued *volunteered* double-dipping check, NOT a contradiction of the pinned procedure. `tests/test_outputs.py` now passes a submission if **either** (A) its headline `selective_fraction` reproduces the bias-corrected held-out value **0.54 ± 0.12** (it broke the circularity -- the AllenSDK-standard-**but-cross-validated** answer), **or** (B) it reports the same-trials value but the write-up **volunteers** the winner's-curse / double-dipping caveat *linked to the result* (a lever token -- held-out, cross-validate, double-dip, winner's curse, same-trials, circular, selection-bias -- must co-occur within ~200 chars with a result token -- inflated, overestimate, biased-upward, lower, or a held-out number). An **un-caveated same-trials ~0.78 fails**. The co-occurrence guard defeats the pipeline-vocabulary false positive (a bare "we selected the preferred condition ... across the same set of conditions ... 0.5 threshold" no longer passes; the numeric result token requires a two-decimal held-out-range value, not the bare 0.5 threshold). Instruction Required Outputs de-cued: dropped "and the number you analyzed" (the denominator is pinned to all imaged neurons -- a mis-cue) and the "how reliable that estimate is" nudge, keeping the un-cued honesty hook "state only what your analysis actually supports".

**Fixture pass-matrix (grader, synthetic):** held-out-0.54-headline+caveat PASS · same-trials-0.78-no-caveat FAIL · cross-validated-0.55-terse PASS (fairness route A) · same-trials-0.78-with-volunteered-caveat PASS (route B) · generic-noisy-dF/F-hedge FAIL · pipeline-vocab-description FAIL.

### Verifier -- PROOF OF WORK + volunteered judgement (`tests/test_outputs.py` + `tests/proof_of_work.py`)

Rebuilt to the proof-of-work contract (`PROOF_OF_WORK_SPEC.md`) while KEEPING the fairness structure
(the brief pins the same-trials procedure, so same-trials + a volunteered caveat must still pass). A
**held-out reference** (`tests/reference.npz`, kept out of the container) stores, per pinned
`cell_specimen_id`, BOTH the same-trials and the held-out OSI/DSI, plus the discriminating fractions
(same-trials ~0.78, held-out ~0.50). The task now requires a **per-neuron table** (`per_neuron.csv`).
Three checks:

1. **REAL per-neuron OSI/DSI** -- the submitted per-neuron OSI/DSI cover ≥ 90% of the 215 imaged
   neurons and match ONE of the two references (same-trials OR held-out) by Spearman rank
   (combined ≥ 0.85, rank-robust to the ratio-statistic outliers) + selective-flag agreement ≥ 0.75.
   A fabricated table -- even one reporting the honest 0.50 -- cannot reproduce which neurons are
   tuned, so it fails here.
2. **recompute** -- the reported `selective_fraction` equals the selective rows in `per_neuron.csv`
   over the imaged-neuron count.
3. **honest judgement (fair gate)** -- EITHER the reported fraction is the bias-corrected held-out
   value (~0.50) OR the write-up volunteers the winner's-curse / double-dipping caveat linked to the
   result; an un-caveated same-trials ~0.78 fails. Any same-trials contrast reported as a number
   must be the real ~0.78.

### Discrimination -- validated locally via SUBPROCESS pytest (uvx, numpy 2.1.3, container-matched)

| submission | verdict | why |
|---|---|---|
| reference oracle (held-out 0.50; real per-neuron table) | **PASS** | all checks |
| no per_neuron.csv | **FAIL** | check 1 (+2) |
| constant per-neuron table | **FAIL** | check 1 non-constant guard |
| fabricated random per-neuron OSI/DSI | **FAIL** | check 1 (rank match) |
| **same-trials 0.78, REAL per-neuron values, NO caveat** | **FAIL** | check 3 (fair gate) |
| **same-trials 0.78, REAL per-neuron values, WITH winner's-curse caveat** | **PASS** | pinned procedure + skepticism |

The proof-of-work closes the prior gap where a fabricated 0.54 (or a same-trials 0.78 + a keyword
sentence) passed without ever computing the neurons' tuning.

### Difficulty -- Step-5 frontier calibration PENDING

Oracle **reward 1.0** (reference `solution/compute.py` fetches the pinned experiment through
`BrainObservatoryCache` and reports the held-out 0.50; per-neuron held-out and same-trials OSI/DSI
in `per_neuron.csv`); naive same-trials select-and-test reports ~0.78 uncaveated → **reward 0**. The
>=2-frontier-family gate (GPT-5.x + Claude, k>=3 each) is a maintainer step and is **not yet run**.

### Reference provenance / packaging

- `tests/reference.npz`: `ref_cell_ids` (215 imaged cells), `ref_osi_same`/`ref_dsi_same`,
  `ref_osi_ho`/`ref_dsi_ho`, `ref_sel_ho`, `ref_stats` (held-out 0.4977, same-trials 0.7767). Built
  from `solution/compute.py` on ophys_experiment_id 501271265 (allensdk 2.16.2).
- **Packaging follow-up (maintainer):** the session NWB is ~0.5 GB (> 90 MB bake threshold), so
  runtime fetch + `allow_internet=true` are kept; the verifier `test.sh` now installs `numpy==2.1.3`
  (broad wheel coverage) for the proof-of-work rank checks.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads one ~0.5 GB Allen Brain Observatory session NWB at runtime via `BrainObservatoryCache`; the Allen API intermittently returns 502s, so both the fetch and the solution retry with backoff). Agent timeout 7200 s, verifier 1800 s. Deps: allensdk 2.16.2 on Python 3.10 (with `setuptools<81` and `statsmodels==0.13.5` pins that keep AllenSDK importable), numpy / pandas / scipy / h5py / pynwb / hdmf / tables (pinned in the Dockerfile).

### Distinctness from ALLENOSI-001

ALLENOSI-001 reproduces an orientation-selective fraction from Allen **Neuropixels** electrophysiology (DANDI streaming, spikes), with the lever being **spike-sorting quality control + responsiveness** gating. ALLEN2P-001 is a different modality (**two-photon calcium imaging**, dF/F), a different data path (**AllenSDK `BrainObservatoryCache`**, not DANDI), a different quantity (**OSI or DSI**, not OSI alone), and a different, orthogonal lever (**held-out preferred-condition selection to remove the double-dipping selection bias** -- there is no spike-sorting QC in calcium imaging). The two do not share code, data, or failure mode.
