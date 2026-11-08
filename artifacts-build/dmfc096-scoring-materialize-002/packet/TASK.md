# NEURAL-096: reconstruct a fixed neural population contrast

This brief defines the fixed selected-count numerical reconstruction. Packet materialization and scorer qualification are separate operator-recorded states.

Given spike counts and cue metadata for 177 fixed trials, reconstruct the raw and clock-adjusted short-prior versus long-prior population contrasts. Use every supplied trial, all 40 units and all 15 bins. Return the signed results, including negative values. A larger positive contrast is not a better answer.

The observation condition supplies a standardized neural count representation. It evaluates analysis of those observations, not raw recording extraction or native waveform understanding. The observations come from one already exposed monkey/session. This task does not predict produced behavioral intervals, establish a population effect, or reproduce the paper's historical GPFA pipeline.

## Inputs and identities

The public packet contains `counts.npz`, `cue_metadata.json`, this task brief and an exact manifest. Counts have axes `(trial, unit, bin)`, shape `(177, 40, 15)` and unsigned 32-bit integer values. The archive also supplies exact trial IDs, unit IDs and bin edges. Cue rows contain only trial ID, split, short-prior indicator, eye/reach modality, direction, Ready time and Set time. Their order matches the count tensor: 129 training trials followed by 48 validation trials, chronological within each split.

The manifest binds these complete identities and the instructions. No subset, alternative order or replacement metadata is permitted. Full NWB files, produced intervals, Go times, outcome flags, held-out-unit spikes and reference results are not public inputs. Prior labels are necessary factors of this analysis; they are not prediction targets to conceal.

The 15 count bins are half-open 50 ms intervals covering the 750 ms before Set. Set itself is excluded. Counts already implement this extraction; do not re-bin them. There is no normalization by firing rate or duration.

## Fixed calculation

1. Set `Y = sqrt(counts)` in float64. Form four strata in order `(is_eye, theta) = (false, 0), (false, 180), (true, 0), (true, 180)`.
2. In each stratum and split, compute a mean vector for each prior. The prior axis is **long, short**. Define each oriented difference as **short minus long**.
3. For each stratum and bin, multiply the training and validation differences elementwise and average over the 40 units. Average the four stratum results equally for each bin, then average the 15 bins equally for the raw scalar. Do not weight strata by their trial counts, square a single split's difference, take absolute values, or clamp negative values.
4. Fit one joint multivariate ordinary least-squares model per stratum using training rows only. The ordered design columns are `[1, is_short, z_clock, z_clock², z_duration]`. Clock is Set time; duration is `Set − Ready`. Compute each mean and population standard deviation (`ddof=0`) using that stratum's training rows. Apply those same scales to validation. If training duration is exactly constant, omit its column and return zero coefficients in that slot; do not omit another column or regularize.
5. Use the declared full-rank gate: at least `p + 1` training rows, singular-value tolerance `max(n, p) × eps64 × largest_singular_value`, and condition number at most `1e8`. Use least-squares `rcond = max(n, p) × eps64`. There is no parameter selection or fallback fit.
6. Subtract only the fitted clock, squared-clock and duration contributions from **both** splits. Retain the intercept and prior contribution. Recompute all means, oriented differences, per-stratum products, bin averages and the scalar from these adjusted values. The adjustment is descriptive; it is not claimed to be an unbiased cross-validated distance or a causal estimate.

All four strata, both splits and both priors are required. Do not drop rows, choose an outlier rule, fit nuisance coefficients on validation, or select a result according to its sign.

## Submission

Submit `submission.json` and `submission.npz` using `PUBLIC_CONTRACT.json`. The JSON binds the exact public-manifest SHA256, `NEURAL-096`, observation condition `selected_counts`, and status `complete`. Arrays use the fixed positional axes of that manifest.

The NPZ contains eleven finite little-endian float64 arrays: the four sets of five coefficients; raw and adjusted means; raw and adjusted short-minus-long differences; raw and adjusted per-stratum/bin products; raw and adjusted bin averages; and the two scalar values. The exact shapes are in the contract. The numeric values occupy 327,616 bytes; the complete NPZ limit is 524,288 bytes. No pickled objects, duplicate members, extra arrays or external links are accepted. JSON is strict UTF-8 and at most 32,768 bytes.

For whole-task abstention, submit only JSON with status `abstained` and a bounded reason. It receives coverage zero, null numerical metrics and no private reference load. A partial result labelled complete is invalid; the scorer never averages only the available cells.

## Assessment

The primary numerical outputs are absolute errors for the raw and adjusted scalar. Every oriented coefficient, mean, difference and trajectory is also compared, with per-block RMSE and maximum absolute error. The scorer checks public arithmetic and training-only normal equations. Matching only the scalars does not establish correct reconstruction: reversing both prior differences can preserve their product.

Finite, well-formed wrong answers remain scored answers with their errors. Signed negative effects are valid. Numerical agreement tolerances are engineering checks, not effect-size, significance or scientific-success thresholds. Extreme finite values that make required arithmetic nonfinite receive an explicit unsupported-numerics outcome rather than clipping or selective averaging.

A file score does not establish what the producer accessed, whether it fitted only on training data, or whether it computed its answer rather than copying exposed results. Those require a separately qualified program-execution and changed-input test. Optional method prose is not proof of provenance.
