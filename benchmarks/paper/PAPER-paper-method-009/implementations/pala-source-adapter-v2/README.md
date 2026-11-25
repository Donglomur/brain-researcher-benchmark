# Pala voltage source adapter

This adapter corrects the source voltage unit boundary for the original Pala
recording. The deposited `PalaPetersen_Analysis.m` thresholds at **−0.03 volts**
(line 150), and multiplies voltage mean and standard deviation by **1000** to
report millivolts (lines 146–147). `initial-evaluator-v1.decode_pala` instead
labels the unconverted source values as `voltage_mv`. Consequently a resting
source voltage of −0.060 V is interpreted as −0.060 mV and its spike detector
refuses the trace as starting above its −30 mV threshold.

`source_adapter.load_pala` authenticates the original `data.mat` against its
recorded MD5, decodes its expected MATLAB fields, and converts each voltage
sample from V to mV exactly once. File identity, size and modification metadata
are checked across authentication and decoding so a changed file cannot retain
an earlier checksum receipt. This is a mutation check, not a hostile-host sandbox.
There is no unit guessing, resampling, row
sorting, concatenation, trial exclusion, cohort selection, or spline fit. Stable
one-based source row IDs, mouse/cell identities, trial types, 20 kHz sampling,
individual trace lengths, and trial boundaries are retained. The returned
voltage arrays are copies and read-only; source arrays remain unchanged.

```python
# Import this directory's source_adapter.py in the operator's approved runtime.
from source_adapter import load_pala

recording = load_pala(approved_data_mat)
trials_with_millivolts = recording.trials
source_receipt = recording.receipt
```

The trial objects satisfy the existing evaluator's field interface. Any use of
that evaluator still follows its explicitly prospective held-trial recipe; this
adapter does not convert it into a native Figure 3 evaluation. The predecessor
loader remains preserved as historical source, and should not ingest the
deposited volts. The low-level `decode_pala_volts` accepts source-format dicts
for adapter controls; it assumes volts and does not authenticate arbitrary
caller-supplied data. Production source access uses `load_pala`, which has no
checksum-bypass argument.

The original source payload has **not** been acquired or decoded by this change.
The actual MAT schema, memory requirement, and v7.3 compatibility remain
unqualified. The source helper supplies the unit evidence; generated MATLAB
round-trips check the implemented expected schema. The source loader reports
both source hashes, byte count, units, multiplier, and preserved row count
without embedding a local path. It does not download anything.

The original eight-neuron/five-mouse cohort identities, twenty-segment mapping,
25/50 ms voltage-bin conflict, voltage-spline policy, native estimator settings,
and exact definition of the reported 23% discrepancy remain unresolved. No
empirical preparation, author calibration, fitted model, candidate comparison,
paper win, or benchmark qualification is claimed.

Generated controls cover source-scale threshold crossings, the predecessor's
unit failure, interpolation after conversion, row/column MATLAB round-trips,
source identities and ordering, 20 kHz timing, a ten-trial 20 Hz inclusion
boundary, source immutability, invalid samples and shapes, and checksum failure
before parsing. Run the test file through the shared bounded test pool during
parallel construction. The source and predecessor pins are in `provenance.json`.
