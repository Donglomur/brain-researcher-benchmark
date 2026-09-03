## ERPP3-001

**Proposal Title:** ERP CORE P3b rare-minus-frequent amplitude at Pz — an un-cued measurement trap (peak amplitude roughly doubles the mean-amplitude value)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** ERP / oddball P3b

**Source finding / benchmark:** The **P3b** rare-minus-frequent difference wave at **Pz** from the **ERP CORE** active visual oddball paradigm (Kappenman, Farrens, Zhang, Stewart & Luck 2021, *NeuroImage*), reported as the component amplitude in its window. **Dataset:** ERP CORE **P3** downsampled continuous EEGLAB files (OSF node `etdkz`), subjects 1-12, fetched by direct OSF download URLs (same pattern as FACEERP-001). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the P3b rare-minus-frequent difference **amplitude** at Pz over the 300-600 ms window") never says **how** to reduce the window to a single amplitude: **mean amplitude** over the window vs the **peak** (most extreme value) in it. The ERP CORE P3 (and modern ERP practice) uses **mean amplitude** across a fixed window — unbiased by noise and trial count. **Peak** amplitude always latches onto the largest excursion and is biased away from zero; here it roughly **doubles** the value. Everything else is pinned — subjects, average reference, 0.1-30 Hz filter, -200..0 baseline, epochs -200..800, all epochs averaged (no extra rejection), the rare/frequent event-code definition, the Pz channel, and the 300-600 ms window — so only the mean-vs-peak choice moves the number.

Note the reference is **pinned to average** (not a lever here): for a midline parietal P3b at Pz both average and mastoid references are historically defensible, so leaving the reference open would not be well-posed. The lever is the measurement type, which has one correct answer (mean).

### Step-0 (validated, real data — mne 1.12.1)

Pinned pipeline; Pz rare-minus-frequent difference wave, per subject then mean over 12 subjects:

| measurement (300-600 ms) | amplitude |
|---|---|
| **mean amplitude (correct ERP CORE measure)** | **+4.43 uV** |
| peak amplitude (naive) | **+8.85 uV** |

Gap ~4.4 uV, correctly signed. Mean-amplitude value robust across reasonable windows (250-550, 300-500, 300-650, 350-650): 4.03-4.51 uV; peak across the same windows 8.6-8.9 uV. 11/12 subjects show a positive rare-minus-frequent P3b. Rare = codes 11/22/33/44/55 (block's target letter presented); frequent = the other two-digit XY codes.

The 150 uV peak-to-peak rejection used for the short N170 epoch (FACEERP-001) destroys most epochs on these longer, pre-ICA P3 files (one subject loses all rare trials), so it is **not** applied — averaging the full trial set is pinned to keep the quantity deterministic and every subject viable.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) a P3b amplitude aggregated over the 12 subjects is reported; (2) the reported amplitude is the **mean-amplitude** value (`|reported| within 2.0 of 4.43 uV`, magnitude-compared so robust to the difference-wave sign) — the peak value (~8.85) is ~4.4 away and fails; (3) `findings.md` reports a Pz amplitude consistent with `p3.json`. The grader skips explicitly-labelled peak/reference fields and per-subject arrays.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, ERP CORE P3 subjects 1-12): mean amplitude = **+4.43 uV** (peak +8.85 for contrast); verifier **PASS (3/3)**.
- **Naive** peak-amplitude fixture: +8.85 uV; verifier **FAIL** (`test_p3b_amplitude_is_mean_not_peak`). Task has teeth.
- Data fetches at runtime via direct OSF download URLs (node `etdkz`); `allow_internet=true`. OSF fetch verified reliable during authoring (all 24 files downloaded).
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 12 subjects × 2 files from OSF). Deps: mne 1.12.1 + numpy/scipy.
