# Processed-input calcium source condition v2

This version corrects the predecessor's conflation of locked output availability
with upstream model exposure. It keeps the same prospective, session-local
measured-kinematics target, numerical estimator, scorer, controls and split
freezer. It does not inherit scientific qualification from any predecessor.

The immutable predecessor is `../train-only-decoding-v1/pipeline.py`, SHA256
`f950ae7a4885471e0cc0aaabfa94e2c582aea4f25f5a4d16b6ee61473f8f11f8`.
Commit `e004272bb6599882a5e2f97d885cf77b2e257d0f` additionally preserves the
reviewed first MAT reader and its temporary blanket RADICaL refusal. Neither
predecessor is edited. The current-binding integrator must preserve the immediate
task and understanding preimages separately before adopting this successor.

## Same target; corrected source condition

Every condition still covers all five imaging mice and ten named sessions,
original eligible trials, matched neural/kinematic lock masks, LR1 left/LR2 right,
and the exact 51 rows at `-100:10:400` ms. Angles in source-declared degrees and
velocities in source-declared degrees/second remain separate 24-joint requests.
There is no added lag, interpolation, invented row, changed target or trial
reduction. Frozen 100-cell/90-PC/ridge-alpha-1 scientific settings and existing
whole-trial split/control mathematics remain unchanged; smaller software fixtures
do not qualify that scientific configuration.

The author caller `preproc/loadLockSave.m`, at commit
`815b610b3beddfed5a3abf611d3a465ab9e4ce5c`, specifies the 101-row locked output
grid `-200:10:800`. The adapter verifies actual supplied grid/config and matrix
dimensions; the normalized pipeline validates the bound record. This grid does
**not** establish the temporal or fitted-trial exposure of upstream processing.

| Quantity | Smoothed events (`neurons.data`) | RADICaL (`neurons.radical_rates`) |
|---|---|---|
| Locked output | Exact `-200:10:800` grid | Same exact grid, independently checked |
| Decoder output | Exact `-100:10:400` membership | Same exact membership |
| Source preprocessing request | SD35 ms, `ceil(2*35/10)=7` padding bins, requested resampling grid `-270:10:870`, then trim | Direct selection of supplied rates; no added SD35 smoothing |
| Full raw-frame dependency | Unverified; requested resampling points are not a complete raw dependency bound | Unverified |
| Model temporal context | Not the RADICaL condition; deconvolution/learned preprocessing remains unknown | Actual inference/input interval unknown; conflicting source statements retained |
| Fitted trials/recordings/checkpoints | Unknown | Unknown |

The RADICaL caller grid is `-200:10:800`; its comment describes the model fit
timepoints. `eventLockRADICaL.m` has a nonexecuting `-200:10:790` comment. The
paper describes a `-100` to `+800` modeling interval with 100 ms padding removed
after fitting. Symmetric padding would suggest `-200` to `+900`, but that is an
inference, not a measured model context or required exported row. These statements
are retained separately. No +900 row is required or fabricated; no +800 full
exposure claim is substituted.

## Versioned contract

`pipeline.admit` now requires `calcium_normalized_v2` and `calcium_protocol_v2`,
with `upstream_exposure_policy` equal to
`processed_inputs_separate_support_unknown_exposure_v2`. Each session in both
documents must contain a `source_condition` record created by
`source_condition.build_source_condition(feature_variant)`. Its exact canonical
JSON SHA256 is bound by `upstream_exposure_sha256` in both documents. The actual
body is therefore checked, unlike the predecessor's otherwise opaque exposure
digest. Other provenance hashes remain externally declared, not independently
rederived by this component.

The shared revision identifier
`radical_lift_locked_processed_input_source_condition_v2` names the adopted
source-condition correction. The explicit `feature_variant` field determines
whether a request uses smoothed events or RADICaL; that identifier never licenses
substituting one representation for the other.

The source-condition record separates the output grids, preprocessing support,
model input/inference context and fitted-trial training exposure. Exact canonical
JSON comparison rejects boolean/numeric aliases, undocumented fields, known/unknown
relabeling and invented exposure receipts. The old `upstream_temporal_support_ms`
key is rejected anywhere in a v2 document. An authenticated new exposure receipt
requires a reviewed versioned extension; this implementation accepts the reviewed
known/unknown state only. Unknown does not mean evidence of leakage: the record
says `fold_safety_status: unknown`, with qualification false.

`source_condition.py` binds exact author-source and paper XML hashes. The paper's
internal version DOI is `10.7554/eLife.106270.3`; the publisher XML filename's
`v1` is not used as the article-version identity. `pipeline.py` pins the source
condition implementation, while the v2 reader and delivery pin the pipeline.

## Execution and qualification boundaries

The condition is retrospective processed-input readout. There is no causal or
online claim, strict bounded-raw-observation parity, upstream fold-safety claim,
authenticated original-model parity, or new scientific result. Prospective
train-only decoder fitting does not make upstream preprocessing train-only.

No authentic locked export has been inspected. The complete released original
asset inventory and one bounded MATLAB7.3 header do not establish availability or
serialization of an authentic `liftLocked` export. Original raw-to-locked
preparation, missing `getInverseKinematics`, actual clock/ROI/camera mappings,
model input/training exposure, protected execution and authentic reference/control
competence remain unqualified. Matching ROI counts/lags cannot establish native
column order, and target-unit labels are source-declared, not measured calibration.

Focused successor controls are in
`../locked-mat-admission-v2/test_source_condition.py`. They use generated fixtures
to test the changed admission and delivery boundaries, never as substitute
scientific examples. Historical v1 test receipts remain historical and are not
represented as v2 authentic runs. `SOURCE.json` records the exact dependency and
reviewed-source cutoff.
