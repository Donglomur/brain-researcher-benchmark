# Figure 3k reward-history regression inputs

This component constructs the original nine rats' response and predictor
matrices for `DARegressRewardHistory_estrous.m`. It fills a concrete gap in
the Figure 2 component: source-specific trial AUC, current reward and seven
reward lags, with a complete record of their rat/day/trial associations.
It does not run a regression or supply an improvement score. The registered
biological associations remain **ineligible for an ordered paper win**.

Python 3.10+ and the standard library suffice:

```sh
python3 prepare.py export.json --output inputs.json
python3 -m unittest discover -s tests -v
```

During coordinated construction, generated controls must run through the
shared test pool. The commands above describe the standalone interface.
No archive download, native MAT read, native preparation, parameter fitting,
dependency installation or model execution occurs in this component.

## Source and consequential behavior

The pinned [Figure 3 processor](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/ProcessData_Figure3.m)
calls the [reward-history helper](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/photometry/DARegressRewardHistory_estrous.m)
with `PstructCPIn`, `Bstruct`, AUC endpoints 0 and 0.5 seconds, seven prior
trials, stages Proestrus/Diestrus, and exactly G008, G016, G021, G022, G024,
G036, G037, G051, G127 in that order. Source hashes are in `sources.json`.
The existing MIT notice is retained at
[`../initial-evaluator-v1/SOURCE_LICENSE.txt`](../initial-evaluator-v1/SOURCE_LICENSE.txt).

The executable helper differs from its comments in three consequential ways.
This component preserves its executable choices, documenting the unresolved
prose discrepancy rather than choosing a new scientific analysis:

| Operation | Preserved source behavior |
| --- | --- |
| AUC | Define `T=linspace(-5,10,width-1)`, find nearest 0 and 0.5 indices, then sum **unstripped** `pstruct(:,i1:i2)` inclusively and multiply by `mean(diff(T))`. No baseline subtraction or trapezoid rule. |
| Reward lags | Within sorted dates, place rewards and AUC at `TrialNumber` in arrays padded through that day's maximum trial number. Concatenate days, take `log2(Reward)`, and shift the concatenated vector for current through lag 7. Lags can cross days. |
| Selection | Select stage membership only. The mixed-block and `TrialType~=2` predicates are commented out. High/low blocks and violation trials remain selected. A row bearing both requested stage labels belongs to both stages, as in the source membership predicate. |

All rows stay in the ledger. For each source stage, `X_without_intercept`
and `AUC` are the inputs intended for the source's `robustfit(X,AUC)` call.
An intercept is **not** inserted into X: native `robustfit` adds it. The
expected coefficient order is intercept, current reward, then lags 1–7.
The returned `complete_numeric_rows` flags describe missing inputs; they do
not filter the stage arrays or assert MATLAB's exact missing-value handling.
No ordinary least-squares surrogate or Python robust-fit approximation is
substituted. Missing signal inside the rectangular AUC window yields null;
missing samples outside the window do not affect that AUC.

The sparse implementation preserves the source's dense padded-vector
semantics while avoiding memory proportional to the largest trial number.
Every lag includes its originating day/trial identity. The ledger names
cross-session lags, missing padded positions, and rows that the commented
mixed/nonviolation filter would have excluded. These are diagnostics, not
new exclusions. Nothing is averaged across rats or sessions.

## Export interface and explicit validity boundary

The JSON input contains `schema_version: 1`, `input_kind` equal to
`generated_engineering_control` or `authorized_native_export`, the exact
ordered `ratlist` above, and `figure3_cpin` with exactly those nine rat keys.
Each rat has `cpin`, a rectangular numerical matrix **including the original
leading column**, and a same-length `behavior` list in its original row order.
Each behavior record has:

| Field | Native source correspondence |
| --- | --- |
| `unique_day` | `Bstruct.(rat).CPIn.UniqueDay`, canonical `YYYYMMDD` |
| `trial_number` | `TrialNumber`, a positive integer; identifies original padded position |
| `reward` | `Reward`, positive finite numerical value, used directly by `log2` |
| `stages` | Native `stage` cell membership, exported as an array of strings; empty or unclassified labels select neither requested stage but still supply reward history |
| `block` | `Block`, integer 1, 2 or 3, retained for the comment discrepancy audit |
| `trial_type` | `TrialType`, nonnegative integer, retained for the same audit |

Signals use null for missing samples. JSON NaN/Infinity and duplicate object
keys are rejected. A native-export declaration is not authenticated
provenance or evidence of acquisition authorization.

The source constructs predictor rows in sorted day/trial-number order but
applies stage masks in original `bdata` order. This component **requires
those orders to agree** and rejects duplicate day/trial identities. It never
silently reorders original rows or permits assignment-overwrite ambiguity.
Native evidence must establish this source assumption before calibration.

Null current rewards would cause the source to delete rows before applying
an unshortened behavior mask. Zero/negative rewards give nonfinite/complex
`log2` values. This real-valued preparation interface rejects such inputs
explicitly, including the affected row, instead of inventing a deletion or
fitting policy. This is a prospective validity boundary, not evidence that
the native source contains no such values. A width that cannot distinguish
the requested clock endpoints is also rejected. All native groups must pass
these checks; no rat or session is discarded to obtain an output.

Each rat must have at least seven padded trial positions across its sessions.
For shorter support, the source's final lag assignment tries to place seven
leading NaNs in a shorter column. The preparer rejects that mismatch. Exactly
seven positions is permitted by the construction, yielding an entirely
missing lag-seven column; this does not establish that `robustfit` can fit it.

## Verification and qualification

Generated controls derive the source index result independently: with a
302-column row containing 0 through 301, MATLAB columns 101–111 sum to 1155,
and the source response is `1155 * .05 = 57.75`. Removing the leading column,
using trapezoids, or subtracting a baseline changes that result. Distinct
reward powers of two give exact lag expectations, including day-boundary
transitions and missing trial-number positions. Additional controls check
stage-only selection, paired row identity, all nine rats, invalid reward
semantics, and the actual JSON CLI. These are software controls only.

Native archive content, export correspondence, original MATLAB `robustfit`
coefficients, missing-value and numerical parity, empirical reference
tolerances, and paper-level estimates remain unverified. No genuine data
preparation has occurred. This Figure 3k input component does not implement
the other Figure 3 RPE analyses, validate supplied `BestFits`, or replace the
existing Figure 2 contrasts and companion controls. It supplies no held-out
predictor, no new split, no significance-based reward, and no scientific
improvement result.
