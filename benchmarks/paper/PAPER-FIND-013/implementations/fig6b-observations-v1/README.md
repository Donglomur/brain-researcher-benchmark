# Original Fig. 6b observation support and R² vector

This component prepares the original processed CA trajectories and scores three
complete sets of supplied fitted values. It retains the original reconstruction
task: all observations used for fitting are available for scoring. It introduces
no held-out split, interpolation target, selected-field subset, or scalar paper
win. The registered historical OLS runtime remains unchanged.

The source metadata identify **2,657 source fields, of which 2,649 enter `Tok`**.
The eight short fields remain in the export with an exclusion reason. The panel
is not 2,649 arbitrary source rows. Counts in CA1 familiar/novel and CA3
familiar/novel are respectively 1,072/1,168/179/238 before eligibility and
1,068/1,167/179/235 afterwards. All 92 condition-plane entries, including four
empty planes, and the 11 source-assigned animal labels are retained.

`observations.py prepare` authenticates both original public MAT file SHA-256
digests, reads their native MATLAB struct order, preserves the source positional
animal assignments, and emits every original field identity. It exports only
COM/onset observations and their support, excluding the source `PFs` variable.
The exported animal labels reproduce author assignments; they do not independently
authenticate biological identities or identify paired neurons across conditions.

For each row, conversion is `6*COM - 6*COM_at_onset`, from onset through the final
source column. The export retains missing positions, the original source laps,
the observed displacement vector, and two distinct predictor clocks:

- `observed_laps_since_onset1` preserves raw lap gaps for the linear fit.
- `literal_nonlinear_clock0` is `0..n_observed-1`, exactly the clock constructed
  **after** NaN deletion by both inspected author scripts. It compresses missing
  interior gaps. It must not be presented as the original physical lap clock.

Eligibility is the interior filled span of at least 15 laps, independently of
fit results. Missing response values are never interpolated into the regression
target, trailing gaps do not extend that span, and observed response vectors are
not truncated to the first 15 laps. Saved source metadata report 43 eligible
fields with fewer than 15 actual observations and 2,647 eligible fields with
post-onset segments longer than 15 laps; either shortcut would change the task.

## Source conflicts that remain material

At the pinned repository revision, `CanDataAnalysis.m` actively fits a
**two-parameter** plateau exponential, with the offset fixed at zero. Its
three-parameter code is commented out. The inspected
`CanDataAnalysis_LinRegBootstrapStats.m` actively fits the paper's
**three-parameter** form with offset bounds ±25 cm. Both use sign-dependent
amplitude bounds and starting values, and both compress the nonlinear clock.
The main script's plotting section includes both the raw `Tok.RCreg_R2` and a
copy clipped below at zero; the signed-rank call uses the clipped copy.

These are concrete source discrepancies, not an instruction to select the
better-performing version. This component exports the evidence needed to audit
them, without deciding which released branch produced the final Fig. 6b vector.
The current contract still requires that result-producing source linkage. The
uninspected `CanDataAnalysis_NonLinRegBootstrapStats.m` is mapped by the README
to Fig. 6f–g and S19b; it has not been acquired for this component.

The scorer uses `1-SSE/SST` on the observed response vector, with no clipping,
adjustment, averaging across fields, significance test, or fabricated R² for a
constant response. Constant rows retain SSE/SST and a null R². Supplied fitted
values must cover every observed value of every one of the 2,649 included PFs
in each arm; missing, extra or duplicate IDs cannot produce a smaller score.
The result contains full paired per-field values and candidate-minus-plateau
differences, with group and animal identities. The fixed 2649 denominator is
never reduced because a fit is poor or an R² is undefined.

## Operator interface

Authentic preparation requires a separately coordinated native protocol; it has
**not** been run in this build. It uses the existing NumPy/SciPy environment and
installs nothing. The source SHA checks precede numerical imports and MAT parsing. Both original
MAT files are captured once with their pinned byte lengths, and `loadmat` parses
those authenticated bytes through a file-like stream. This retains about
5.55 MB of source byte bodies, in addition to parsed arrays; it does not reopen
mutable paths after checking their identity.

```sh
python3 observations.py prepare --ca1 /EXTERNAL/CA1_COM_withPFs.mat \
  --ca3 /EXTERNAL/CA3_COM_withPFs.mat --output /EXTERNAL/fresh-observations.json
```

Freeze that output's SHA-256 externally. Predictions are a JSON object with
exactly `linear`, `plateau`, and `candidate`, each mapping every included `id` to
its fitted-value list in observed-response order. There is no parameter fitting
in the scorer and the arm names do not authenticate an author run.

```sh
python3 observations.py score --observations /EXTERNAL/fresh-observations.json \
  --expected-observations-sha256 OPERATOR_FROZEN_SHA256 \
  --predictions /EXTERNAL/fitted-values.json --output /EXTERNAL/fresh-scores.json
```

The operator must supply the frozen digest independently of a participant; this
local utility is not an isolated participant runner. Source authenticity comes
from the pinned input files and the separately frozen preparation receipt, not
from a self-declared digest inside a candidate file. Outputs must be fresh files. The scorer authenticates and decodes the same
immutable observation bytes, so replacing the pathname between authentication
and parsing cannot change the scored observations.

## Qualification

This is an observation-preparation and R²-evaluation component. Generated
controls exercise clock gaps, span eligibility, full support, invalid values,
negative/constant R², exact panel coverage and source identity admission. They
do not qualify the unexecuted native MAT adapter or reproduce the final paper.
All 11 generated controls passed in shared-pool run
`paper01-find013-controls03` (0.492252 child CPU seconds; 39,763,968-byte peak
child RSS). Two earlier requests were busy and launched no test process.
No authentic preparation, author numerical inference, candidate trial, private
target inspection, new acquisition, or scientific improvement occurred here.

Remaining work is exact result-producing branch and original fitted-vector
recovery; an approved authentic preparation and independent readback; native
author calibration including fitting defaults/stopping; and a frozen comparable
capacity/search policy, panel aggregation, meaningful effect and animal-aware
uncertainty. No current-SOTA claim is made. Source pins and exact inspected line
ranges are in `source_evidence.json`.

The byte-snapshot correction is covered by generated path-replacement controls
for JSON scoring and both MAT inputs, plus refusal before numerical imports for
an incorrect second input. The MAT checks use runtime doubles, not scientific
arrays, and do not qualify native MAT parsing. SciPy's documented
[`loadmat` file-like input](https://docs.scipy.org/doc/scipy/reference/generated/scipy.io.loadmat.html)
is used without changing its existing parsing options.
