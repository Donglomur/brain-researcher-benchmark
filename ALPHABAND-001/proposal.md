## ALPHABAND-001

**Proposal Title:** Reproduce the Berger effect (occipital alpha, eyes-closed vs eyes-open) — an un-cued occipital-channel-selection trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Human EEG / oscillations

**Source finding:** Berger, H. (1929), *Über das Elektrenkephalogramm des Menschen* — posterior alpha (8–13 Hz) is enhanced with eyes closed and suppressed with eyes open, maximally over occipital cortex. **Dataset:** PhysioNet **EEG Motor Movement/Imagery** database (`mne.datasets.eegbci.load_data`), subjects 1–5, run 1 (eyes open) and run 2 (eyes closed) — the two baseline resting recordings. Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the **occipital** alpha-band power ratio eyes-closed vs eyes-open") names the target but never mentions the pitfall. The raw EDF channel labels in this dataset are **non-standard** — they carry trailing dots and mixed casing (`"O1.."`, `"Oz.."`, `"O2.."`, `"Fc5."`, …). A direct occipital pick (`pick_channels(["O1","O2","Oz"])`) silently matches **nothing**, and a careless pipeline falls back to averaging alpha over the **whole head (64 channels)**, which dilutes the strongly-occipital Berger effect. The correct pipeline runs `mne.datasets.eegbci.standardize` and sets the 10-05 montage first, then measures alpha over the occipital electrodes. The instruction pins everything else (subjects, runs, band 8–13 Hz, Welch PSD, common-average reference, mean-of-per-subject-ratios) so only this channel-handling choice moves the number.

### Step-0 (validated, real data — mne 1.12.1)

Subjects 1–5, band 8–13 Hz, common-average reference, Welch (2-s segments), mean across subjects of per-subject EC/EO occipital alpha ratio:

| pipeline | ratio (mean across subjects) |
|---|---|
| **occipital O1/O2/Oz (correct)** | **19.64** (per-subject 16.5, 8.0, 24.3, 48.0, 1.3) |
| whole-head 64-ch average (naive trap) | **4.37** |

`correct > naive` for all 5 subjects. **Robustness of the correct number** (sensitivity sweep, band pinned to 8–13 Hz): occipital electrode set {O1,O2,Oz}→19.6, {O1,O2}→21.1, {O1,O2,Oz,Iz}→17.8, {O1,O2,Oz,POz,PO3/4/7/8}→19.3; no re-reference→11.4; Welch 4-s→20.7; pooled-means aggregation→16.1. Every genuine occipital measurement lands in ~11–23; every whole-head/global answer within the pinned band is ≤ ~5. The verifier accepts `|reported − 19.6| < 10` (window 9.6–29.6), which passes all occipital variants and fails the whole-head trap.

### Verifier — proof-of-work (3 pillars, NUMBERS not keywords)

The grade is carried against a held-out reference (`tests/reference.npz`) built by running
the oracle on the pinned EEGBCI recordings (subjects 1-5, runs 1/2). `tests/proof_of_work.py`
+ `tests/test_outputs.py`:

1. **Per-subject proof of work** — `per_subject.csv` must cover the 5 subjects, be
   non-constant, and match the held-out per-subject OCCIPITAL eyes-closed/eyes-open ratios
   (tol max(2.5, 30%), ≥80% of subjects; Berger direction ratio>1 for most). The real
   occipital per-subject ratios span ~1.3-48; a whole-head pipeline compresses them to ~4
   and cannot match.
2. **Recompute** — the mean of the submitted per-subject `ratio` must equal both the
   reference occipital mean (19.64) and the reported headline ratio.
3. **Discriminating number (occipital-vs-whole-head)** — the reported ratio must be the
   occipital ratio (within 3.0 of 19.64) and clearly above the whole-head dilution
   (reference 4.37); a whole-head/global average fails.

Validation matrix (subprocess pytest per case): honest oracle → PASS; no-table → FAIL;
constant → FAIL; non-constant fabricated (right mean, wrong per-item) → FAIL; naive
whole-head → FAIL.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, cached EEGBCI): ratio = **19.641**; verifier **PASS** (2/2).
- **Naive** whole-head 64-ch average fixture: ratio = **4.374**; verifier **FAIL** (`test_berger_ratio_reproduced`). Task has teeth.
- Data fetches at runtime via `eegbci.load_data` (PhysioNet); `allow_internet=true`. Dev validation used the cached copy under `~/mne_data/MNE-eegbci-data`.
- **Step-5 frontier calibration PENDING** (maintainer step): oracle-passes + naive-fails validated locally; the ≥2-frontier-family difficulty gate is a maintainer step.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 10 short EDF recordings, subjects 1–5 × 2 runs). Deps: mne 1.12.1 + numpy/scipy/pooch.
