# MATLAB7.3 locked-input admission v2

This additive successor enables the separately named RADICaL representation under
the [v2 processed-input source condition](../train-only-decoding-v2/README.md).
The reviewed predecessor at commit
`e004272bb6599882a5e2f97d885cf77b2e257d0f` remains byte-for-byte unchanged in
`../locked-mat-admission-v1/`. Its +900 blanket admission refusal is historical.

The adapter still verifies all ten original source identities and the complete
raw eligibility census, exact original trial-number order, both lock masks,
source config, 101-row grid, all supplied locked ROI columns with raw ROI-lag
metadata consistency, and ordered 24 joints. It
selects the same 51 rows without resampling. RADICaL additionally requires the raw
inspection report to establish original `trialNumber` equals one-based `R`
positions, because the author helper uses `R(trialNumber)`. It never renumbers
trials to satisfy this condition. All existing bounded HDF5, filesystem, ordinary
file, hash, resource and private-output checks are retained.

`normalize-locked` accepts `calcium_locked_mat73_manifest_v2`. The v1 manifest's
ambiguous `upstream_temporal_support_ms` is removed, not rewritten to 800. Every
session entry must instead supply `source_condition` using the v2 builder and
bind its canonical SHA256 in `provenance.upstream_exposure_sha256`. These records
and hashes propagate to both normalized dataset and frozen protocol. Their
schema versions and the normalization result are v2. Source exposure facts and
unknowns are checked, including the distinction between direct RADICaL rate
selection and the separate SD35-smoothed-events condition. The actual source
configuration still contains `smoothSD=35`; that field does not prove RADICaL
rates were Gaussian-smoothed.

`inspect-raw` remains the identical scalar-metadata operation: its raw manifest
and report schema remain v1, as do reach-context records and split mathematics.
The reader reuses the exact immutable v1 `PRIMARY_ASSETS.json` pin. See the
[v1 reader reference](../locked-mat-admission-v1/README.md) for unchanged raw
manifest fields, private file layout, HDF5/JSON limits and CLI arguments. Its
historical normalization/upstream-support semantics are superseded only by this
v2 package. No runtime dependency installation is performed; the reader requires
Python3.11+, NumPy and h5py.

Example source record construction (operator-local Python, not a scientific run):

```python
record = p.source_condition.build_source_condition("radical")
entry["source_condition"] = record
entry["provenance"]["upstream_exposure_sha256"] = p.digest(record)
```

The record is evidence of the known/unknown source condition, not an invented
receipt for true raw-to-locked exposure. Only declared unknown actual raw/model
support and fitted-trial exposure are supported; fabricated full bounds, upstream
fold-safety, online status or parity claims are refused even when rehashed.

No authentic neural/kinematic arrays have been processed by this revision; no
model fit or scientific score is established. The captured release contains ten
original imaging assets totaling 12,707,357,935 bytes and no locked export within
that inspected inventory. One original 520-byte header proves MATLAB7.3 for that
asset; it does not establish locked-export format. Authentic unsupported formats
still require a justified reader extension or original source preparation.
Missing native kinematics helper, real clock/ROI/array correspondence, actual
upstream exposure and authentic execution remain explicit gaps. The source
condition correction alone promotes no benchmark to ready or qualified.

Run only the focused new construction controls with `python3 -B
test_source_condition.py` from this directory in an existing NumPy/h5py runtime.
Generated fixture files are software controls, not benchmark data. The descriptor
and independent review bind the exact source cutoff and observed test count.
