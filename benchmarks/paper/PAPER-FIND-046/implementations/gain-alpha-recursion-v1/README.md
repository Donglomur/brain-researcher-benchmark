# Figure 3 gain and learning-rate recurrences

This component reconstructs the deterministic reward-belief updates used by
the source's Figure 3a and gain-versus-learning-rate simulations. It fills a
computation absent from the existing Figure 2 evaluator and Figure 3k input
preparer. It does not establish full-panel reproduction or make the descriptive
hormonal association task eligible for an improvement score.

The implementation follows the pinned
[model helper](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/model/GenerateLatencyData_VanillaAlpha_cg.m)
and [Figure 3 caller](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/ProcessData_Figure3.m).
Only `opto_arg=0` and `fig=3` are included. The five named source calls preserve
the baseline and both stage conditions for gain and learning-rate changes.

## Source behavior retained

The first pass starts each retained session at one. Its complete state vector
determines the second pass's median initial state, separately for each learning
rate. Gain acts only when the current error is strictly above that learning
rate's first-pass threshold. Rows with missing ITI are excluded from the
recurrence, then restored as null outputs in their original positions.

Both source loops stop before the final retained trial: its error remains
missing, while its state is the preceding update. If that final trial starts
a new session, the source loop never applies its reset. The component preserves
and reports this asymmetry. There is no active latency floor. None of these
behaviors is silently repaired into a preferred model.

## Native-statistic boundary

MATLAB percentile semantics and the relevant MATLAB release are not qualified
here. An attempted official documentation lookup failed; no Python percentile
convention is substituted. `requests` emits the exact full ITI and first-pass
error operands, including nulls that a native exporter must restore to NaN.
`reconstruct` requires a receipt bound to the complete request hash, containing
the three finite 90th-percentile outputs. It rejects missing, extra, mismatched
or out-of-support values. **A hash identifies operands; it does not authenticate
a claimed MATLAB calculation.** Generated control receipts are labeled as such.

## Preparing the original Figure 3 input

`prepare.py` adds the three upstream transformations in the pinned
[Figure 3 caller](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/ProcessData_Figure3.m):
convert rewards with the source
[`convertreward.m`](https://github.com/constantinoplelab/published/blob/b7b68ca8c107d8ce4a061e16da214307f175c3e5/EstrousRPEPaper/process/behavior/convertreward.m),
set each session's first ITI to missing, then set ITIs **strictly above** the
native 99th percentile to missing. The percentile operands are the complete
ITI vector **after** session-first masking, including all original missing
positions. Neither percentile estimation nor MATLAB missing-value semantics
are inferred by Python. The native result remains an external requirement.
[Preparation source pins](PREPARATION_SOURCES.json) identify this added scope.

Raw input has the same four top-level fields and `rat_trial` arrays as the
model input below, but `preprocessing` must be `author_figure3_raw_ratTrial`.
Reward values are the original native `ratTrial.reward` values. Both steps of
`convertreward` are preserved: standard volume pairs 4/5, 8/10, 16/20, 32/40,
and 64/80 become 5, 10, 20, 40, and 80 respectively. Unlisted values, including
zero and negative values, are preserved by the source. Surviving input levels
1, 2 and 3 become 5, 10 and 20. No new reward-validity filter is introduced.

```sh
python3 prepare.py requests raw.json --output preprocessing-request.json
python3 prepare.py prepare raw.json --receipt native-p99.json --output prepared.json --audit-output preparation-audit.json
python3 model.py requests prepared.json --output recurrence-request.json
```

The `native-p99.json` receipt has exactly `schema_version: 1`, the matching
`input_kind`, `request_sha256`, a nonempty `producer` declaration, and `values`
with the single key `iti_p99`. Its request hash binds the complete raw input
identity and masked operands. The finite value must lie within the finite
operand support. **These checks do not authenticate native execution or prove
that the value is the 99th percentile.** Generated tests deliberately supply
branch-control values and make no percentile-parity claim.

The prepared JSON is directly accepted by `model.py`. The separate mandatory
audit binds its hash to the raw input, statistic request and receipt and
records every original row, reward transformation, first-ITI assignment,
outlier mask and final recurrence inclusion. No row, trial identity or
`ntrials` entry is removed. Zero-length sessions remain in the partition and
repeat the source assignment at the next session's first row. A trailing
zero-length session would extend MATLAB's ITI vector beyond the declared
original row count; this unsupported alignment is rejected explicitly.
All-missing percentile operands, fewer than two final retained ITIs, and
retained rows with missing rewards are rejected, rather than silently
subsetting or emitting an input that the recurrence cannot consume.

Both output paths must be distinct and absent. If an I/O failure occurs
between writes, any partial artifact is retained for inspection; the command
returns failure and both complete outputs are required before use. Input and
output hashes identify declared exports, not authentic original population
membership. This fills an input-preparation gap without establishing native
preparation, numerical parity, reproduction or improvement readiness.

## Input and commands

The input has exactly `schema_version: 1`, `input_kind`, `preprocessing` equal
to `author_figure3_preprocessed_ratTrial`, and `rat_trial`. That final object has
exactly `trial_ids`, `reward`, `iti`, and `ntrials`. The first three arrays retain
every original row and order; identities are explicit and unique. `ntrials`
partitions all rows in original session order, including zero-length sessions.
Missing numbers use null. At least two ITI rows must remain, and each nonempty
session's first ITI must already be missing, as required by the caller.

This interface starts **after** the author's reward conversion, first-ITI
removal, and 99th-percentile outlier handling. It neither performs those steps
nor authenticates them. No original rat/session support is inferred from an
exporter's declaration. Missing rewards on retained rows are rejected rather
than assigning an unverified propagation policy.

```sh
python3 model.py requests prepared.json --output requests.json
python3 model.py reconstruct prepared.json --receipt native-statistics.json --output recurrence.json
```

The receipt has exactly `schema_version: 1`, matching `input_kind`,
`request_sha256`, a nonempty `producer` declaration, and `values` keyed by
`iti_p90`, `first_rpe_alpha_0.6_p90`, and `first_rpe_alpha_0.8_p90`.
`input_kind` is `generated_engineering_control` or `authorized_native_export`;
the latter is a declaration, not permission or proof of native authenticity.
Existing output files are never overwritten. Each JSON input has an explicit
32 MiB envelope; larger full inputs are refused, never silently subsampled.

## Verification and remaining work

Generated tests use independently hand-derived recurrences to check median
initialization, session resets, strict gain comparison, all original row
positions, the final-trial asymmetry and inactive latency floor. Adversarial
controls check malformed partitions, duplicate identities/JSON keys, missing
values, altered statistic operands, receipt completeness and the actual CLI.
Some receipts deliberately inject branch-control values; those tests do not
assert MATLAB percentile parity.

```sh
python3 -B -m unittest discover -s tests -v
```

The public component needs explicit CI enrollment before integration. No
authentic array, MATLAB process, model fit or new scientific run was performed.
Native source preprocessing, source membership, native percentile receipts and
independent numerical parity remain gates. Supplied `BestFits`, the Figure 3
photometry/RPE joining and bins, block dynamics/regressions, and all other
original findings and companion panels remain separate required work. Results
always retain `reproduction_qualified: false` and `improvement_eligible: false`.
