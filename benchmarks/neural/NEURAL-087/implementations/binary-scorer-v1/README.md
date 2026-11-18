# Recovered binary connectivity scorer

This component restores executable scoring for NEURAL-087's historically
declared binary endpoint from the local historical source closure. It does not
restore the empirical packet, establish its eligibility, deliver a participant
runtime, or qualify the benchmark. No authentic observations, targets or model
predictions were read while constructing this component.

`scorer.py`, `contract.py` and `io_utils.py` are byte-identical source recoveries;
their hashes and provenance are in `SOURCE_LINEAGE.json`. `score.py` adds an
externally frozen binding digest, exact historical counts and inherited query
endpoint-partition checks to the recovered operator CLI. The original runtime
declaration and canonical task contract are unchanged.

## Invocation and trust boundary

Using Python 3.10 or later with its standard library, invoke from a trusted
operator environment whose working directory and Python path are controlled:

```sh
python3 -B score.py \
  --binding BINDING.json --binding-sha256 OPERATOR_FROZEN_SHA256 \
  --roster query_roster.json --targets targets.json \
  --anatomy anatomy.json --joint anatomy_plus_in_vivo.json \
  --output scores.json
```

The binding must follow `neural087_prepared_binding_v1`, with task ID
`NEURAL-087`, historical counts (97717 fit, 7429 validation, 105146 total train,
6691 query), and exact `bytes`/`sha256` descriptors for `query_roster` and
`query_targets`. The operator freezes the binding digest before participant
execution. A hash supplied by the participant supplies no trusted provenance.
This loader does not authenticate the biological provenance of any supplied
binding. Raw data, endpoint IDs, target tables and scores belong outside Git.

Roster rows are exactly `edge_id`, `pre_id`, `post_id`, `projection`; the source
contract preserves the inherited NEURAL-088 node partition. Each paired
submission has `{"schema_version":1,"predictions":[...]}`, with each prediction
exactly `edge_id` and `probability`. Both views must contain every query edge
exactly once. Order may differ. Targets are ordered rows with `edge_id` and
integer `connected` in `{"schema_version":1,"targets":[...]}`.

Before any input body is read, a metadata-only preflight rejects aliases
between the target and every earlier input role, and between the output and
every input role. It checks resolved paths and existing-file identity, including
symlinks and hardlinks. Both complete submissions are then validated before the
target file is opened.
Malformed predictions return exit 2 with an invalid-submission result and zero
private reads. Invalid operator bindings, roster or targets raise errors and
produce no score. The output must be a fresh path. This is operator software,
not a process sandbox: keep the target-bearing paths and scorer inaccessible to
participant programs and freeze both predictions before invoking it.
The operator must keep input paths immutable throughout execution: this
preflight does not defend against concurrent hostile filesystem changes. The
private-loader counter counts that callback alone; the alias controls are
independently tested with an audit hook that traps every fixture-body open.

## Exact metric scope

The primary is joint-view log loss: average unweighted pair losses within each
presynaptic neuron, then average those neuron means equally. The historical
protocol has unit pair weights; nonuniform sampling weights are unsupported by
this recovered implementation and must not silently be ignored. Logarithms are
natural (nats). Endpoint probabilities 0 and 1 are allowed; a confidently wrong
prediction gives positive infinity, encoded as a status with JSON null value,
without clipping. No-positive average precision and infinity-minus-infinity
contrasts are explicitly undefined.

Companions include edge-weighted tied-threshold average precision (a step
precision–recall integral, not trapezoidal AUPRC), equal-neuron Brier error,
per-neuron loss and fixed projection strata. The candidate anatomy-minus-joint
contrast is descriptive; weakening anatomy cannot improve the absolute primary.
Fixed-reference prediction comparisons are implemented by `reference_compare.py`
as described below. Fitting and scientifically qualifying the independent
anatomy-only and joint references remain unresolved.

`test_scorer.py` uses generated fixtures only, including a full 6691-row operator
control. It tests arithmetic, paired completion, target access ordering,
binding identity, partition refusal and real-CLI path-alias rejection before
any input body is opened. Tests are software evidence, not a new
study result, empirical score or validation of source reconstruction.

Remaining scientific gaps are the version-consistent functional/EM mapping,
historical pair-ID authentication and negative eligibility; raw recording
preparation; matched participant delivery and reference comparators; and
appropriate dependent uncertainty. This selected, exposed, single-mouse
cohort cannot establish independent-animal generalization or direct raw-neural
interpretation. The source audit's reconstruction and selection limitations
continue to apply.

Native interpretation and building or using tools, models and pipelines remain
separate first-class outcomes. This scorer advances the pipeline evaluation
route; it records neither a native interpretation result nor a participant's
ability to build a successful pipeline. Those need matched-case observation
delivery and actual controlled responses or program execution, respectively.

## Independently frozen reference comparison

`reference_compare.py` extends the same arithmetic with an externally fixed pair
of reference prediction vectors. It retains the candidate's absolute joint-view
log loss as the primary. Additional outputs are the fixed anatomy-minus-fixed
joint contrast and, for each information view, fixed-reference minus candidate
loss. Positive same-information gain means lower candidate loss. All contrasts
use equal-presynaptic weighting and retain negative, infinite and undefined
results. They do not estimate uncertainty or establish scientific improvement.

The trusted operator supplies a reference JSON document with exactly:

```json
{
  "schema": "neural087_fixed_reference_predictions_v1",
  "task_id": "NEURAL-087",
  "query_roster_sha256": "ROSTER_COMMITMENT",
  "reference_protocol_sha256": "FROZEN_REFERENCE_RECIPE_SHA256",
  "views": {
    "anatomy": {"schema_version": 1, "predictions": []},
    "anatomy_plus_in_vivo": {"schema_version": 1, "predictions": []}
  }
}
```

The empty arrays above illustrate the envelope only; each real view must cover
every exact query edge. `roster_commitment(rows)` commits to ordered roster
content, including neuron identities and grouping. It hashes the UTF-8/ASCII
canonical JSON (`sort_keys=True`, compact separators, `ensure_ascii=True`,
`allow_nan=False`) after the literal prefix `neural087_reference_roster_v1\n`.
The operator freezes the exact reference-file SHA256 and the reference recipe
before candidate evaluation. Changes to even whitespace require a different
file commitment; supplying a newly chosen digest cannot prove prior freezing.

Invoke from a trusted Python environment with controlled working directory and
import path:

```sh
python3 -B reference_compare.py \
  --binding BINDING.json --binding-sha256 OPERATOR_FROZEN_SHA256 \
  --roster query_roster.json --targets targets.json \
  --anatomy anatomy.json --joint anatomy_plus_in_vivo.json \
  --reference fixed_reference.json --reference-sha256 FIXED_REFERENCE_FILE_SHA256 \
  --output comparison.json
```

The CLI reuses the unchanged complete 6691-pair roster binding and inherited
endpoint-partition checks. Its metadata preflight also rejects reference/target
and output/input aliases, including existing hardlinks. It validates all four
complete probability vectors before one protected target-file read. A bad
operator reference raises an error without a score; a malformed candidate
produces an invalid-submission result with zero target reads. The in-memory
`compare` core permits smaller bounded generated rosters for arithmetic tests;
that core alone is not complete historical-population admission.

This component binds selected objects and computes comparisons. It does not
authenticate fit history, recipe competence, information-set equality, absence
of label leakage, freezing chronology, negative-pair eligibility or source
cohort membership. Those require separate operator evidence. Keep the reference
and target-bearing paths outside participant access, and keep inputs immutable
through evaluation. This remains trusted operator software, not a sandbox.
Neither control success nor positive arithmetic gains promote task readiness,
prove native neural understanding, or establish population-level or SOTA claims.

`test_reference_compare.py` adds generated controls for fixed-reference integrity,
all-four-submission target-access ordering, exact historical-sized support,
equal-presynaptic arithmetic, negative and undefined contrasts, and reference
path aliases. Existing scorer source and its historical recovery hashes are
unchanged. CI must enroll this new test file; it is not implicitly covered by
the existing `test_scorer.py` command.
