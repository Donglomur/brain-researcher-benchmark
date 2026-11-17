# Original Figure 5 score panel

This component scores the registered 24-joint reaching/grasping endpoint against
**matched source-author predictions**, retaining all ten M1/S1 sessions, five
paired mice, and 50 held-out fits per session. It fills the original score-panel
and aggregation gap in the earlier phase-template scorer. Earlier implementations
and historical results remain unchanged.

`scorer.py` recomputes the source variance-explained metric for author and candidate
predictions, verifies the author's saved `VEs`, preserves the complete 50 × 24
panels, and reproduces `plotVEAll.m`: median across fits per joint, followed by
median across proximal joints 1–7 or distal joints 8–24. Candidate improvements
are differences between these original summaries, not the median of paired score
differences. Negative VE is retained. A constant target channel, missing session,
missing joint, malformed number, duplicate identity or incomplete fold is rejected;
no panel is silently narrowed.

This is executable **score-panel software**, not an authenticated author baseline
or an improvement-ready benchmark. Generated tests cannot recover the published
numerical panel. No authentic neural data, original author predictions, MATLAB
execution, fitting, candidate trial or scientific improvement has been performed.
The original source inputs, original folds and published numerical baseline remain
unresolved. No meaningful-effect threshold, uncertainty rule, scalar winner or
current-SOTA claim is introduced.

## Source fidelity

The [pinned cvRegress function](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/cvRegress.m)
uses `1 - var(y-yhat)/var(y)` over concatenated held-out trial timepoints. A constant
prediction offset therefore leaves VE unchanged; SSE/SST R² is a different metric.
Both sample-variance divisors cancel. For a complete original panel the comparison
must preserve all 24 ordered joints, the -100 through +400 ms lift-locked window
on the existing 10 ms source contract, all eligible trials and both source areas.

The [source plotting function](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/plots/plotVEAll.m)
defines the exact median-of-joint-medians reduction. It does not pool mice, flatten
joint/fold values or supply a single Figure 5 superiority statistic. The report
retains mouse pairing and does not treat fits or joints as independent animals.
Figure-panel lettering varies between the article and source script; these
function-level semantics identify the implemented endpoint.

The source split is five consecutive repetitions of ten trial partitions. Model
numbers 1–10 hold out permutation residues 1–9,0. Validation checks each recorded
model's exact modulo-compatible size, source trial order, complete complementary
train/test sets and once-per-repeat coverage. This is stronger than merely
checking balanced partitions, but **does not prove original fold authenticity**.
Seed `240926` alone is insufficient: PCA random rotations and the six model
configurations advance the shared RNG stream. This implementation consumes
recorded author fold manifests and never invents replacements.

`source-pins.json` records twelve official source files, verified against both cached
SHA-256 and Git blob hashes at revision
`815b610b3beddfed5a3abf611d3a465ab9e4ce5c`. These public sources were already cached;
no network payload or private solver reference was accessed for this work.

## Operator path

A future approved native author run may pass its completed `outputsM1_rr` and
`outputsS1_rr` structs to the provided MATLAB adapter:

```matlab
export_fig5_reference(outputsM1_rr, outputsS1_rr, '/private/new-reference.json');
```

The adapter exports original per-trial targets, recorded train/test identities,
saved fold VEs and predictions reconstructed with the corrected source intercept
formula. It uses `record.output`, the instantaneous RADICaL joint-angle model;
partial, residual, velocity, lagged and bagged reconstructions are not substituted.
It checks the source 90-PC/91-coefficient form and the 50-model/24-joint shape.
The date/area mapping follows `fig5_analysis.m`, including cfa24's later M1 date.
The source structs omit session date, so the caller must authenticate input-file
and session lineage independently; the explicit mapping alone cannot prove it.

The MATLAB adapter is source-reviewed but **has not been executed**. It is a
prospective native bridge, not evidence that an authentic MAT file is ready.
Large JSON serialization and authentic preparation require the separate native
resource protocol. The adapter's existence check is an operator safeguard,
not an atomic freeze. Freeze and independently review exported bytes before use.

```sh
python3 -I -B scorer.py \
  --reference /private/frozen-reference.json \
  --reference-sha256 <independently-recorded-sha256> \
  --candidate /private/candidate-predictions.json \
  --output /private/new-score-panel.json
```

The Python scorer uses only the standard library. It makes no download and never
fits a model. Its required reference hash rejects changed reference bytes; it
cannot certify the operator's source identity. Outputs refuse overwrite and
include input hashes. Keep references, scores, candidate predictions and all
numeric panels outside public Git. This is not a secure participant controller,
and a shared process/filesystem does not protect targets from participants.

The source reference and candidate JSON headers contain exactly:

- `schema: "fig5-source-panel/v1"`, `task_id: "PAPER-FIND-REP-003"`,
  `source_revision`, `role`, `joint_names`, `angle_units: "degrees"`,
  `time_ms`, and `sessions`.
- Reference `role` is `operator_author_reference`. Each session has `mouse`,
  six-digit `session`, `area`, `trials`, and `models`. Trials contain
  `trial_number` and a 51 × 24 `joint_angles` matrix in the **source trial order**.
  Each of models 1–50 contains `model`, ordered `train_trials`/`test_trials`,
  `author_prediction` (concatenated test-trial time rows), and 24 saved `author_ve`.
- Candidate `role` is `candidate_predictions`. Each session has `mouse`, `session`,
  `area`, and 50 `models`, each containing `model`, the identical ordered
  `test_trials`, and `joint_angles` concatenated in that order. No targets or
  author predictions belong in a participant input packet.

The fixed joint names, sessions and time grid are declared in `scorer.py`.
`tests/test_scorer.py` creates an entirely generated full-size identity/panel
control and failure cases. This is an example schema generator for engineering
use, not scientific observations.

## Remaining qualification and integration

Before same-task author calibration: authenticate all ten original source data
files and eligible trial order, RADICaL rates, ZETA top-100 selection, pre-CV PCA
exposure, native dependency versions and the complete original RNG call sequence;
then execute and independently verify the exporter and saved-VE parity. The code
checks numerical parity but cannot prove the claimed data lineage. Candidate
methods may change architecture while keeping the same observations and evaluation.

Before a paper-win decision: recover/calibrate the original numeric baseline,
freeze candidate and source comparator on identical original folds, preserve
required companion controls, and predeclare the four area/group comparisons,
meaningful effect and paired mouse-level uncertainty. Source Figure 5 summaries
are retained here; these missing decisions are not silently replaced by a new
statistical test.

Integration proposal only: add this component as a source-panel scoring artifact;
retain canonical disposition `source_unresolved`. Do not replace the original
contract, register a new task, or label this as a completed benchmark.
