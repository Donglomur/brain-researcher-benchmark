## FACEERP-001

**Proposal Title:** The N170 face effect at PO8 — an un-cued EEG-reference trap (hard reproduction)

**Scientific Domain:** Life Sciences / Neuroscience / EEG-ERP (face perception, N170)

**Source paper / dataset:** Kappenman, Farrens, Zhang, Stewart & Luck (2021), *ERP CORE: An open resource for human event-related potential research*, NeuroImage, https://doi.org/10.1016/j.neuroimage.2020.117465. Data: ERP CORE **N170** continuous EEGLAB recordings (`<n>_N170_shifted_ds.set/.fdt`), subjects 1-12, fetched at runtime from the ERP CORE OSF node (`pfde9`) via pinned `https://osf.io/download/<id>/` file ids.

**Status: FULL runnable task, oracle + naive validated locally. Step-5 frontier calibration PENDING (maintainer step).**

### Genre
Reproduction (numeric match). The whole pipeline is pinned in the instruction — subjects 1-12, filter 0.1-30 Hz, epochs -200..400 ms, face codes 1-40 / car codes 41-80, -200..0 baseline, 150 uV rejection, EOG channels, channel PO8, measurement window **110-150 ms**, and measure = **per-subject peak (most negative) of the face-minus-car difference wave, then mean over subjects**. The **only** thing left to the agent is the montage reference.

### The un-cued lever (PRIVATE — never named in instruction.md)
The EEG reference. The ERP CORE N170 dataset is referenced to the **average of the scalp electrodes** (README Script #1: "re-reference the data to the average of all 33 EEG sites"), which preserves the occipito-temporal N170 as a genuine negativity at PO8. The classic face-ERP alternative — a **P9/P10 linked-mastoid** reference — sits right beside the N170 generators and roughly halves the measured amplitude (and inverts the absolute face N170), so it gives a materially smaller number. The instruction only says the referencing "should follow the convention of the ERP CORE N170 dataset you are reproducing"; it never says "average", "mastoid", "linked mastoid", or "reference choice matters".

### The design note that makes it work
The face-car effect at PO8 **peaks ~110-150 ms and reverses sign by ~150-200 ms**, and it interacts with the measure: in 110-150 ms, average-reference MEAN amplitude is only -3.47 uV (collides with the mastoid peak), while the **peak/min** measure cleanly separates the two references. So the task pins the peak/min measure in the 110-150 ms window (the ERP CORE canonical N170 window, README Scripts #11/#12), NOT a 130-200 ms mean.

### Step-0 result (measured; subjects 1-12, per-subject peak then mean)
| reference | face-car N170 peak at PO8 (110-150 ms) |
|---|---|
| **average reference (correct ERP CORE convention)** | **-6.17 uV** |
| P9/P10 linked-mastoid (naive) | -3.15 uV |

12/12 subjects same direction; paired t = -6.58, p = 4e-5. On the **absolute face N170** the polarity even flips (avg peak -2.75 uV -> mastoid +1.30 uV). The correct reference roughly doubles the amplitude relative to the naive one.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) numeric reproduction — the reported amplitude matches the average-reference value on **magnitude** (|amp| within **1.5 uV** of 6.17; magnitude comparison is robust to whether the sign is reported); the linked-mastoid magnitude (3.15) is ~3 uV away and fails, while the grand-average-then-peak variant of the correct reference (-5.46) passes. (2) light honesty check — `findings.md` reports an N170 amplitude at PO8 consistent with `n170.json`. No weighted rubric, no score.json.

### Discrimination (validated locally)
| solution | amplitude | verdict |
|---|---|---|
| reference / oracle (average reference) | -6.17 uV | **PASS** |
| naive (P9/P10 linked-mastoid) | -3.15 uV | **FAIL** |

### Cost
`hard`. cpus 2, mem 8 GB, internet on (fetches 12 subjects x 2 EEGLAB files ~ 0.5 GB from OSF at runtime). Deps: mne 1.12.1 + numpy/scipy (EEGLAB .set read via scipy; no pymatreader needed for these v6/7.2 files). Runtime ~2-4 min.

### Notes / caveats
- **OSF-fetch reliability caveat:** the shipped fetch pulls 24 files from `osf.io/download/<id>/` at runtime; OSF occasionally throttles or times out. The file ids are pinned and were verified to download the exact bytes matching the cached copies (sizes match). A transient OSF failure is an infra artifact (the task writes `failed_precondition`), not a task FAIL. For dev, `ERPCORE_N170_DIR` can point at a local cache.
- Step-5 frontier calibration (>=2 frontier families, k>=3, hand re-scored) is the maintainer gate and is PENDING; this proposal ships the oracle-pass + naive-fail evidence.
