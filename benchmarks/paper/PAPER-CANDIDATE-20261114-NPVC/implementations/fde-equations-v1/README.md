# NPvC Figure 2 likelihood component

This standalone standard-library component evaluates the source paper's Eqs. 2,
3 and 6 using **already fitted, held-out likelihood operands**. It supplies the
neural prediction mathematics absent from the historical signed-motif component.
It is not a fitted NPvC model or a complete Figure 2 benchmark.

The author NPvC joint density on the source's 200 activity coordinates is
integrated with `delta_r = (max - min) / 200`. Coordinates include both endpoints;
their spacing is `(max - min) / 199`. These are deliberately distinct. A stable
log-sum-exp computes the conditional density from the same joint model. The
observed-response density is supplied separately, so this component does not
invent the upstream interpolation method. The peak conditional grid density is
the NPvC saturated term, and the supplied unconditional marginal activity density
is its null term. The reported mode uses the first maximum and also records the
number of tied maxima; source tie-breaking has not been recovered.

The GLM has its own Poisson likelihood, predictor-free fitted mean, and saturated
mean equal to observed activity. It does not reuse the NPvC denominator. The
noninteger deconvolved activity magnitudes are retained; `lgamma(y + 1)` extends
the factorial term, which cancels from the likelihood differences. No rounding,
clipping, epsilon, pseudocount or variance-explained substitute is introduced.

For each supplied neuron/epoch, log-likelihood differences are summed over its
held-out observations before taking the FDE ratio. Foldwise diagnostics are also
returned. Negative values, values above one, and negative reference denominators
are preserved. A zero denominator gives `fde: null` with `denominator_state:
zero`, retaining the unit. Nonfinite operands and positive activity assigned a
zero Poisson mean cause explicit refusal rather than omission. This finite
likelihood domain must be checked on authentic source outputs before use.

## Operator interface

```sh
python3 -B fde.py --input /external/held-out-operands.json --output /external/fde-result.json
```

Input schema `npvc-fde-operands-v1` has a `units` array. Each unit supplies:

- `identity`: string `animal_id`, `session_id`, `neuron_id`, `projection`, and
  `epoch` (`sample`, `delay`, `test`, `turn`, or `reward`). These are source joins,
  not IDs inferred from release ordering.
- `activity_bounds`: the source session minimum and maximum in the original
  deconvolved-activity coordinate, shared with the supplied fitted densities.
- `observations`: rows containing string `trial_id` and `frame_id`, integer
  `fold_id` in 1–5, integer `trial_type` in 1–8, and nonnegative `activity`.
- Each row's `npvc` object contains `log_joint_grid` (200 ordered log densities),
  `log_joint_observed`, and `log_marginal_observed`. Its `glm` object contains
  `mean` and `null_mean`, in the same activity units as that observation.

`test_fde.py:fixture` is an explicitly generated small interface example. It is
not an eligible source session. Rows must come from a separately authenticated
source runner; this component cannot determine whether supplied fold IDs are
truthful or whether upstream fitting leaked targets. Duplicate unit identities
and duplicate trial/frame rows within a neuron/epoch are rejected. A fresh output
is required and the input digest is retained. Input size is bounded to 64 MiB;
the numerical functions may be called on individual units by a future streaming
runner without selecting a smaller scientific panel.

## Scientific boundary

The input may contain partial support, and the result explicitly reports that
scope. It does not authenticate the 59-session/ten-mouse paper cohort, invent
historical folds, require whole-trial rather than time-point folds, merge epochs,
average neurons or projections, or select a primary paper-win statistic. The
five epochs, eight trial types, fivefold protocol, original movement/task inputs
and session eligibility must be recovered and enforced by the preparation and
evaluation owner before any complete-panel claim.

The prior source audits found 64 released session archives plus six support
files, while the paper describes 59 sessions and 2,860 analyzed cells. Numeric
animal/session metadata do not establish filename or trace-row joins. The
reporting summary adds behavioral performance above 70% and at least five
trials of every condition, but does not identify the exact retained cohort.
The original split unit, real-data fitting caller, per-neuron numeric baseline,
cross-epoch aggregation and justified improvement/uncertainty rule remain
unresolved. This component does not change that qualification state.

Sources and exact cached-evidence digests are in `SOURCE.json`. No original data,
private targets, source-author code, predictions or local evidence paths ship
with this implementation. Tests use analytic generated controls only.
