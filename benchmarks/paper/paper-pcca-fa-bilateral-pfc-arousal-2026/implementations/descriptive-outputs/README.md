# Bilateral PFC covariance and pupil reproduction outputs

This is the portable quantitative evaluator component for the existing task
`paper-pcca-fa-bilateral-pfc-arousal-2026`. It evaluates the complete declared
historical empirical assay. It does not fit a model, launch candidates, establish
native data lineage, or implement the separate protected prediction task.

Reconstruct the paper's covariance partition and pupil associations from all 42
bilateral recording sessions. Preserve both hemispheres and every admitted
channel/trial. Produce the full model parameters, full-session fitted pupil
predictions for three latent groups, the top-latent control, and every ordered
same-animal mismatched-session prediction. The 41-session pupil population must
result from the published per-animal variance rule applied to all 42 sessions;
do not select an exclusion to match the expected counts. The historical paper
reports a fitted association, not held-out prediction accuracy.

Use the authenticated source preparation policy and a future competent reference
once they are admitted. The remaining 100 microsecond versus 1 millisecond
crosstalk and pupil-filter wording differences remain unresolved. This component
cannot turn an arbitrary preparation into a faithful reproduction. Numerical
acceptance tolerances are unset. Published rounded values provide context only.

## Interface

The operator supplies a trusted UTF-8 support JSON with exact keys:

* `task`: the task ID above; `schema`: `pcca-prepared-support-v1`.
* `preparation_binding`: SHA256 of the separately reviewed complete native
  preparation/provenance artifact. A string-shaped hash is a binding, not proof
  of that artifact's scientific validity; the existing operator must admit it.
* `sessions`: all 42 records in the sorted `ROSTER.json` order. Each has `id`,
  `channels` with ordered `left`/`right` identities, ordered unique `trial_ids`,
  and full-session un-z-scored `fast_pupil` values. Channel and trial identities
  must come from native preparation. The checked-in tests fabricate these values.

The candidate produces newline-terminated JSONL, in this exact order:

1. One header: `kind=header`, `schema=pcca-output-v1`, exact `task`, and SHA256 of
   the exact operator support file as `support_sha256`.
2. All 42 model records in roster order: `kind=model`, `session`, exact
   `channels`, `dimensions` (`across`, `left`, `right`), `loadings` (`W_left`,
   `W_right`, `L_left`, `L_right`), `noise` (`left`, `right`), ten finite selected
   fold `selected_cv_loglik` values and finite `final_loglik`. Loadings are
   channel-by-factor, with the same across-factor basis in both hemispheres.
   Dimensions follow the source's 1..min(15, channel-count) bounds. Full search
   logs remain an external method-audit obligation; ten numbers do not prove
   that the full dimension grid was searched or that fitting converged.
3. All 41 admitted pupil records in sorted order: `kind=pupil`, `session`, exact
   full `trial_ids`, and `predictions`. Predictions have two modes, `all` and
   `one`, each containing full arrays for `across`, `within_left`, `within_right`.
   Predict the operator-derived within-session z-scored pupil. The `one` mode
   must use the leading SVD-ordered latent, including the paired across-area
   transform specified by the official driver; a random first coordinate is not
   the source control. Prediction values alone cannot prove this construction.
4. All 552 ordered distinct same-animal pairs, ordered by sorted source then
   target: `kind=pair`, `source`, `target`, exact `source_trial_ids` and
   `target_trial_ids` truncated to the minimum of the two complete session
   lengths, plus the same six prediction arrays. The source supplies latents;
   the target supplies pupil. Each mismatched regression is fitted on that pair,
   as in the source. Do not refit z-scoring after prefix truncation. Both the
   full-latent and single-latent drivers generate these controls.

There are exactly 636 records. No omissions, extra records (including JSON null),
NaN/Infinity, duplicate JSON keys, reordered identities, substituted groups,
negative noise variances, constant pupil targets, or zero-energy selected loading
dimensions are silently repaired. All-zero contrasts produce undefined t and p. Constant nonzero contrasts have
an explicitly labeled limiting p of zero or one and null t; neither is a finite
t statistic. No unit is dropped to manufacture a p-value.

```
python3 -I -S -B evaluate.py --support prepared-support.json \
  --candidate candidate.jsonl --reference admitted-reference.jsonl \
  --output fresh-report.json
```

`--reference` is optional for descriptive output evaluation. When supplied, it
must cover the same full support and pass the same admission rules. The report
includes invariant covariance/noise differences and complete prediction MSEs.
It never equates a successfully parsed reference file with an authenticated
competent baseline. Output creation is exclusive; failed input validation writes
no success report. An output write error may leave a partial file to preserve.

The stream is bounded to 256 MiB total and 2 MiB per JSONL record; the support
file to 16 MiB; each hemisphere to 512 channels and each session to 100,000 trials.
These are refusal ceilings, not permission to subsample. If complete authentic
support exceeds them, revise and review the engineering envelope. No full-data
runtime or memory feasibility is claimed by small generated controls.

Run the generated controls with `python3 -I -S -B test_evaluate.py -v`.
No original data, reference values, fitted model, or source repository is loaded.

Paper: [Interactions across hemispheres in prefrontal cortex reflect global cognitive processing](https://doi.org/10.1038/s41467-026-71725-0).
Official [model](https://github.com/SmithLabNeuro/pcca_fa) and
[figure code](https://github.com/meganmcd13/figures-dual-pfc) identities are in
`PROVENANCE.json`. See `METHOD.md` for the exact mathematical mapping.

## Portable source boundary

Python 3.11 or later on a POSIX system with `O_NOFOLLOW` and `O_NONBLOCK` is
required. The runtime consists of `evaluate.py`, its companion `ROSTER.json`,
and the standard library. No NumPy, SciPy, author repository or private checkout
is imported. Public roster strings describe the published session population;
they do not authenticate native channels, trials, targets or the Wa exclusion.

Run `python3 -I -S -B test_portability.py` for exact source inventory and real
relocated complete-CLI controls. `test_evaluate.py` contains the original generated
mathematical controls. The portable test fabricates every numeric value and
trial/channel identity; it is not an authentic fit or a paper result.

This independently authored evaluator is supplied under the bundled MIT license.
No official model code, notebooks, paper text, authentic inputs, fitted parameters
or reference outputs are bundled. `SPEC.json` identifies input schemas and limits;
`SOURCE_MANIFEST.json` covers every other file, excluding itself. Keep the support
(which includes pupil targets), optional reference and detailed report private to
the operator. Unlike the separate DFINE API, this evaluator reads trusted support
before candidate validation. It is not a target-release or isolation service.
