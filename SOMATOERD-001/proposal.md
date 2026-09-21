## SOMATOERD-001

**Proposal Title:** Contralateral sensorimotor beta ERD to median-nerve stimulation — an un-cued induced-vs-evoked power trap (evoked power flips the sign and inflates the value ~25x)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG sensorimotor rhythms / event-related (de)synchronization

**Source finding / benchmark:** The contralateral sensorimotor **beta-band (15-30 Hz) event-related desynchronization (ERD)** evoked by median-nerve stimulation, in the MNE **somato** dataset (single subject, Elekta/Neuromag 306-channel MEG, 111 median-nerve trials), quantified as the percent change in beta power relative to a pre-stimulus baseline (Pfurtscheller & Lopes da Silva 1999). **Dataset:** fetched at runtime with `mne.datasets.somato.data_path()` (no credentials). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the beta ERD as the percent change in beta power relative to baseline") never says **how the time-frequency power is obtained from the trials**. Beta ERD/ERS are **induced** (non-phase-locked) phenomena: the correct estimate computes the time-frequency power of **every single trial and then averages the power** (`epochs.compute_tfr(..., average=True)` — the MNE default path). A naive pipeline computes the time-frequency power of the **trial-average / evoked response** (`epochs.average().compute_tfr(...)`), keeping only phase-locked power. On these data the early somatosensory evoked field dominates the evoked spectrum and its pre-stimulus evoked baseline is averaged down toward zero, so the evoked-power "ERD" comes out **large and POSITIVE** — the opposite sign of the true ERD and off by an order of magnitude.

Everything else is pinned so only this choice moves the number: the four contralateral gradiometers (`MEG 1342/1343/1332/1333`), Morlet wavelets over 15-30 Hz on a 1 Hz grid with n_cycles = freq/2, percent baseline over −1.0..−0.25 s, the 15-30 Hz band, and the 0.10-0.35 s window. Baseline **mode** is pinned to *percent* on purpose — it is the classical Pfurtscheller ERD definition and, on this modest-magnitude ERD, the mode alternatives (logratio/zscore/ratio) do not give a robust fair gap, so the mode is not the lever. The measurement window is pinned early because this dataset is dominated by a large post-stimulus **beta rebound (ERS, ~+120%)**; a broad/late window would report the rebound, but pinning the window removes that as a confound and isolates the induced-vs-evoked choice.

### Step-0 (validated, real data — MNE 1.12.1)

Pinned pipeline; mean percent-baseline beta power over the four gradiometers, band and window:

| time-frequency power | reported ERD |
|---|---|
| **induced / total (per-trial, then averaged) — correct** | **−17.7 %** |
| evoked (time-frequency of the trial-average) — naive | **+443.6 %** |

Gap: opposite sign, ~25x in magnitude. The correct value is robust to reasonable Morlet choices (n_cycles = f/2 → −17.7%; n_cycles = 7 → −20.3%; n_cycles = f/4 → −18.5%; multitaper → −10.3%) and to the exact frequency grid; all land inside the verifier tolerance. The channels sit over the hemisphere contralateral to the stimulated median nerve (head-coordinate x > 0) and carry both the strongest ERD and the strongest rebound — the sensorimotor signature.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) a beta-ERD percentage aggregated over the trials is reported; (2) the reported value is the **induced-power** value (`|reported| within 8.0 of 17.7 %`, magnitude-compared so robust to the −17.7 % vs +17.7 %-decrease sign convention) — the evoked value (~+444 %) is ~426 outside and fails; (3) `findings.md` reports a beta ERD magnitude consistent with `erd.json`. The grader skips explicitly-labelled evoked/reference/metadata fields.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, somato sub-01): induced ERD = **−17.73 %** (evoked +443.6 % for contrast); verifier **PASS (3/3)**.
- **Naive** evoked-power fixture (+443.6 %): verifier **FAIL** (`test_erd_is_induced_not_evoked`). Task has teeth.
- Data fetches at runtime via `mne.datasets.somato.data_path()` (OSF, no credentials); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads the ~600 MB somato dataset once). Deps: mne 1.12.1 + numpy/scipy/pooch.

---

## Proof-of-work verifier (2026-09)

The prior grader accepted any `erd.json` whose single `beta_erd_percent` had magnitude
~17.7 (|.| in [9.7, 25.7]) — a fabricated scalar + a keyword `findings.md` passed. This
revision applies the suite-wide proof-of-work contract (single-value / RESTCONN model).

**Held-out reference** (`tests/reference.npz`, built from `solution/compute.py` on the real
MNE somato sub-01 recording, never shipped to the agent): the induced beta-band power time
course (percent baseline, 901 samples over -1.5..1.5 s) + `ref_stats`
(induced window ERD -17.73%, naive evoked window +443.60%). sha256
`ca00e1377bfc6d1dd9406998fa3e4251fb74c59e3665dfb87e175e5cdc2e1f0a`.

**Neutral intermediate** (added to Required Outputs, un-cued): `beta_power_timecourse.csv`
— the 15-30 Hz power over the four gradiometers vs epoch time. BOTH a correct
(per-trial-then-average) and a naive (average-then-TFR) pipeline produce such a curve, so
requiring it does not cue the un-cued induced-vs-evoked judgement; matched to the held-out
induced reference it closes fabrication AND the naive shortcut (the evoked curve is a large
positive excursion, r ~ -0.07 with the reference).

**Four pillars** (`tests/test_outputs.py` + `tests/proof_of_work.py`): (1) the submitted
curve tracks the held-out reference (cross-time r >= 0.85); (2) the window ERD recomputed
FROM the submitted curve == reference == reported `erd.json`; (3) the ERD graded as a number
— a decrease (<= -5%), closer to the induced value than the evoked artefact; (4) secondary
prose (magnitude consistent with `erd.json`).

**Validation** (subprocess pytest per case, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, numpy 2.1.3):

| case | result |
|---|---|
| honest (oracle) | PASS |
| defensible (curve + numerical noise) | PASS |
| no time course | FAIL |
| constant curve | FAIL |
| fabricated (right window ERD, scrambled curve) | FAIL (pillar 1 only — the intended teeth) |
| naive evoked-power curve | FAIL |

Data still fetches at runtime (`allow_internet=true`); the somato recording exceeds a
convenient bake size, so baking the derived TFR is a maintainer follow-up.
