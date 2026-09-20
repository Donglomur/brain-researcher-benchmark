# N2PC-001 — N2pc component amplitude (ERP CORE visual search)

## Dataset
ERP CORE **N2pc** task, BIDS-compatible continuous EEGLAB recordings, OSF node `yefrq`
(parent project `thsqg`), fetched at runtime from `https://osf.io/download/<id>/` (no
credentials). Subjects **1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13** (subject 2 is not in the
released N2pc set). 30 scalp electrodes + 3 EOG, 1024 Hz.

## Paper
Kappenman, Farrens, Zhang, Stewart & Luck (2021), *NeuroImage*, ERP CORE
(https://doi.org/10.1016/j.neuroimage.2020.117465). N2pc component: Luck & Hillyard (1994).

## Deliverable
The **N2pc component amplitude** at the **PO7/PO8** pair — the mean
**contralateral-minus-ipsilateral** amplitude in the **200-300 ms** window, grand-averaged
over the 12 subjects. The quantity is a difference between two scalp electrodes, hence
**reference-independent** (well-posed / convention-invariant).

## Reproduced result
**N2pc = -1.38 uV** (exact -1.375; contralateral 1.59, ipsilateral 2.97 uV; **12/12
subjects negative**). Validated with MNE 1.12.1, 0.1-30 Hz band-pass, average reference,
-200..0 baseline, all target-stimulus events, mean amplitude, per subject then averaged.

## Un-cued lever (private reviewer note)
The one un-cued analytic choice is **how the contralateral/ipsilateral waveforms are formed
from PO7/PO8 given the target's visual field.** The N2pc is *lateralized*: a left-field
target draws the negativity over the right scalp (PO8), a right-field target over the left
(PO7). Target side is the **tens digit** of the 3-digit stimulus code (1=left, 2=right; the
hundreds digit is colour and the units digit the gap — both distractors). The component must
be built by **re-mapping the electrodes per target side** (contra = PO8 on left-target
trials, PO7 on right-target trials). A pipeline that instead takes a **fixed** electrode
difference across all trials (PO8-PO7 or PO7-PO8) **pools the two visual fields**, on which
the negativity sits over opposite electrodes; because the field is balanced it cancels almost
completely. The instruction names the deliverable as "contralateral-minus-ipsilateral" (the
component's definition) but never cues the per-side re-mapping or warns against pooling.

## Step-0 numbers
| analysis | value |
|---|---|
| contralateral-minus-ipsilateral (correct N2pc) | **-1.375 uV** |
| fixed PO8-PO7 across all trials, pooled (naive) | +0.336 uV |
| fixed PO7-PO8 across all trials, pooled (naive) | -0.336 uV |

Robustness of the correct value: -1.374 to -1.378 uV across 0.1-20/30/40 Hz low-pass,
average vs no re-reference, and -150/-200 ms baselines; 12/12 subjects negative. The pooled
fixed-electrode difference stays near zero (|.| ~ 0.34 uV) — the lateralization collapses.

## Grading — proof-of-work verifier
The grade is carried by NUMBERS against a held-out reference (`tests/reference.npz`), built
by running the oracle (`solution/compute.py`) on the pinned ERP CORE N2pc sample (subjects
1/3-13; content pinned by the OSF file ids in `solution/compute.py`). Three pillars
(`tests/proof_of_work.py` + `tests/test_outputs.py`):

1. **Per-subject SIGNED proof of work** — `per_subject.csv` must cover the exact 12-subject
   sample (real ids), be non-constant, and match the held-out per-subject
   contralateral-minus-ipsilateral `n2pc_uv` (SIGNED, tol 0.85 uV, ≥80% of subjects). An
   abs()-ed, sign-flipped, or field-pooled table fails.
2. **Recompute** — the mean of the submitted `n2pc_uv` column must equal both the reference
   grand-average (−1.375 uV) and the reported `n2pc_amplitude_uv`.
3. **Discriminating number (lateralized-vs-pooled)** — the reported N2pc must be a clear
   negativity (≤ −0.70 uV, within 0.40 of −1.375), and the reported pooled fixed-electrode
   difference must be near zero (reference +0.336 uV). A pooled fixed-electrode pipeline
   (~±0.34 uV) cannot match the signed per-subject N2pc.

Validation matrix (subprocess pytest per case): honest oracle → PASS; no-table → FAIL;
constant table → FAIL; non-constant fabricated (right mean, wrong per-item) → FAIL; naive
pooled fixed-electrode → FAIL.

Reference-build data: pinned OSF file ids in `solution/compute.py`; per-subject `n2pc_uv`
range −0.28…−2.84 uV, all 12 negative, grand-average −1.375 uV.

Packaging note: ERP CORE N2pc raw EEGLAB files are >90 MB total, so they are fetched at
runtime from the pinned OSF ids (`allow_internet=true`); baking a derived per-subject
snapshot into `environment/` is a maintainer follow-up.

## Step-5 frontier calibration
PENDING.
