# Full32 paired-participant bootstrap

This standalone sidecar summarizes an authenticated, completed result from the existing NEURAL-077 full32 paired evaluator. It leaves that evaluator, its condition protocol and its captured evidence unchanged. It reads aggregate evaluator summaries, not EEG, private labels, candidate code or participant capture files.

The input must retain all 32 fixed participants, both numeric conditions, 200 trials with 40 targets and 160 standards per participant, and the original direct-minus-program orientation. The sidecar checks class-confusion balanced accuracy, equal-person macro means and all paired differences. Missing, duplicate, foreign, reordered or inconsistent rows are refused. A matching hash binds the selected bytes; it does not prove that an untrusted producer performed a truthful evaluation. The operator must authenticate the completed upstream result and capture provenance before using it.

The immutable evaluator computes balanced accuracy at `p >= 0.5` and natural-log loss with metric-only clipping at `1e-15`. This sidecar resamples those participant summaries; it does not recompute or change trial predictions or clipping.

## Versioned statistical policy

`BOOTSTRAP_POLICY.v1.json` implements the previously declared 95% percentile interval using 10,000 paired bootstrap draws of 32 participants, with replacement, from NumPy PCG64 seed `20261119`. Trials are never sampled as independent participants. Both arms and every metric use the same index array.

The explicit prospective completion uses NumPy linear quantiles at 0.025 and 0.975. The primary interval is direct-minus-program participant-macro balanced accuracy. Five secondary intervals are reported without multiplicity adjustment: the paired natural-log-loss difference, each arm's macro balanced accuracy, and each arm's macro natural-log loss. These conventions are recorded separately; the historical protocol and evaluator are not rewritten.

Output contains aggregate point estimates and intervals, the policy and runtime versions, a reproducible draw fingerprint, and upstream result/contract/arm identities. It does not duplicate participant identities or per-person rows. The original evaluator result retains the 32 paired differences. There is no significance threshold, pass criterion, improvement-readiness claim or population-inference claim. These are summaries of this finite public cohort.

## Command

Use an operator-authenticated Python/NumPy installation whose identity was frozen before execution. The command checks explicitly supplied versions; those checks alone do not authenticate an entire installed runtime. The source-control environment is Python 3.11.6 with NumPy 1.26.3.

```sh
python -I -B paired_bootstrap.py \
  --result ACCEPTED_RESULT.json --result-bytes RESULT_BYTES --result-sha256 RESULT_SHA256 \
  --policy BOOTSTRAP_POLICY.v1.json --policy-bytes 1396 \
  --policy-sha256 bf3dddf5ea64b910ee68f10502eb214b65d4b7ef38c50bfc2f425430ca5cd0c2 \
  --python-version 3.11.6 --numpy-version 1.26.3 \
  --output FRESH_BOOTSTRAP.json
```

Both inputs require exact byte/hash commitments. Inputs are bounded ordinary files and the output must not already exist. The pure numerical entry is `paired_bootstrap(result, policy, expected_python_version=..., expected_numpy_version=...)`; callers supplying objects are responsible for authenticating their input bytes first.

## Generated controls and limits

`python -I -B test_paired_bootstrap.py -v` exposes ten new generated controls. They check shared pairing, fixed-seed determinism, direct-minus-program orientation, equal-person weighting, manual linear-percentile calculations, complete-panel refusal, runtime-version checks and pinned, create-only CLI output. Fixed published participant identifiers are paired only with invented test summaries; no actual results or private joins are fixtures. Replicate arrays remain in memory and the small CLI fixture uses temporary JSON files.

The suite is source validation, not an original-data bootstrap, model run, capture qualification or scientific outcome. Any later use must preserve the upstream feedback-release and authoring-custody requirements. No bootstrap result from a real participant comparison is claimed by publishing this code.
