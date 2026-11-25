# NEURAL-050 numerical clock repair

This version fixes a numerical defect in the existing bounded-array preparation
path. The original [v1 evaluator](../initial-evaluator-v1/evaluator.py) remains
unchanged. This is an operator analysis component; it does not deliver a
participant episode or establish direct neural interpretation.

At nominal 500 Hz, a two-second window has FFT bins at 0.5 Hz intervals. The
registered half-open gamma band must include bin 160 (80 Hz) and exclude bin 200
(100 Hz). In v1, rate estimation from the first timestamp difference can round
500 Hz downward when a constant offset is added to otherwise identical clocks.
Comparing floating-point frequencies directly then drops bin 160 and includes
bin 200. A generated mixed edge-tone control preserves this predecessor failure.

The corrected preparation estimates rate from the full observed clock span. It
selects bins in integer coordinates and snaps an edge coordinate to its nearest
integer only within a propagated binary64 representation/arithmetic bound. The
bound comes from the timestamp magnitude and clock span; it is not the looser
regularity tolerance. Genuine frequency differences outside that bound retain
their classification. The code never rounds the source rate to an advertised
500 Hz or resets stream timestamps. It rejects a numerically unresolvable edge
when its bound reaches a quarter of a bin.

The Hann taper still spreads an edge tone into adjacent bins. Excluding the
100 Hz *center bin* does not claim that an exactly 100 Hz sinusoid contributes
zero total in-band power. Tests use the independent 160:200 integer-bin
periodogram oracle, including this expected leakage.

Each source pin records the inferred rate, selected bin interval, raw edge
coordinates, tolerances and snap decisions. Prepared features identify this
implementation; reports separately identify feature preparation and evaluation.
Evaluating a legacy packet does not relabel its preparation as corrected. A
caller must reprepare original qualified arrays to repair existing features.

The [v1 input contract and scientific limitations](../../docs/initial-evaluator-v1.md)
continue to apply. The prospective protocol, same-window source-pixel wrist
speed, channel selection, QC, patient/day splits, ridge comparators, MSE/R²
aggregation, matching and shift diagnostic are unchanged. Canonical task and
understanding files are preserved. Python 3.10+ and the existing NumPy dependency
are required; tests also use the existing pytest dependency.

```sh
python3 evaluator.py prepare raw-manifest.json feature-packet.json
python3 evaluator.py evaluate feature-packet.json report.json
python3 evaluator.py evaluate feature-packet.json report-within.json --mode within_patient_days
```

During the parallel revision, generated tests must run through the shared
reviewed test pool. The suite checks full preparation at both spectral edges
and five clock offsets, genuine rate differences, noninteger sample rates,
clock/grid rejection, CLI preparation, and equality of all scientific report
values with v1 on the same generated feature packet in both split modes.

The verified shared-pool run passed 39 generated tests: 15 new controls and 24
unchanged predecessor tests. The preserved counterexample confirms the original
edge-selection failure and corrected integer-bin power. These checks establish
software behavior only. One earlier invocation stopped before testing because
its runtime lacked pytest; the successful run used the existing interpreter
from the predecessor review without installing dependencies.

Source evidence is reused from the pinned [AJILE12 notebook](https://github.com/BruntonUWBio/ajile12-nwb-data/blob/f44ca6f6c51251b62b6f47492bba400472d4a7ba/Example_AJILE12_exploratory_analysis.ipynb)
and [DANDI release metadata](https://api.dandiarchive.org/api/dandisets/000055/versions/0.220127.0436/).
The notebook illustrates 80–100 Hz processing and reads source sample rates;
the current periodogram estimator remains explicitly prospective, not a
reproduction of the notebook's filtering and differentiated log amplitude.
Exact reused byte hashes are in [provenance.json](provenance.json).

No authentic NWB payload was read or prepared and no model was run in this
repair. Source clock calibration, bounded NWB conversion, motor anatomy/wrist
laterality, source QC and pose geometry, full cohort coverage, protected
participant delivery, and authentic reference qualification remain unresolved.
The roundoff bound is not evidence of source synchronization accuracy.

## Raw payload identity during preparation

The preparer now captures each bounded exported NPZ once, verifies its SHA-256,
and decodes that same immutable byte snapshot. Previously, hashing the path and
then reopening it allowed a replacement file to supply features under the first
file's recorded hash. Replacement after capture no longer changes the decoded
observations; a mismatched captured payload is rejected before decoding.

This retains one complete compressed NPZ in memory while its arrays materialize,
in addition to the decoded arrays. The snapshot is released before clock and
feature processing. Provision bounded exports with this additional memory cost;
this change does not make an arbitrarily large archive admissible.

The generated replacement regression retains a predecessor counterexample,
checks the revised path against analytic gamma power and wrist speed, and checks
rejection before decoder entry when captured bytes fail the expected hash. The
historical 39-control receipt in `provenance.json` remains evidence for its prior
revision. Neither the identity repair nor generated checks qualify authentic
source exports or participant performance.

## Constant targets and units

The scorer now marks a target constant only when all observed values are equal.
The former absolute variance cutoff (`1e-15` pixels²/second²) could erase a
defined delta-R² after a change of movement scale. Nonconstant, representable
variances retain their normalized increment. If the variance intermediate
underflows or overflows, a narrow exact-arithmetic fallback on the observed
binary64 operands retains any representable normalized increment. MSE values
below binary64 range may round to zero, while the ratio is formed before that
rounding. Nonfinite reported final values are refused explicitly. Ordinary
variance arithmetic, folds, patient/day weighting and true constant-target
handling are unchanged. Generated controls cover the public independent scorer
and complete evaluator; they do not qualify authentic data or participant results.
