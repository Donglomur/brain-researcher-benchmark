# Figure 3 recovery and reproduction outputs

This component computes the source Figure 3e/f curves on the complete six-condition,
30-dataset-per-condition panel. It also reports candidate versus author reproduction
discrepancies and separate paired recovery diagnostics. It does not fit a model,
generate simulations, read pickle artifacts, or authenticate an author baseline.
No authentic panel or candidate run has been evaluated here.

The newly inspected figure notebook resolves an important ambiguity in the current
contract: its curves are **signed estimation error**, not raw estimates or absolute
error. At each trial count, cell 6 concatenates area 1 and area 2 errors from all
30 datasets and computes their mean and NumPy default standard deviation (`ddof=0`).
Thus each plotted summary uses 60 area values from 30 independent datasets. Averaging
the two areas before taking the standard deviation changes the published curve.
The pCCA comparator is present only for the across-area endpoints; there is no
source within-area pCCA curve in cells 7–8.

The trial counts are `100, 150, 300, 600, 1000, 1500`. The original driver iterates
draw first, then trial count, for 180 datasets. Its five-fold, no-warmstart,
dimension-candidate `0..14` policy still conflicts with the paper's `1..10`
simulation dimension description. The source CV seed is not evidence of a frozen
simulation RNG state. These fitting questions remain open; the scorer does not
select a convenient alternative protocol.

`metrics.py` independently calculates per-area percentage shared variance and
95%-shared dimensionality for a 30-neuron pCCA-FA parameter export. It averages
each neuron's variance fraction, rather than taking a ratio of summed variances.
It uses the source threshold `0.95 - 1e-9` and handles zero selected dimensions.
The helper accepts up to 30 loading coordinates, so candidate methods are not
forced to use the author's disputed dimension grid. The pCCA control's native
parameter-to-metric conversion is still an operator responsibility; this component
accepts its two across-area metric outputs and never invents within-area ones.

## Interface

Use Python 3.11 or later on POSIX; no third-party packages are required:

```sh
python3 -I -B evaluate.py /operator/support.json /operator/submission.json > report.json
python3 -I -B test_evaluate.py
```

The programme's `compare(support_bytes, candidate_bytes)` interface accepts strict,
bounded UTF-8 JSON. The CLI refuses symlink inputs and nonregular files. Both
documents retain all 180 rows in original draw-major order. `draw` is the source
loop index `0..29`, and `trials` is the trial-count value. An operator must map
these identities from authenticated source execution, not infer them from a
candidate's ordering. Each row binds the exact prepared observation file by SHA256.

Support has exactly:

```text
schema: "pcca-fig3-support-v1"
task: "paper-pcca-fa-bilateral-pfc-arousal-2026"
preparation_sha256: independently reviewed preparation receipt digest
protocol_sha256: frozen scientific protocol digest
rows: [{trials, draw, observations_sha256, truth, author, pcca}, ...]
```

`truth` and `author` contain `across_1`, `across_2`, `within_1`, `within_2`.
Each component has `psv_percent` (0–100 percentage points) and `dshared`
(integer 0–30). `pcca` contains only the two `across_*` components. Zero
shared dimension requires zero shared variance. Across plus within variance
cannot exceed 100 percent for either area. Author and pCCA values must come from
authenticated matched fits; syntactic acceptance is not proof of that lineage.

Submission has exactly:

```text
schema: "pcca-fig3-submission-v1"
task: "paper-pcca-fa-bilateral-pfc-arousal-2026"
support_sha256: digest of exact support JSON bytes
condition: "paper_data" or "paper_data_author_code"
rows: [{trials, draw, observations_sha256, estimates}, ...]
```

`estimates` has the same four-component layout as `truth`. The two access
conditions use identical observations, targets and scoring. The report retains
the condition; this scorer does not enforce delivery or code-access separation.
No participant transport is supplied. The support and its truth/author/control
values are operator-owned. Participants should receive observations, ordered
identities, the support digest and the permitted source material; they must not
receive the support document. No values are hardcoded as candidate targets.

`pccafa_metrics(parameters)` accepts exactly `W1`, `W2`, `L1`, `L2`, `psi1`,
`psi2`. Loading matrices have 30 rows; `W1` and `W2` have matching column counts.
`psi1` and `psi2` are length-30 independent-variance vectors. It returns the
four-component endpoint layout. It does not execute source fitting code.

## Outputs and qualification

`source_curves` reproduces the signed-error mean and population SD in each of the
24 combinations of trial count, across/within component and endpoint. `%sv`
errors are percentage points; dimensionality errors are dimensions. The source
pCCA comparator accompanies the 12 across-area combinations. All area-specific
errors are preserved in `per_draw`.

`reproduction_discrepancies` keeps candidate-minus-author values separately from
recovery against ground truth. Reproduction is a first-class intended outcome,
but an admitted tolerance and matched author baseline are still missing.

`improvement_diagnostics` reports, for each dataset, the mean of its two areas'
absolute errors for the candidate minus the equivalent author quantity. These
are explicit benchmark-owned diagnostics, not a source-paper loss or confidence
interval. A reduction in signed bias alone does not imply better recovery; equal
positive and negative errors can cancel. No pooling across units or trial counts,
winner threshold, confidence statement, current-SOTA claim or successful method
comparison is added. Both `reproduction_pass` and `improvement_pass` remain null.

Remaining work: resolve source-release and fitting-policy bindings; prepare the
original or approved protocol-equivalent complete panel; authenticate pCCA-FA and
pCCA fits and numeric outputs; freeze reproduction tolerances and a scientifically
justified improvement decision; supply paired participant delivery. The existing
historical covariance/pupil component is preserved and does not substitute for
this simulation endpoint. Supplementary Figure 4 remains a separate route.

## Source and controls

[SOURCE.json](SOURCE.json) pins the verified figure and driver Git blobs, the
model arithmetic source, and the precise release-association limitation. The
notebook has no cached outputs. Raw source files, response receipts and private
work paths remain outside Git. Two raw-host fetches failed before response bytes;
the actual release-tree API returned a retained rate-limit response. No bypass or
scientific execution followed.

The generated controls verify signed errors, 60-area population SD, the 30-dataset
unit, separate trial conditions, the pCCA across-only control, neuron-normalized
fractions, rotation-invariant dimensionality and its exact numerical boundary,
complete paired identities, byte bindings, invalid numerical inputs and file
admission. They contain no source observations or fitted results and establish
software behavior only.
