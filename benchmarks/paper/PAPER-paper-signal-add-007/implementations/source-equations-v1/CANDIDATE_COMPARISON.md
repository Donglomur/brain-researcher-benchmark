# Candidate comparison on the original ICNet panel

`candidate_comparison.py` compares a proposed model with an operator-declared
ICNet baseline using the existing equations (3)–(5). It retains all four original
sounds, animals 3–9 and the 3,476 eligible units per sound. It reports the complete
Fig. 4d per-unit vectors and the separate Fig. 4b flattened animal companions.
Positive differences mean higher candidate values for that metric and observation;
they do not constitute a statistical or scientific improvement decision.

The existing `lnp_comparison.py` asks whether ICNet exceeds the paper's Poisson LNP
comparator. This interface asks whether a candidate exceeds ICNet on the same
numerical endpoint. The pinned equation scorer is unchanged. No model is fitted,
sampled or run by this interface: both models supply their already frozen sampled
count and expected count predictions for both recorded trials.

## Input and execution

The manifest has schema `icnet-candidate-comparison-input/v1` and exactly two
model entries, `baseline` and `candidate`. Each entry contains:

- `panel`: a complete `icnet-source-equations-input/v1` manifest described in
  [README.md](README.md#operator-interface).
- `provenance.model_sha256`: the declared model/checkpoint identity.
- `provenance.prediction_protocol_sha256`: the declared prediction protocol
  identity, including the count-distribution and expectation construction,
  random-generator version, draw/seed schedule, repeated draws and dependence
  between trials and models where applicable.
- `provenance.stochastic_policy`: a nonempty description of that policy. A
  deterministic policy must be stated explicitly. This text and its protocol
  pin are retained; neither is proof that the producer followed it.

All arrays are uncompressed NPY files relative to a common operator input root.
Predictions may use different paths and hashes. Both panels must name exactly
the same recorded-trial hashes, masks, ordered unit identities, temporal support,
trial measurement times, original training/evaluation split and explicit variance
divisor. Different observation paths are allowed if their authenticated bytes
match. Case ordering in the manifest may differ because the join uses animal and
sound identities. Different prediction-freeze pins are retained independently;
equal pins remain valid for an identity control.

```sh
python candidate_comparison.py --manifest /operator/comparison.json \
  --input-root /operator/aligned-arrays --output /operator/new-comparison.json
```

The output path must be new. Declared mismatches across the complete panel are
rejected before array access; the retained scorer then authenticates every NPY
and verifies the full support and numerical counts. Keep source arrays,
predictions, unit-level reports and private manifests outside Git. Authentic
scoring still requires the project's separately admitted resource and evaluation
protocol. Full-panel native runtime and memory have not been measured here.

## Output and scientific limits

For each of the 28 animal/sound cases, the report contains both models' complete
per-unit scores, diagnostics and candidate-minus-baseline percentage-point
differences, plus each model's flattened animal scores and their differences.
Undefined values remain `null`; their units are retained. Negative and above-100%
scores are preserved. No averaging across sounds, unit deletion, clipping,
significance test or universal scalar is applied.

Matching hash declarations establishes numerical comparability only after the
underlying bytes are checked. It cannot authenticate the original data/crop/mask,
prove that the baseline is the historical ICNet model, establish source numerical
parity or prove protected training and evaluation access. Units are nested within
seven animals, with repeated sounds and trials. A scientific improvement study
still needs a frozen effect and uncertainty rule for the full endpoint, a
stochastic replication policy, a qualified ICNet baseline and matched access and
resource budgets. All reproduction, improvement and paper-win flags remain false.

The mathematical and population source is [Drakopoulos et al., 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12460167/),
Methods “Predictive power metrics”, equations (3)–(5), and Fig. 4b,d. Existing
source provenance is retained in [source-pins.json](source-pins.json). The paired
candidate interface and handling of undefined differences are prospective
engineering choices, not recovered historical author code.

`test_candidate_comparison.py` exercises the actual numerical scorer on a small
generated 28-case panel, independently checks an analytic variance difference,
preserves undefined units and checks mismatched observations/columns/times/masks,
source pins, metadata and corrupted arrays. These are software controls only:

```sh
ICNET_CONTROL_FIXTURE_ROOT=/operator/generated-controls \
  python -B test_candidate_comparison.py
```
