# Resting-state component association: a circular-shift method case

Analyze the released ADHD-200 recording for participant **`0010064`**. Estimate
the signed association between the MSDL components **`R DMN`** and **`Cereb`**
and its rank among circular phase re-pairings. This is a single-recording method
application, not a replication of xDF or a population cerebellar-network finding.
Either significance verdict, or an explicitly unsupported result, can be correct.

## Inputs and public contract

Original inputs are available offline under `/app/data/restconn`. Read
`/app/SOURCE_NOTICE.md`, `/app/source_manifest.json`, `/app/method_contract.json`
and `/app/output_schema.json` before analysis. The manifest fixes source bytes;
the method and schema specify the measurement, precision and required evidence.
Do not fetch another participant, replace sources or infer missing frames.

Fit all **39 overlapping MSDL maps simultaneously**, then select the named pair.
These timecourses are map coefficients, not simple ROI averages. Preserve every
original frame, the exact selected nuisance columns and the declared order of
detrending, filtering, nuisance regression and standardization. Keep raw header
timing/scaling separate from the operational analysis clock. Affine resampling
does not by itself establish a verified nonlinear template registration.

For the accepted cleaned pair `x = R DMN`, `y = Cereb`, calculate signed Pearson
correlation and enumerate **every offset `k = 1, ..., N-1`** of `roll(x, k)`
against unchanged `y`. Retain repeated values at different offsets. The public
two-sided rank is `(1 + count(abs(r_k) >= abs(r_0))) / N`, with strict
`p < 0.05`. Use the contract's accurately summed comparison before rounding;
do not decide ties from rounded reported correlations. The source-defined
pre-standardization activity check determines whether this inference is supported.
An inactive component requires explicit null inference, not invented `p = 1`.

## Deliverables

Write these five files to `/app/output`:

- `raw_map_coefficients.npz`: keyed full-39-map extraction receipts.
- `timeseries.csv`: every original frame and both cleaned component series.
- `connectivity.json`: signed correlation, complete keyed circular null,
  exceedance flags/count, exact numerator/denominator, status and verdict.
- `run_metadata.json`: source and contract identities, original geometry/clock,
  map/nuisance ranks, selected/excluded columns and component-support diagnostics.
- `findings.md`: a concise interpretation and limitations in your own words.

The schema defines fields and bounds. Coherent keyed ordering changes and harmless
extra fields are allowed. Findings are not graded by keywords. A reserved
`failure_report.json` denotes an unsuccessful run, not a valid completed output.
Use a fresh destination; do not overwrite previous evidence.

## Interpretation

Exhaustive circular shifts remove Monte Carlo variability, not uncertainty about
the null model. Circular wraparound and temporal structure can invalidate nominal
type-I-error calibration; stationarity alone is not a universal guarantee.
Report what this specified circular-rank calculation says about this recording,
without treating rejection as neural/causal coupling or non-rejection as absence
of coupling. Optional alternative analyses must be clearly separate and cannot
replace the required circular-rank record.

Background: [Afyouni, Smith and Nichols (2019)](https://doi.org/10.1016/j.neuroimage.2019.05.011)
develop xDF, a different method; [Yuan and Shou (2024)](https://doi.org/10.1371/journal.pbio.3002758)
discuss limitations of cyclic permutations and introduce a different test. This
task does not implement or reproduce either paper's primary method/result.

Scoring is binary: all source, completeness and arithmetic checks must pass for
reward 1.0. There is no proportional-scoring promise or required outcome band.
