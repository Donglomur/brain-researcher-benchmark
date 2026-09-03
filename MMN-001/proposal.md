## MMN-001

**Proposal Title:** ERP CORE mismatch-negativity deviant-minus-standard amplitude at FCz — an un-cued measurement trap (peak amplitude roughly doubles the mean-amplitude value)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** ERP / auditory mismatch negativity

**Source finding / benchmark:** The **MMN** deviant-minus-standard difference wave at **FCz** from the **ERP CORE** passive auditory oddball paradigm (Kappenman, Farrens, Zhang, Stewart & Luck 2021, *NeuroImage*), reported as the component amplitude in its window. **Dataset:** ERP CORE **MMN** downsampled continuous EEGLAB files (OSF node `5q4xs`), subjects 1-12, fetched by direct OSF download URLs (same pattern as ERPP3-001 / FACEERP-001; the auditory MMN file has no monitor-delay shift, so the continuous file is `<n>_MMN_ds.set`). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the deviant-minus-standard MMN difference **amplitude** at FCz over 125-225 ms") never says **how** to reduce the window to a single amplitude: **mean amplitude** over the window vs the **peak** (most extreme / most-negative value) in it. The ERP CORE MMN (and modern ERP practice) uses **mean amplitude** across a fixed window — unbiased by noise and trial count. **Peak** amplitude always latches onto the largest negative excursion and is biased away from zero; here it roughly **doubles** the value. Everything else is pinned — subjects, P9/P10 mastoid reference, 0.1-30 Hz filter, -200..0 baseline, epochs -200..800, all epochs averaged (no extra rejection), the standard/deviant codes (80/70), the FCz channel, and the 125-225 ms window — so only the mean-vs-peak choice moves the number. This is the same measurement lever validated in the shipped ERPP3-001, applied here to a small frontocentral negativity in a different (auditory) modality.

Note the reference is **pinned to the ERP CORE P9/P10 mastoid montage** (documented for the MMN in the ERP CORE README), not a lever.

### Why not a baseline / window / trial-selection lever (tested, negative)

Because the graded quantity is a **difference wave**, linear common-mode distortions cancel: baseline choice (-200..0 vs none) moves the MMN mean <0.5 uV on 12 subjects and high-/low-pass cutoff is negligible. Trial selection does not discriminate either — the "first stream of 15 standards" (code 180) is only 15 of ~800 standards, so including or excluding it is invisible in the average. The measurement (mean-vs-peak) lever is the one that produces a clean, robust gap on this small component.

### Step-0 (validated, real data — mne 1.12.1)

Pinned pipeline; FCz deviant-minus-standard difference wave, per subject then mean over 12 subjects:

| measurement (125-225 ms) | amplitude |
|---|---|
| **mean amplitude (correct ERP CORE measure)** | **-1.82 uV** |
| peak amplitude (naive, most-negative) | **-3.53 uV** |

Gap ~1.7 uV, correctly signed. Mean-amplitude value robust across reasonable windows (100-200, 125-225, 150-250: -1.5…-1.8 uV) and neighbouring frontocentral sites (Fz -1.96, FC3/FC4 ~-1.7). 11/12 subjects show a negative deviant-minus-standard MMN; every subject's peak is more extreme than its mean (peak grand mean -3.53). Standard = code 80, deviant = code 70.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) an MMN amplitude aggregated over the 12 subjects is reported; (2) the reported amplitude is the **mean-amplitude** value (`|reported| within 0.8 of 1.82 uV`, magnitude-compared so robust to the difference-wave sign) — the peak value (~3.53) is ~1.7 away and fails; (3) `findings.md` reports an FCz amplitude consistent with `mmn.json`. The grader skips explicitly-labelled peak/reference fields and per-subject arrays.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, ERP CORE MMN subjects 1-12): mean amplitude = **-1.82 uV** (peak -3.53 for contrast); verifier **PASS (3/3)**.
- **Naive** peak-amplitude fixtures: most-negative -3.53 uV and most-absolute -2.99 uV both **FAIL** (`test_mmn_amplitude_is_mean_not_peak`). Task has teeth.
- Data fetches at runtime via direct OSF download URLs (node `5q4xs`); `allow_internet=true`. OSF fetch verified reliable during authoring (all 24 files downloaded, exact `<n>_MMN_ds.{set,fdt}` names).
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 12 subjects × 2 files from OSF). Deps: mne 1.12.1 + numpy/scipy.
