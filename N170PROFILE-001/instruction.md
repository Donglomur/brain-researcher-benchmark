# ERP CORE N170 characterization at PO8

Use the public ERP CORE N170 recordings to estimate the signed face-minus-car
amplitude and a 50%-fractional-peak latency at the a priori PO8 electrode.
The participant, not the trial or time sample, is the independent unit.

The scientific target comes from the N170 characterization in Figure 2 and
Tables 1–3 of [Kappenman et al. (2021)](https://doi.org/10.1016/j.neuroimage.2020.117465).
This task is a **paper-derived processing adaptation**, not the paper's complete
ICA/artifact pipeline or an exact reproduction of its published numbers.
A measured fractional-peak latency is not a precise biological effect onset.

## Data

The image contains all 74 original `*_N170_shifted_ds.set/.fdt` files for the
37-person sample at `/app/data/n170profile`, with a pinned source manifest.
The sample is IDs 1–40 excluding 1, 5 and 16. Use these exact IDs; do not select
participants based on the results. Data acquisition is complete; work offline.

The records have 33 channels at 256 Hz. The 30 scalp channels are listed in
`/app/method_contract.json`; the remaining three are EOG. FDT values are
little-endian float32, with channel index varying fastest, interpreted as
microvolts under the declared EEGLAB convention. The original stage already
contains the event shift and downsampling. Do not repeat either operation.
See `/app/SOURCE_NOTICE.md` for provenance and attribution.

## Analysis

Follow the fully public `/app/ANALYSIS_CONTRACT.md` and
`/app/method_contract.json`. In brief:

1. Average-reference the 30 scalp channels and apply the declared .1–30 Hz
   centered Hamming FIR, with explicit segment and padding rules. No ICA or
   additional onset low-pass is part of this adaptation.
2. Faces are event codes 1–40; cars are 41–80. Use the released event clock,
   preserve all event/trial identities, and epoch at offsets −51..102 samples.
   Baseline-correct each epoch over −51..0. Reject an epoch if any scalp
   channel's peak-to-peak range is strictly greater than 150 µV.
3. Average accepted PO8 epochs separately by condition. From face minus car,
   measure signed mean amplitude over the nearest-sample 110–150 ms window.
   Measure the declared ERPLAB-inspired 50%-negative-peak latency in 10–150 ms:
   choose a local trough with the stated neighborhood/fallback rules, then
   search backward for the nearest in-window half-height sample.
4. Report participant measurements, then their complete-cohort mean and
   two-sided participant-level t confidence interval. Undefined conditions or
   onsets must remain explicit nulls, not substituted boundary times or dropped
   participants. Constant defined cohorts have point intervals.

The public `/app/measurement_kernel.py` specifies measurement edge cases and
can be used directly. It intentionally differs from pinned historical ERPLAB
software in three respects: actual negative-voltage support, earliest tied
trough selection, and acceptance of exact half-height equality. No negative
group effect, significance, particular onset, or match to paper numbers is
required. Interpret the result supported by these recordings and this method.

## Outputs and scoring

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `annotations.csv`: every original event.
- `trials.csv`: every face/car candidate and its selection reason.
- `erp_evidence.npz`: condition PO8 averages and trial rejection evidence.
- `per_subject.csv`: all 37 participants' signed measurements and support.
- `n170.json`: complete-cohort summaries with explicit missingness.
- `run_metadata.json`: source identities and observed processing provenance.
- `findings.md`: a short, appropriately limited interpretation.

Exact fields, nulls and numerical bounds are public in
`/app/OUTPUT_CONTRACT.md` and `/app/output_schema.json`. Both JSON reports use
`schema_version: "n170-output-v1"`. Use float64 for waveform evidence;
six-decimal scalar receipts are acceptable. Coherent row/axis permutations and
bounded descriptive extras are allowed.

The verifier independently reconstructs the original-source condition averages,
checks trial selection, and recomputes measurements and group summaries from
your accepted waveform evidence. It does not use an old numerical answer bank.
Scoring is binary: 1 only for a complete valid bundle; there is no proportional
partial-results score. Empty, unsupported or fabricated results do not pass.

Optional scalp/cluster analyses are ungraded. If included, corrected cluster
inference does not establish pointwise electrode significance or an exact onset;
label time/electrode membership as cluster-level only.

On a true input/precondition failure, exit nonzero and write
`failure_report.json` with a nonempty reason. Do not disguise missing conditions
or a scientifically undefined onset as an input failure, and never reuse a
stale successful output bundle.
