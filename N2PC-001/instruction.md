# ERP CORE N2pc: signed lateralization in a fixed cohort

Compute the signed PO7/PO8 contralateral-minus-ipsilateral response for subjects
**1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13**, using their original ERP CORE
visual-search recordings.

This is a twelve-person methods adaptation, not a reproduction of the paper's
cleaned N=35 N2pc characterization or recommended 200–275 ms measurement window.
[Kappenman et al. (2021)](https://doi.org/10.1016/j.neuroimage.2020.117465),
Tables 1–2, provides that characterization. Here the fixed endpoint is
**200–300 ms**, with no ICA, ocular, behavioral, reaction-time or participant
exclusions. A lateralized response in this simplified analysis does not by
itself establish artifact-free covert attention.

## Inputs and public contract

The offline originals are at `${N2PC_DIR:-/app/data/n2pc}`: 24 paired SET/FDT
files plus `source_manifest.json` and `SOURCE_NOTICE.md`. The manifest gives
the exact version, size and SHA256/MD5 of every original. Do not download,
substitute a participant, use an answer cache or change source files.

Read **`/app/method_contract.json`**. It specifies the complete numerical
operator, event rules, output schemas, precision and resource bounds.
Equivalent implementations are accepted; no particular library or secret
estimator is required. The recordings have 33 channels at 1024 Hz. Use the
listed 30 EEG channels for the average reference, excluding the three
peripheral EOG channels. File units are not explicitly labeled: the declared
EEGLAB/MNE reading convention interprets stored float32 values as microvolts,
not an independently measured calibration.

## Analysis

- Preserve every original event row and its source index. Target-left codes
  are 111,112,211,212; target-right codes are 121,122,221,222. Responses do not
  determine eligibility.
- Convert one-based event latency to recording-relative time by
  `(latency-1)/1024`, then to an integer sample with nearest, ties-to-even
  rounding. Keep the original event identity even when an epoch is dropped.
- Treat numeric `-99` as a discontinuity: a half-integer latency `k+0.5`
  defines a cut at zero-based sample `k`. Filter the two sides independently.
  Do not interpret the boundary's duration as a new span of missing samples.
- Apply the contract's centered 0.1–30 Hz Hamming FIR with
  `reflect_limited` padding and the 30-channel average reference.
  Full epochs use offsets **-205..461**. Drop epochs outside the recording or
  crossing a discontinuity; do not crop, bridge or interpolate them.
- Baseline each trial/channel using offsets **-204..0** (not -205).
  Measure its corrected mean over offsets **205..307**. These are the actual
  1024 Hz samples in the nominal baseline and 200–300 ms intervals.
- Average trials within each target field. If `L7,L8,R7,R8` are the four
  field/channel means, compute
  `contra=(L8+R7)/2`, `ipsi=(L7+R8)/2`, and `N2pc=contra-ipsi`.
  The fixed-channel comparator is `((L8-L7)+(R8-R7))/2`.
  Give fields equal weights, then give the twelve participants equal weights.
  Counts are not aggregation weights.

Use the same retained trials for scalars and full waveforms. Keep a participant
with empty field support and report the contract's null/undefined state;
never substitute an available-case group result. There is no required sign,
magnitude, fraction of negative participants or near-zero comparator.
The descriptive `n_subjects_negative` count follows the signed values in your
numerically accepted `per_subject.csv`; permitted rounding near zero can change
this count, but cannot exempt an amplitude from its tolerance check.

## Outputs and grading

Write the eight artifacts below to a fresh `${OUTPUT_DIR:-/app/output}`.
Their full typed schemas are in the public contract:

`annotations.csv`, `trials.csv`, `response_epochs.npz`,
`per_subject.csv`, `waveforms.csv`, `n2pc.json`,
`run_metadata.json`, and `findings.md`.

The NPZ contains complete **prebaseline** PO7/PO8 epochs in microvolts, keyed by
subject, original event index, channel label and sample offset. The verifier
reconstructs these from authenticated originals and recomputes all reported
measurements from the accepted submitted epochs. Primitive tolerance is
`1e-6 + 1e-6*abs(reference)` µV; derived tolerance is
`1e-8 + 1e-6*abs(recomputed)` µV. Identities and sample membership are exact.
Coherent row/axis reordering and harmless finite extra fields are allowed.

Grading is binary: complete valid evidence receives 1, otherwise 0.
`findings.md` must be nonempty, but is not checked for keywords or a preferred
biological conclusion. On a failed precondition, exit nonzero and preserve a
`failure_report.json` with the stage and reason. Do not replace partial evidence
with plausible success files or retry against a different source.
