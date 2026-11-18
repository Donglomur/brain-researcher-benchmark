# Selected original main-panel comparison

This component supplies descriptive comparison for the current selected endpoint:
99 original main PCA model conditions, 17 ROIs, ten participants, 102 repeated
test videos and ten repetitions. It retains every participant/layer RSA value,
every mean-then-layer-max profile and all 17 lower/upper test noise ceilings.

The existing `original-panel-comparison-v1` also requires 92 SRP, 92 unreduced,
51 training-video and one auxiliary model condition. Those belong to separately
retained paper analyses. This component does not manufacture their unavailable
inputs, require them for the selected main endpoint, or claim to complete them.
Its source of scope is the task's `primary-endpoint-v1/selection.v1.json` and
`reproduction.v2.json`; `SOURCE.json` records their exact identities.

`compare_main.py` loads the existing comparator only after checking its exact
12,907-byte SHA-256 identity. It executes the verified bytes and reuses the
pinned source axes and original signed selection function. No feature extractor,
RDM producer, Spearman computation or scientific fit is duplicated.

## Inputs

Both modes require `--protocol`, the same pinned metadata file used by the
predecessor. Its SHA-256 is
`59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c`.
The full repository-relative path is recorded in `SOURCE.json`.

The reference JSON has exactly these fields:

- `schema`: `hundred_models_selected_main_reference_v1`.
- `origin`: `published_author_outputs` or `reproduced_author_outputs`.
- `test_support`: the predecessor's exact subject, stimulus, repetition,
  brain-RDM digest and video-input digest fields. Names and order come from the
  pinned protocol; both compared sides must declare identical observations.
- `run_sha256`: digest of the full external scientific run record.
- `noise_ceilings`: the 17 ordered `{roi, lower, upper}` test rows.
- `layer_catalog`: all 99 `test:pca:<model>` conditions, each with its complete
  ordered evaluation-layer list.
- `rsa`: all 99 × 17 ordered `{condition, roi, layers, values}` rows. Every layer
  has all ten signed participant correlations in the original order.

Candidate mode accepts the predecessor's
`hundred_models_original_candidate_v1` schema: the same `test_support`,
`run_sha256`, `freeze_sha256`, one complete candidate `layers` list and 17 ordered
`rsa` rows. Candidate layer names may differ from author models; they cannot
change across ROIs. The output keeps all 1,683 candidate/reference differences
and the 17-ROI strongest-reference profile. No mean or count across ROIs is
substituted for that vector.

Reproduction mode accepts the reference fields without `origin`, with schema
`hundred_models_selected_main_reproduction_v1`. Its complete layer catalog must
match the reference. The output retains both sides and every paired
participant/layer difference, profile difference, selected layer and ceiling
difference. It supplies no invented tolerance, equivalence pass or missing-data
imputation. Matching a descriptive difference is not independent reproduction.

Both modes reject missing, extra or reordered support; malformed/nonfinite
correlations; unbound observation digests; and missing test companions. Explicit
null statistics stay visible. An undefined reference layer prevents that
model/ROI selection; any undefined main reference prevents choosing a strongest
model from the remaining subset. Schema fields for separate training/auxiliary
branches are rejected instead of silently ignored.

## Invocation and tests

From this installed component directory:

```text
python3 -I -S -B compare_main.py --mode candidate --protocol PROTOCOL.json \
  --reference main_reference.json --observed candidate.json --output comparison.json
python3 -I -S -B compare_main.py --mode reproduction --protocol PROTOCOL.json \
  --reference main_reference.json --observed author_rerun.json --output replay.json
```

An existing output is never overwritten. Input JSON has the predecessor's strict
duplicate-key/nonfinite rejection and 64 MiB per-file ceiling. An explicit
`--legacy-component` path may locate the exact pinned source outside its normal
sibling location; it does not permit an unverified replacement.

`test_compare_main.py` uses generated correlations only and the existing source
protocol. Eight tests passed once through the shared bounded pool. They check
complete main support, equality with the predecessor's main outputs when a full
335-condition generated record is available, strongest-reference selection,
undefined coverage, identity/layer/companion failures, full reproduction
differences, immutability and refusal to execute altered helper code. No authentic
RSA data, model weights, fMRI arrays or new dependency were used.

The test resolves repository root from the installed directory. During private
review, set `BENCHMARK_REPOSITORY_ROOT` to the read-only repository. CI enrollment
requires an explicit new component command; these files alone do not enroll it.

## Scientific limits

The result is always descriptive: `reproduction_pass`, `paper_win`, an across-ROI
decision, confidence interval and equivalence tolerance remain null. The original
public panel is not an unseen candidate test. Selected participant differences
follow whole-cohort layer selection and are not independent confirmatory units.

Digest equality does not authenticate original inputs, source-equivalent
preprocessing, missing historical RSA arrays, checkpoint/layer completeness,
noise-ceiling derivation, candidate freeze chronology or permitted exposure.
Source-valid independent replay, meaningful effect and selection-aware
participant/stimulus inference still require separate qualification. The task's
source-unresolved status and both access conditions remain unchanged. No AI,
reproduction, improvement, SOTA or whole-paper completion result is claimed.
