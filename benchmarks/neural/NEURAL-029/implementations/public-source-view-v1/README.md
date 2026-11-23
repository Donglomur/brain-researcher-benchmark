# Public source-trajectory renderer

`view_source.py` renders one permitted one-second-condition calcium trace from
NEURAL-029's public packet. Select an opaque pair, source split, one-based trial
and registered-cell index. The page retains every one of the 61 samples at
0, 0.05, …, 3 seconds after movement end; it performs no averaging, smoothing,
time warping, trial filtering or target-response lookup.

```sh
/ADMITTED/venv/bin/python -I -B view_source.py \
  --input /PUBLIC_PACKET_ROOT --pair-id PUBLIC_PAIR_ID \
  --split calibration --trial-index1 1 --cell-index1 1 \
  --output /FRESH_OUTPUT/source-trace.svg
```

Python 3.11/3.12 and the existing admitted NumPy 2.2.6 environment are required.
The renderer authenticates its sibling `public-warp-reference-v1/reference_program.py`
against fixed reviewed bytes before using its public-manifest and file-capture
primitives. It validates every manifest descriptor, then opens only the selected
pair's public NPZ. Both calibration and validation arrays in that selected file
must have complete finite trial × cell × 61 geometry; unsupported archive members
and oversized NPY headers are rejected before array allocation. Other pairs'
arrays are not opened or claimed verified. The complete original task remains
every target trial, registered cell and time across the declared full cohort.

The y-axis is linear and page-scaled. Its limits are printed and recorded in SVG
metadata; constant traces appear at the midpoint. Amplitudes remain released
processed calcium values with physical units unqualified. The dashed marker is
the planned one-second source delay, not an observed reward event. The page labels
calibration versus validation, the source-order trial index, opaque cell identity,
and the planned two-second target condition. It never displays target responses.
Source chronology and biological identity still require independent admission.

The SVG carries the selected source NPZ hash and permitted metadata. It is an
output representation for a future typed viewer, not a provider transport, action
audit, response collector, isolation boundary or model evaluation. No direct or
viewer condition becomes qualified through rendering. The original frozen-program
executor and complete submission/scoring interface are unchanged.

`test_view_source.py` uses generated arrays only. It checks all 61 display positions,
exact trial/cell selection, split indexing, public-only reads, invalid selections,
nonfinite and malformed archives, bounded NPY geometry, constant/extreme finite
display scaling, dependency identity, and exclusive CLI output. These controls do
not establish authentic-input compatibility, biological completeness or neural
understanding. Required MAT parts, complete native registration/clock evidence,
participant transport and empirical evaluation remain unresolved.
