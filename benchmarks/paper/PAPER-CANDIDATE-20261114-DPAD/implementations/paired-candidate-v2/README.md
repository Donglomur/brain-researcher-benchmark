# DPAD paired candidate scorer

This component compares an arbitrary candidate's frozen predictions with all
seven author model profiles on the original joint behavior/neural endpoint.
It adds the missing candidate comparison path to `initial-evaluator-v1`, whose
implementation and evidence remain unchanged. It does not fit a model, prepare
recordings, reproduce Figure 6, authenticate an author baseline, or decide a
paper win.

Reproduction of the original findings and improvement beyond them are separate
first-class outcomes. The complete author-grid metrics support a future
reproduction assessment; paired candidate/author metrics support a future
same-task improvement assessment. Both remain `not_assessed` here. Reproduction
is not demoted to only a comparator step, and numerical agreement alone is not
promoted without source fidelity. Paired paper+data versus paper+data+author-code
participant delivery is outside this scorer and remains to be built and audited.

The owner freezes the full author grid once: 7 candidate session identities ×
5 temporal folds × 8 dimensions × 7 author methods = 1,960 prediction cases.
The unchanged predecessor selects its author configurations from the complete
90-architecture training grid and computes channel-mean Pearson correlations.
The resulting reference retains every grid score and source artifact digest.

A candidate may use its own named algorithm and configuration at every latent
dimension; it need not use the author's architecture menu or `n1`. Training
records cover the same eight dimensions and all 35 folds. Selection follows the
paper's larger-of-two-smallest-peak dimension rule. Candidate predictions cover
all 280 dimension/fold cases. Final paired reporting uses the 35 training-selected
models, retaining neural CC and behavior CC for each of the seven author contrasts.
The complete author architecture comparison is preserved separately.

`paired.py` has three commands, all using standard Python 3.10+:

```sh
python3 paired.py freeze-author --training AUTHOR_TRAINING --targets TARGETS --predictions AUTHOR_PREDICTIONS --output REFERENCE
python3 paired.py select-candidate --training CANDIDATE_TRAINING --output PLAN
python3 paired.py compare --targets TARGETS --reference REFERENCE --plan PLAN --predictions CANDIDATE_PREDICTIONS --reference-sha256 OWNER_REFERENCE_DIGEST --plan-sha256 OWNER_PLAN_DIGEST --output RESULTS
```

Freeze commands print the canonical-content SHA256. Expected hashes must come
from the owner's protected freeze record. A participant must not choose these
hashes or replace reference/plan/training/target artifacts. Digests detect changes;
they do not prove chronology, truthful training metrics or permitted inference.
Reference and result files contain evaluator-side scores and must remain outside
the participant input path and public Git. The result includes all 245 paired
fold deltas, 49 session-level descriptive means, both endpoint summaries, and a
clearly labeled predecessor frontier diagnostic. No paper-win flag is emitted.

The generated fixture in `test_paired.py` is an executable schema example. Author
training and predictions retain the predecessor schema. Training, target and prediction
bundles additionally carry a `channel_layout` keyed by session, with ordered
`neural` and `behavior` lists of `{id, unit}` entries. Neural width is 77–99;
the four behavior IDs are `position_x`, `position_y`, `velocity_x`, `velocity_y`.
These are canonical role labels; units must be obtained from authenticated
preparation and recorded consistently. Every prediction/target case repeats its
ordered `neural_channel_ids` and `behavior_channel_ids`. Equal array shape alone
does not establish alignment. Units are compared, never converted silently.

Candidate training records add `candidate_id`, `code_sha256`, `channel_layout`,
and per-dimension `configuration_sha256`, `training_neural_cc` and
`training_behavior_cc`. Each case retains fit/selection sample membership.
Candidate predictions bind the same candidate/code and frozen plan, and each
case binds its dimension/configuration. No candidate fit/search is executed.

Only the historical symmetric preprocessing declaration and exactly one-step
prediction lag are admitted to this same-task comparison. The earlier causal
profile and greater lags cannot silently become the original endpoint. Source
preprocessing itself is still unverified. Missing samples, mismatched sample
order, changed channel IDs/units, incomplete grids, nonfinite predictions and
constant channels reject scoring. This retains the predecessor's strict rule;
the official code's invalid-row filtering and later channel sanitization remain
unresolved and are **not claimed equivalent**. We do not implement a guessed
sanitizer or silently drop difficult rows.

The 35 paper reporting units are dependent folds in seven sessions of one monkey.
SEM and signed-rank frontier results here are calibration diagnostics; session
means are descriptive and do not resolve inference or meaningful-effect rules.
Numeric published Figure 6i values, original channel sample, session crosswalk,
preprocessing/caller identity and authentic author predictions remain missing.
None of the generated controls establishes performance on recordings.
The inherited interface loads JSON artifacts into memory. No full-panel memory
profile has been measured; authentic scoring needs its own resource review and,
if necessary, a reviewed streaming adapter before execution.

Tests cover independent orthogonal-vector CC calculations; an intentionally best
held dimension that must not change the training choice; all-grid completeness;
sample/channel/unit identity errors; author/plan/target drift; prediction failures;
same-task observation restrictions; source lineage; and the executable selection
CLI. Run `python3 -m unittest -v test_paired` through the authorized lightweight
test pool. The fixture uses 78 generated channels for dimensional controls only.

Source lineage: the source-paper [Methods and Figure 6](https://www.nature.com/articles/s41593-024-01731-2)
define the dual endpoint, folds and dimension selection. The cached official
[evaluation.py at 41f108bc](https://github.com/ShanechiLab/DPAD/blob/41f108bc90252ced19fe3c8eda7eaff2e87c57b3/source/DPAD/tools/evaluation.py)
supports channel CC and highlights the unresolved row/sanitization distinction.
No author code is copied or executed. See `provenance.json` for exact pins.
