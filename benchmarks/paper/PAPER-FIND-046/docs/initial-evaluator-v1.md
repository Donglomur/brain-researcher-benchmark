# Figure 2 contrast and cross-archive construction component

`implementations/initial-evaluator-v1/evaluator.py` computes the numerical
Figure 2h stage contrast and Figure 2i serum-session response from an explicit
export of the author’s aligned CPIn structures. It also produces the rat/day
map needed to inspect Figure 1 serum, Figure 2 photometry and Figure 3 source
relationships. This is a useful initial computational component, **not a
complete or scientifically qualified PAPER-FIND-046 benchmark**. The canonical
task and its historical state are unchanged.

The canonical contract SHA256 is
`35e8e70519700bb6b0a94468a19e179aa6ac06fe2f3c374299c938752243fe7f`.
The source revision is
`constantinoplelab/published@b7b68ca8c107d8ce4a061e16da214307f175c3e5`.
The package’s `sources.json` pins the inspected primary code, paper snapshot,
license and contract-to-implementation mapping. No dataset is bundled.

## Implemented scientific operations

The [pinned Figure 2 processor](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/ProcessData_Figure2.m)
loads both Figure 2 and Figure 1. Its stage helper selects Proestrus then
Diestrus, high block 2 versus low block 3, and `PrevTrialType != 2`. The
processor passes `thirdrew_arg=0`, so the implementation does not restrict
reward amounts. For each rat/stage/block it removes the leading CPIn matrix
column, averages trials at each sample with missing-value omission, and
subtracts the minimum of that mean trace over the inclusive nearest-sample
baseline interval −0.05 to 0 seconds. It integrates the inclusive nearest
0 to 0.5 second samples by the trapezoid rule. Time is exactly the source’s
`linspace(-5,10,width-1)`, rather than an independently interpolated clock.
The reported rat effect is `(high−low)_Proestrus − (high−low)_Diestrus`.
Each block includes counts, trial identities, baseline and effective time
indices. A mean across rats is emitted only when every declared regular rat
has a computable contrast. This mean is an added audit diagnostic; the source
uses paired signed-rank inference, which this component does not implement.

The [serum helper](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/photometry/SerumEstradiol_vs_DARPE.m)
uses a separate full roster from `fields(BstructSerum)`. It divides each
rat’s entire CPIn matrix by the maximum of the mixed-block mean response
(`Block==1`, `PrevTrialType!=2`). **The leading matrix column participates in
that normalization**, as in the executable source. It is removed only for
the time-series calculations. All serum matrices must match the source’s
G127 width, which defines their common time axis. Session AUC uses the same
mean/minimum-baseline/trapezoid operations, without restricting to Proestrus
or Diestrus and without a reward-amount filter. Joins are exact rat and
calendar date. G138 dates 20240627, 20240701 and 20240709 are retained in the
ledger with the source’s low-SNR exclusion reason.

Every photometry session remains in the output, including absent serum
matches, source exclusions and missing-AUC sessions. Unmatched serum rows
also remain visible. The source-shaped `delta_good`, `E2_good` and `stages`
arrays exclude only sessions with missing delta AUC; missing hormone values
are retained. The scalar descriptive Pearson correlation follows
[`PlotFigure2.m`’s `corrcoef`](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/vis/PlotFigure2.m):
any missing value, fewer than two pairs or a constant vector makes it
undefined. No correlation p-value or independence claim is produced.

The [paper](https://www.nature.com/articles/s41593-025-02104-z) reports nine
regular photometry rats, and five rats/41 sessions for the plotted serum
panel. These are published reference counts, **not observed archive
inventories**. In particular, five is not a permitted filter on the raw
serum roster. The Figure 3 source explicitly lists G008, G016, G021, G022,
G024, G036, G037, G051 and G127. The cross-archive audit retains that list,
requires acknowledgement of supplied `BestFits`, and reports all observed
rat/day relationships without selecting an intersection cohort. It cannot
identify a smallest complete empirical cohort without the native records.

## Explicit input interface

The standalone CLI uses Python 3.10+ standard libraries only:

```sh
python3 benchmarks/paper/PAPER-FIND-046/implementations/initial-evaluator-v1/evaluator.py export.json --output report.json
```

Input is a JSON object with these fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `input_kind` | `generated_engineering_control` or `authorized_native_export`; the latter is a declaration, not verified acquisition permission or admission |
| `figure2_ratlist` | Complete ordered exported `NAcc_ratlist` |
| `figure2_serum_ratlist` | Complete ordered `fieldnames(BstructSerum)`; distinct from the regular roster |
| `figure2` | Rat-keyed objects with `cpin` and `behavior` arrays, from regular `Pstruct/Bstruct` |
| `figure2_serum` | Same shape, from `PstructSerum/BstructSerum` |
| `serum_table` | All exported serum rows with `rat`, `session_date`, `estradiol_conc` |
| `figure3_manifest` | Exact ordered nine-rat `ratlist`, `best_fits_supplied: true`, and a `sessions` array of `rat`/`unique_day` records; an empty array declares an unknown inventory |

Each `cpin` row includes the original leading column followed by the signal
samples; do not discard or relabel its numerical values. Each corresponding
behavior row has `trial_id` (explicit nonempty string), `unique_day`
(`YYYYMMDD`), `block` (1/2/3), `prev_trial_type` (integer) and `stage` (one
nonempty string). The exporter must preserve native row order and identity;
the component cannot prove that association from an untrusted declaration.
Rat/day/trial identities must be unique. `session_date` accepts `YYYYMMDD`
or `YYYY-MM-DD`. Signal/hormone missing values use JSON `null`, never NaN or
Infinity. Matrix and behavior row counts must agree. No acquisition,
resampling, motion correction, MATLAB reader, behavioral fitting or model
execution occurs here. The native transformation and the metadata column’s
identity must still be independently verified before empirical admission.

The source code assumes an unambiguous serum join and scalar stage output.
This package adopts an explicit **prospective fail-closed ambiguity policy**:
reject duplicate JSON keys, duplicate serum rat/day rows, multiple stage
labels within any serum-matched day (including a low-SNR excluded day),
missing G127, inconsistent serum widths, zero/undefined normalizers and
degenerate time grids. It does not silently select a sample, average serum
replicates, collapse labels or repair a clock. Missing signal samples are
omitted when forming per-sample means; an integration interval still
containing a missing sample has undefined AUC. These policies are
construction choices, not retrospective evidence about the source payloads.

One additional prospective export policy is explicit in every result:
averaging always follows the declared trial axis, even for a singleton trial
group. MATLAB's unqualified `mean(matrix,'omitnan')` switches its default
dimension for a single row, potentially yielding a scalar or an indexing
failure in these helpers. The adapter does not reproduce that degenerate
dimension behavior. The source-equivalence analytic controls duplicate
identical trials so every selected group is multirow; a separate control
tests the disclosed singleton policy. Every affected rat/stage/block,
serum day/block and mixed normalization selection is listed explicitly in
`singleton_selections_affected_by_export_policy`, alongside its existing
trial counts. Native singleton behavior and actual
group sizes remain part of the unverified MATLAB/export parity gate.

## Verification and limits

Run the generated control suite with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-046/implementations/initial-evaluator-v1/tests -v
```

Independent source/reference derivation supplies the analytic expectations:
the mean-before-minimum baseline control gives Proestrus high AUC 1.9, low
AUC 0.475 and a rat stage effect 0.95; serum normalization including a 100
metadata value gives delta 0.01425; a coarse nearest-sample grid gives AUC
0.18. An independently reviewed endpoint control gives serum delta 0.0475,
exposing both metadata-column and integration-endpoint mistakes. Additional
tests exercise missing values, exclusions, duplicate identities, unmatched
specimens, absent stage blocks, exact Figure 3 population, BestFits retention,
Pearson missingness and the real CLI. Generated controls establish engineering
behavior only; they are not scientific observations or a measured native
resource envelope.

The full canonical scope remains open. Figure 3 RPE encoding/history
computations, supplied fit provenance, exact empirical populations, raw
archive checksums, native MATLAB parity, numerical reference tolerances,
protected references, matched access-arm resources and grouped improvement
assessment remain gates. Figure 3 reward-history comments and executable
masks differ, and its source AUC/lag indexing differs from Figure 2; those
endpoints require their own explicit source audit rather than reuse of this
component. Stage is observational, and these associations do not establish
an intervention effect. No scientific run, binary reward, reproduction
qualification, baseline competence or whole-paper result is claimed.

Archive data terms remain the contract’s CC BY 4.0 record, separately from
the inspected MIT code license reproduced in the package. Public access
does not establish model non-exposure, blinded evaluation or permission for
unbounded acquisition. Historical asset checksums remain source-reported,
not newly verified content hashes.
