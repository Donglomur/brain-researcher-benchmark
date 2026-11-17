# Complete declared-roster scoring

This version repairs admission of incomplete NEURAL-091 exported packets. The
preserved [v1 evaluator](../initial-evaluator-v1/evaluator.py) validates submitted
prediction keys against the current query table, but does not reconcile that
table with the protected `source_roster` or its exclusions. Deleting a query
repeat and its target, then recomputing `public_sha256`, can therefore produce a
finite score for an incomplete declared cohort. The generated regression test
retains this counterexample and requires v2 to reject it.

`complete_roster.py` checks that every declared session/unit/presentation is
represented exactly once by an observed row, a whole-presentation exclusion
(`invalid_stimulus` or `temporal_guard`), or a unit-specific
`zero_valid_exposure` exclusion. Missing training rows, missing units, unknown
identities, duplicate exclusions and exclusions overlapping observations fail.
The reconciliation groups units by presentation and does not materialize a
Cartesian set of every potential observation.

The public table must also retain every held family for every calibrated unit.
Rows for the same session/presentation must agree on stimulus, timing, mouse,
condition and pre-onset state; exposure and counts remain unit-specific. A
session-local condition cannot cross stimulus families. Unknown public
top-level fields are rejected so accidental source/target attachments cannot
pass this check. The packet schema and all source-roster digests remain v1.

The scorer then calls the preserved v1 implementation. Spike counts, valid
exposure, training-only controls, mouse-macro Poisson bits per spike, held-family
breakdowns, zero-rate dispositions and mouse bootstrap are unchanged. The
output adds only `declared_roster_coverage`, with observation and exclusion
counts. Source preparation and control fitting continue to use v1.

From the repository root, score an existing operator-owned export with:

```sh
python3 -I -B benchmarks/neural/NEURAL-091/implementations/complete-roster-evaluator-v2/complete_roster.py --public public.json --private private.json --predictions predictions.json --output score.json
```

Keep protected files outside participant access; this command is a scorer,
not an execution sandbox. During the parallel construction wave, all Python
checks must run through the coordinator's shared test pool. The task-local test
suite uses generated observations only and includes complete v1 preparation,
all three exclusion types, the preserved omission counterexample, identity
conflicts, target-key failures, and a CLI round trip.

## Source and qualification limits

The source dependency is the unchanged v1 evaluator, SHA-256
`16606e98d575cce41cf18c0b8b20b3f6b313bccf1ec94bcfd52286c7d56153d4`.
Its [source mapping](../initial-evaluator-v1/COMPONENT_SOURCE.json) records
[AllenSDK v2.16.2](https://github.com/AllenInstitute/AllenSDK/tree/a9b5c685396126d9748f1ccecf7c00f440569f69),
commit `a9b5c685396126d9748f1ccecf7c00f440569f69`. This repair makes no new
claim about raw SDK source-byte verification or native NWB compatibility.

Reconciliation proves coverage relative to the **declared** roster and audit.
It cannot verify that the initial roster contains every native presentation,
that exclusion reasons are true, that source hashes match recording bytes, or
that protected targets are authentic. An operator who edits both roster and
audit can still redefine the declared population; external frozen-protocol and
native-source authentication remain required. This version does not introduce
a new scientific endpoint, stimulus representation, baseline model, or access
condition. Genuine cohort preparation, a competent stimulus-transfer reference,
protected participant execution and scientific qualification remain absent.
No authentic recording, historical solver target, model, or native numerical
preparation was used for this repair.

Tool/model/pipeline construction and native interpretation are separate neural
outcomes. This component improves admission of outputs from the former; it does
not measure native interpretation. A future comparison must retain matched
cases and report each access condition separately.
