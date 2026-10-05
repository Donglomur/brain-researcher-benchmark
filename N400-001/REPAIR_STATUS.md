# Repair evidence

## Scope and original-source identity

Easy original-data method control, not the paper's artifact-cleaned 39-person N400
finding. All 24 original OSF version-1 SET/FDT files match published byte lengths,
SHA256 and MD5: 197,427,832 bytes. No synthetic EEG or mutable-source substitution.
Initial source acquisition completed in 58.83 seconds with zero retries. A later
portable Docker source build failed with masked diagnostics; that failure is retained.
After adding safe error reporting, one explicit retry succeeded; no source pins or
numerical parameters were changed. Each attempt has zero automatic retries.

Source manifest: `09483405a6b48aec79d9e40c96409709a7e0c4e462cb0deb646551fe6cfb2616`.
Public method contract: `8771e08ea44ee3c973a9b57c32f7d0352078f50e89767334635b8e2c8f1a0dc1`.
The estimator was frozen before signal inspection. A pre-pilot schema-only addition
made nested metadata requirements public; it did not change the scientific method.

## Executed local evidence

- Original source: 12 continuous 33-channel/256 Hz files, 4,343 events and 1,440 target
  epochs. All targets retained, 60 per condition per subject; no boundary records.
  Boundary handling is fixture-tested, not an actual challenge in this source.
- Signed equal-subject contrast: −8.694516432690577 µV. All 12 subject contrasts
  happen to be negative; negativity is not an acceptance condition.
- Independent direct-FDT, analytic sinc/Hamming, NumPy-FFT and scalar-reduction route
  matches every event/trial/curve/subject plus all required source traces and epochs.
  Maximum filtered-trace difference is 1.70e−10 µV; group contrast differs by 1.5e−14 µV.
  Independence is numerical, not absolute: both routes use SciPy to parse the SET container.
- A third original-source SciPy FIR/convolution route rebuilt `tests/reference.npz`:
  SHA256 `e7385b2a9f1a7ac8abf90375765151ac5250ccda4eb689980e3e40429deee52b`.
  Neither legacy bank nor oracle output supplied its reference measurements.
- Exact native runtime image: **252 tests passed, no skips**, including genuine oracle
  and independent positives, equivalent formatting/software acceptance, and 55
  malformed or scientifically wrong output rejections. The signed trial/curve/subject
  checks prevent opposing errors from passing through group-mean cancellation.

These tests establish engineering/numerical consistency, not physiological ground
truth. Uncleaned source excursions remain: raw required channels approximately
−316,660..296,758 µV, filtered referenced recording −8,915..9,934 µV, and retained
epochs −75.7..263.0 µV. These descriptive ranges are not an artifact diagnosis or
an exclusion criterion. No ICA, behavioral screening or amplitude rejection is
performed. Voltage units follow the EEGLAB FDT convention, not populated header
unit annotations. Licensing scope remains documented without claiming precedence
between OSF CC-BY 4.0 and the author repository's CC-BY-SA 4.0 notice.

## Reproduction and final gate

The runtime contains only pinned originals, their manifest and the public method;
oracle, answer bank, authoring code and private analysis arrays are not baked in.
`solution/solve.sh` runs offline. `builder/build_reference.py` independently rebuilds
the bank from originals and checks supplied genuine outputs before atomic replacement.
`builder/test_real_outputs.py` uses `REPAIR_ORACLE_OUTPUT` and
`REPAIR_INDEPENDENT_OUTPUT`; without those artifacts its source-execution cases skip,
so a mechanics-only test run must not be called complete validation.

At this commit, native original-source validation is complete; clean-commit Harbor
oracle and actual final-image regressions are the remaining delivery gate. Their
receipts are recorded externally against the resulting commit to avoid a circular
commit/hash claim. No push, merge, public image release or Sol/model run is claimed.
