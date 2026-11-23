# NEURAL-040 fixed-fit evaluator v2

This additive scorer closes two identified software gaps in the existing
multimodal investigation: a submission cannot alter an ablated arm while retaining
valid metadata, and a report must include all three modality claims. The original
encoder, scorer, contract, and historical evidence are preserved unchanged.

The operator supplies the frozen protocol, permitted precomputed features, and
training targets. The scorer independently reruns the pinned predecessor encoder
for every person and every full/no-audio/no-visual/no-language arm. It compares
every submitted array to the recomputed predictions before requesting private
evaluation targets. A new hash on a forged prediction file does not bypass this
comparison. The complete finite claim vector is also validated before target access.

Predictions must agree within fixed `rtol=1e-10, atol=1e-12`; these are numerical
comparison tolerances, not scientific effect thresholds. All scoring uses the
recomputed arrays, including when a submitted difference passes the tolerance.
This avoids amplifying tiny changes to nearly constant predictions through Pearson
normalization. Exact cross-platform reproducibility of degenerate PCA eigenspaces
is not established: the scoring environment and input bytes must be frozen before
an authentic run, and a numerical disagreement fails rather than changing the fit.

The encoder source is pinned by SHA256
`19d1f793b0c59200420dcfd0570be911202c402698f488a3b75ae5a128f6db98`.
The scorer imports only the verified predecessor bytes. Four source participants,
1000 ordered parcels, whole-film split, training-only PCA/ridge, common rank and
regularization, guarded rows, equal film/parcel/person Pearson aggregation,
signed contrasts, and the original descriptive uncertainty/null controls are retained.
All absolute arm correlations remain in the output. Complete numerical claims are
checked at the predecessor's absolute `1e-8` tolerance; an incorrect complete claim
returns `verified=false`. No larger-effect reward or favored modality is introduced.

## Operator interface

Use the unchanged v1 `encode` command to create predictions, then run:

```sh
python evaluator.py \
  --protocol protocol.json --features features.npz \
  --training-targets training-targets.npz \
  --training-target-metadata training-targets.json \
  --predictions encoded/predictions.npz \
  --prediction-metadata encoded/prediction-metadata.json \
  --claims claims.json \
  --private-targets private-targets.npz \
  --private-target-metadata private-targets.json \
  --output private-score.json
```

The protocol and target sidecars retain the [v1 packet format](../../docs/initial-evaluator-v1.md).
`claims.json` must contain exactly one `{"family": "audio", "mean_delta_r": 0.0}`
record for each of `audio`, `visual`, and `language`. The numbers are the participant's
reported estimates; zero here illustrates the format and is not a reference answer.
Unknown/duplicate families, missing claims, booleans, nonnumeric or nonfinite values
are rejected. Output creation is exclusive and never overwrites an existing score.

The callable `score_fixed_fit` uses the same path. Its `evaluation_loader` is a
trusted operator callback that returns `(targets, target_metadata)` after claim and
prediction verification. It must not execute participant code. This ordering is
an API property, not a process sandbox. Keep every evaluation target and score
(including per-parcel effects) operator-private, and provide no scoring feedback
during protected assessment. The output records input hashes without local paths. Each JSON or NPZ input is
read once into an immutable byte snapshot; parsing, array loading, and its reported
SHA256 use that same snapshot. Prediction metadata is included in the recorded
identities. A file replaced after capture cannot silently relabel the bytes used.
Duplicate JSON/NPZ keys, nonfinite JSON constants, and pickled arrays remain refused.

This holds one compressed NPZ snapshot in memory while decoding its arrays, so
operators must budget that additional peak memory for the largest input archive.
It does not make the collection of files an atomic snapshot or authenticate their
scientific origin; supplied target/prediction metadata must still match the captured
archive hashes. Private snapshots are captured only after fixed-fit verification.

The reference input paths must be selected and frozen by the operator. Letting a
participant replace protocol/features/training targets would defeat their scientific
meaning even though the numerical check still succeeds. File hashes and a refit do
not establish authentic source lineage, upstream extractor context/exposure, source
parcel order, pre-outcome freezing, or isolation from held targets. This component
checks consistency with the supplied reference inputs; it does not authenticate them.

## Validation and qualification

The task-local generated controls test unchanged full scoring, a forged ablation
accepted by v1 but rejected by v2 before private loading, omitted/extra/swapped
predictions, complete claim schema, incorrect numerical claims, roundoff tolerance,
changed features, and actual CLI file/hash behavior. Run through the shared approved
test pool with one thread and at most 1 GiB/180 seconds. No additional dependencies
beyond the existing NumPy environment are needed.

Authentic four-person data/feature preparation, source identities and parcel
alignment, feature/media rights and exposure, nuisance/time-only companion,
competent source reference, participant transport/isolation, protected assessment,
and scientific admission remain unresolved. No authentic data preparation,
model trial, organizer reproduction, causal interpretation, population inference,
or scientific qualification is established by this software change.
