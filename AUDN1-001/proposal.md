## AUDN1-001

**Proposal Title:** Auditory N100 amplitude in the MNE sample dataset — an un-cued baseline-correction trap (skipping baseline inflates the GFP peak ~2x)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** auditory ERP / evoked responses

**Source finding / benchmark:** The **auditory N100** (the N1; EEG counterpart of the MEG N100m/M100), quantified as the peak scalp **Global Field Power (GFP)** amplitude in the 80-120 ms window, for the left-auditory condition of the MNE **sample** dataset (combined MEG/EEG auditory + visual paradigm). **Dataset:** fetched at runtime with `mne.datasets.sample.data_path()` (no credentials). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the auditory N100 peak GFP amplitude") never says whether the evoked response is **baseline-corrected** before the amplitude is measured. An evoked amplitude — and the GFP, which is the spatial standard deviation across electrodes — must be measured against a pre-stimulus baseline; without it the residual per-electrode pre-stimulus offsets add to the spatial variance and inflate the GFP peak. Correctly baseline-corrected, the left-auditory N100 GFP peak is **4.4 uV**; skipping baseline correction inflates it to **~9.2 uV** on the pinned filtered file (and to ~27 uV if the un-filtered raw file is used instead).

Everything else is pinned so only the baseline choice moves the number: the `sample` **filtered** raw file, the left-auditory trigger (code 1), EEG channels with the marked bad channel excluded, the shipped SSP projectors, the average reference, the −0.2..0.5 s epoch, and the 80-120 ms GFP-peak measurement. GFP is chosen as the readout because it is **reference-independent** and needs no electrode hand-selection, so the correct value is a single well-defined number.

**Note on scope (reviewers):** sensor-space **latency** was explored as the graded quantity but did not yield a robust well-posed lever — the GFP N100 latency is ~93 ms and very stable, while single-channel `get_peak` latencies differ inconsistently across conditions (the gap even collapses to 0 ms for the right-auditory magnetometers), so latency was dropped in favour of amplitude. The baseline lever is well-posed and robust (correct value ~4.4 uV is stable across the filtered/un-filtered files and reasonable windows; the naive value is always ≥9 uV). This mirrors the shipped ERPP3-001 pattern (ERP amplitude in physical units, magnitude-compared). MNE's `Epochs` default is `baseline=(None, 0)`, so the naive no-baseline path is a deliberate deviation (as with ERPP3's peak-vs-mean choice); frontier difficulty is left to Step-5 calibration.

### Step-0 (validated, real data — MNE 1.12.1)

Pinned pipeline; peak EEG GFP amplitude in the 80-120 ms window, left auditory:

| baseline | reported N100 amplitude |
|---|---|
| **pre-stimulus baseline correction (correct)** | **4.4 uV** |
| no baseline correction (naive) | **9.2 uV** (filtered file) / ~27 uV (un-filtered) |

Gap ~2.1x on the pinned file. The correct value is robust: 4.39 uV (filtered), 4.57 uV (un-filtered raw), 4.48 uV (un-filtered + 40 Hz low-pass), and 4.39 uV across 70-130 / 80-120 / 90-110 ms windows.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) an N100 amplitude averaged over the left-auditory epochs is reported; (2) the reported amplitude is the **baseline-corrected** value (`|reported| within 2.5 of 4.4 uV`) — the un-baselined values (≥9 uV) are well outside and fail; (3) `findings.md` reports an amplitude consistent with `n1.json`. The grader skips explicitly-labelled no-baseline/reference/metadata fields.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, sample left auditory, 72 epochs): N100 GFP peak = **4.39 uV** (no-baseline 9.23 uV for contrast); verifier **PASS (3/3)**.
- **Naive** no-baseline fixture (9.23 uV): verifier **FAIL** (`test_n1_amplitude_is_baseline_corrected`). Task has teeth.
- Data fetches at runtime via `mne.datasets.sample.data_path()` (no credentials); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads the ~1.5 GB sample dataset once). Deps: mne 1.12.1 + numpy/scipy/pooch.
