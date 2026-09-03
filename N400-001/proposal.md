## N400-001

**Proposal Title:** ERP CORE N400 unrelated-minus-related amplitude at CPz — an un-cued trial-selection trap (pooling prime words roughly halves the target N400)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** ERP / N400 semantic access

**Source finding / benchmark:** The **N400** unrelated-minus-related difference wave at **CPz** from the **ERP CORE** word-pair association paradigm (Kappenman, Farrens, Zhang, Stewart & Luck 2021, *NeuroImage*), reported as the component amplitude in its window. **Dataset:** ERP CORE **N400** downsampled continuous EEGLAB files (OSF node `29xpq`), subjects 1-12, fetched by direct OSF download URLs (same pattern as ERPP3-001 / FACEERP-001). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **unrelated-minus-related** N400 difference **amplitude** at CPz over 300-500 ms") never says **which stimulus events** enter the two conditions. The N400 relatedness effect is elicited by the **target** word (the second word, when the relation to the prime is realized), so the contrast must be built from **target words only**: unrelated targets (221/222) minus related targets (211/212). The **prime** words (codes 1XY) precede the point at which relatedness can be evaluated and carry **no** relatedness effect (the prime-only difference is ~0). A pipeline that groups by the "Related / Unrelated" event-code column alone — pooling primes and targets, {121,122,221,222} minus {111,112,211,212} — dilutes the target effect with an equal number of ~zero-difference prime trials and roughly **halves** the reported amplitude. Everything else is pinned — subjects, P9/P10 mastoid reference, 0.1-30 Hz filter, -200..0 baseline, epochs -200..800, all epochs averaged (no extra rejection), the CPz channel, the 300-500 ms window, and mean-amplitude measurement — so only the trial-selection choice moves the number.

The reference is **pinned to the ERP CORE P9/P10 mastoid montage** (not a lever). This is the reference documented for the N400 in the ERP CORE README, and it gives a large, clean centro-parietal N400 (all 12 subjects negative). It is not left open, so the reference is not part of the well-posedness.

### Step-0 (validated, real data — mne 1.12.1)

Pinned pipeline; CPz unrelated-minus-related mean amplitude 300-500 ms, per subject then mean over 12 subjects:

| trial selection | amplitude |
|---|---|
| **target words only (correct)** | **-8.70 uV** |
| prime + target pooled by relatedness (naive) | **-4.20 uV** |
| prime words only (sanity, ~0) | +0.18 uV |

Gap ~4.5 uV, correctly signed. The mechanism is a dilution of equal magnitude, so it is robust: it holds across reasonable windows (250-550 / 300-500 / 350-550 at CPz: target -7.9…-8.7 vs pooled -3.7…-4.2) and neighbouring midline channels (Cz, Pz). 12/12 subjects show a negative target-only N400. The prime-only difference (+0.18 uV) confirms primes carry no relatedness effect.

Note on levers that do NOT discriminate here (tested, negative): because the graded quantity is a **difference wave**, linear common-mode distortions largely cancel. High-pass cutoff (none…1.0 Hz) moves the target N400 by <0.3 uV; low-pass cutoff (10…40 Hz) is negligible; baseline choice (-200..0 vs none) moves it <0.4 uV on 12 subjects. The trial-selection lever is the one that survives, because it changes the two conditions differentially.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) an N400 amplitude aggregated over the 12 subjects is reported; (2) the reported amplitude is the **target-only** value (`|reported| within 2.0 of 8.70 uV`, magnitude-compared so robust to the difference-wave sign) — the pooled value (~4.20) is ~4.5 away and fails; (3) `findings.md` reports a CPz amplitude consistent with `n400.json`. The grader skips explicitly-labelled pooled/reference fields and per-subject arrays.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, ERP CORE N400 subjects 1-12): target-only mean = **-8.70 uV** (pooled -4.20 for contrast); verifier **PASS (3/3)**.
- **Naive** pooled-by-relatedness fixture (-4.20 uV): verifier **FAIL** (`test_n400_amplitude_is_target_only`). A wrong-reference-but-correct-selection fixture (-3.40 uV under average reference) also **FAILS**. Task has teeth.
- Data fetches at runtime via direct OSF download URLs (node `29xpq`); `allow_internet=true`. OSF fetch verified reliable during authoring (all 24 files downloaded, exact `<n>_N400_shifted_ds.{set,fdt}` names).
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 12 subjects × 2 files from OSF). Deps: mne 1.12.1 + numpy/scipy.
