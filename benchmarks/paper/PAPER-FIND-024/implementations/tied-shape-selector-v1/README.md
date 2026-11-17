# Source tied-shape selection

This component supplies the missing shared-shape parameter selection used by the source predictor. Given already computed loss grids for **one original segment split**, it selects a common gamma shape across slow and fast speech, while allowing integration width, start delay and boundary strength to vary by rate. It preserves the source operation “minimum within each shape and rate, then sum across rates.” Summing the rates before minimizing nuisance parameters would impose additional tying and change the predictor.

The current PAPER-FIND-024 contract compares a tied predictor against fixed, opposite-split **untied** integration-window estimates (published Spearman anchor 0.668). This selector advances recovery of that predictor. It does not generate the loss grid, recreate either segment split, create or read evaluator targets, compute the final Spearman reduction, establish native parity, or qualify an improvement. The unchanged historical CCC implementation remains a separate prospective reconstruction component.

Reproduction and same-task improvement are separate first-class outcomes under the latest project scope. This source operation supports recovery for both, but supplies neither complete score. Paper-plus-data and paper-plus-data-plus-author-code participant conditions must remain distinct; this source-inspection work does not constitute either participant trial. The existing task/contract files are unchanged pending central integration of that broader scope.

## Source and scope

The implementation follows [tie_shape.m at the pinned author revision](https://github.com/snormanhaignere/time-vs-structure/blob/08f2319a99a047ab2d1f631e0bffcfcea8a5bc08/matlab-code/tie_shape.m): its loss axes are width, delay, shape, boundary strength, channel. Lines 15–21 minimize nuisance parameters separately in each rate before summing. Lines 30–47 recover each rate's width, start delay and boundary strength at the common winning shape. Lines 50–56 assert coordinate consistency across rates. All channel identities and their order are retained; no channel filtering occurs.

The [author demo](https://github.com/snormanhaignere/time-vs-structure/blob/08f2319a99a047ab2d1f631e0bffcfcea8a5bc08/matlab-code/demo_model_fits.m) uses `unbiased-sqerr`, 100 widths over 0.0312–2 seconds, zero start delay, shapes 1–5, interval mass 0.75, and boundary strengths 0, 0.25, 0.5, 1, 2. This component consumes losses and coordinates explicitly; it does not infer the unrecovered width spacing or loss formula from those settings. Grid generation and original settings must be bound before a source baseline run.

Only finite float64 losses with a unique winning shared shape and unique winning nuisance tuple in each rate are supported. Negative losses are retained. Duplicate grid coordinates, malformed axes, nonfinite/complex/Boolean tensors, missing channels, reversed rates, ambiguous minima and overflowing pooled losses are rejected. This deliberately limited domain avoids inventing the unresolved native `myminall` tie/NaN policy. Equal floating-point minima are tested exactly; no tolerance silently changes the winner. Start delay is returned; the source's median-delay conversion requires TCI's `modelwin_convert_delay` and is not implemented here.

The source cache contains public author code only; no empirical data or historical private targets were opened. The recovered cached bytes and earlier normalized-source pins are recorded in [source-provenance.json](source-provenance.json). No author code is redistributed in this component.

## Interface

`select_tied_shape(loss, *, intper_sec, delay_sec_start, shape, boundstrength, channel_ids, rates)` consumes:

- `loss`: six-dimensional real tensor **rate × width × delay × shape × boundary strength × channel**. The outer rate axis joins the two source per-rate arrays; the remaining five axes preserve author order.
- `intper_sec`, `delay_sec_start`: width and start-delay coordinate vectors in **seconds**.
- `shape`, `boundstrength`: dimensionless coordinate vectors.
- `channel_ids`: unique nonempty strings in the loss tensor's channel order. For pooled use these must include participant identity; electrode numbers alone are not globally unique.
- `rates`: exactly `[1/sqrt(3), sqrt(3)]`, in slow/fast order.

All parameter coordinates are shared across rates, as required by the author checks. The output gives two rows per channel, including physical parameter values, zero-based coordinate indices, the selected per-rate loss, and the sum of rate-specific minimum losses for the selected shape. `shape_loss` retains every supplied shape and channel in input order. No population reduction, cohort selection, target estimate or uncertainty result is emitted.

The offline CLI requires a local NPZ containing exactly these seven arrays, with `channel_ids` stored as a NumPy Unicode vector. It forbids object-pickle loading and binds the operator's previously frozen file hash. It captures the file once and loads those same verified bytes, so a later pathname change cannot substitute a different grid. That hash binds bytes, not scientific authenticity. Neither the CLI nor its report belongs on a candidate path that exposes opposite-split targets.

```sh
python3 selector.py /absolute/path/predictor-split-losses.npz \
  /absolute/path/tied-predictor.json --expected-sha256 OPERATOR_FROZEN_SHA256
```

Python 3.10+ and an existing NumPy installation are sufficient. Tests are generated software controls and must run through the shared two-slot test pool during this build. They include an exhaustive joint-search oracle and a counterexample where erroneous common-width tying chooses a different shape.

Original split membership, endpoint-specific participant/electrode roster, native loss generation and dependency closure, opposite-split untied target preparation, source 0.668 aggregation, paired uncertainty and native-author calibration remain unresolved. No same-task score, empirical improvement, or new scientific run is claimed.
