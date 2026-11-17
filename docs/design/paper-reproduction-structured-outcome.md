# Opt-in structured reproduction metadata

`src/neurobench/paper_reproduction_v2.py` represents source-indexed arrays without
turning them into a category, a selected peak, or an invented scalar average.
It adds `paper-reproduction/v2`, `paper-reproduction-result/v2` and
`paper-outcome-receipt/v2`. The existing v1 files, schema dictionaries, contracts
and criteria remain unchanged.

This is a metadata validator. It reads no scientific array, opens no artifact
locator, executes no submitted entrypoint or comparator, and authenticates no
scientific evidence. `scientific_outcome` always remains `unknown`. A successful
metadata check is neither a runnable benchmark nor verified reproduction.

The public API keeps the established signatures:

```python
contract_validate(reproduction_contract, task_id=None)
outcomes_validate(outcomes, reproduction_contract, improvement_contract)
admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt)
summary(outcomes, reproduction_contract, improvement_contract, receipts=())
```

V1 reproduction input delegates directly to the unchanged v1 API. V2 uses its
own strict schemas and receipt envelope; an existing v1 receipt does not silently
gain structured-result support. The outcome bundle remains the existing digest
container. Its version-aware validator still binds both scientific outcomes to
the same source paper, original task anchors and evaluation identities.

## A structured finding describes source quantities

V2 retains the existing scalar/categorical finding checks and adds
`kind: indexed_array_family`. Such a finding contains:

- Its source description, evidence and verified/unresolved status.
- `representation`: a named source family, immutable family identity and exact
  named member specifications.
- `expected`: an authenticated reference-manifest descriptor, or null while
  unresolved.
- `required_granular_output_ids`: links to computation-policy outputs that cover
  this finding. A shape alone is not computational evidence.
- `comparison`: the separately justified scientific comparison and uncertainty
  policy. No default norm, tolerance, reduction or replication count is supplied.

A finding marked `verified` must supply an expected reference with verified
original-source equivalence. Known source quantities without that target remain
`unresolved`. An unresolved finding may retain a recovered reference descriptor
that explicitly records unresolved publication equivalence; this does not make
the finding or endpoint eligible.

Each member has an exact manifest key and source quantity; ordered named axes;
shape; allowed numeric representation types; units; semantic, support, domain
and derivation identities; source aggregation; and evidence. Axis coordinates
can be explicit labels, a bounded arithmetic grid, an authenticated manifest, or
an explicit unresolved declaration. Coordinate identity hashes are supplied from
real source manifests; the validator never invents one by hashing a shape or
description. Display coordinates and computational coordinates must remain
distinct when the source distinguishes them.

Known axes and shapes can coexist with unresolved artifact identities. Set those
identities, unknown dimensions or representation types to null and keep the
representation unresolved. This can describe a real source limitation; it cannot
make an endpoint eligible. Do not fill unknown identities with zero hashes,
guessed coordinates or nominal source counts presented as measured values.

The domain-policy identity covers source support and nonfinite/missingness
semantics. Legitimate source NaNs are not universally forbidden in external
arrays; neither are they silently dropped or replaced. The independently owned
verifier must check actual values, masks, denominators, transformations and
policy compliance. Nonfinite numbers are rejected in the JSON metadata itself.

## Fixed support and data-dependent collections

Fixed source members must be present exactly once. Missing participants, folds,
conditions or companion families cannot be hidden by substituting equal-shaped
arrays. Ragged source folds can be separate named members with their own
authentic shapes and support identities; padding them into one convenient shape
is not inferred or authorized.

A `data_dependent` member represents a collection such as cluster masks on a
fixed source grid. Its policy declares record-key fields, whether zero records
are allowed, and a source-grounded correspondence rule—or a justified declaration
that record correspondence is not required. Each actual record retains its key,
content hash, representation and support. The full collection has its own
content-manifest hash. Metadata validation checks record-key uniqueness and
complete family presence. A key tuple may legitimately contain the same value in
different fields.

The validator does not require generated cluster IDs or record counts to equal
the reference. Any scientific matching belongs to the separately frozen
correspondence policy and comparator. Zero records may be a valid source outcome;
omitting the whole required analysis family is a different error. The current
collection representation requires each record to share its declared source
grid. It does not invent a general variable-shape matching algorithm.

## Reference identity is not publication equivalence

The reference descriptor distinguishes `publication_historical`,
`current_author_code` and `operator_reconstruction`. It records actual revision,
provenance, source-equivalence status, rationale and evidence. A byte hash proves
which artifact is declared, not that current-code or operator outputs reproduce
the publication. Claimed eligibility requires a verified original-source
equivalence declaration; a trusted reviewer must authenticate that declaration.

The only implemented scientific comparison class is
`numerical_reference_equivalence`. Its policy binds:

- The exact reference manifest and trusted comparison-program identity.
- A complete-family criterion policy and a separate uncertainty-policy identity.
- The source method, independent unit, dependence structure, multiplicity scope,
  rationale and evidence.

These policies must contain the actual independently justified numeric rules,
support treatment, uncertainty design and any required simultaneous coverage.
Their hashes are not permission to omit those rules. The metadata layer does
not read their contents and cannot validate their scientific justification.

Other relational or distributional scientific comparisons are outside this
initial implementation. Use comparison status `schema_limited` with the actual
unsupported class and contract eligibility `schema_blocked` when that is the
operative limitation. This is an engineering limit, not scientific ineligibility.
Genuine source gaps may remain separately unresolved. Do not invent a numerical
reference criterion merely to pass the supported schema.

## Derivation and scientific comparison are separate

The v2 receipt preserves the existing candidate freeze, input/data/code
provenance, independent analysis execution, complete granular output verification,
budget and time-order checks. Its result names every actual structured member,
its source identities and its independently executed output manifest.

That derivation record answers whether the submitted analysis produced the
required quantities on the original support. It does not answer whether the
scientific finding was reproduced.

`scientific_comparisons` supplies a separate independent record for each structured
finding. Each record binds the candidate, contract, outcome bundle, execution,
actual output manifest, result and finding digests, source family specification,
reference descriptor, comparison program, criterion and uncertainty policies.
Its timestamps follow granular derivation verification within final evaluation.
Its decision-manifest hash must identify the actual independently generated
comparison report, including observed comparison values, uncertainty calculations
and the policy-based decision. Every member assessment binds its actual submitted
member digest, expected manifest key, comparison record and correspondence policy.
These per-member report and manifest hashes are opaque identity declarations
here. This validator does not open those reports to establish that a reference
member exists, that record correspondence was performed correctly, or that the
reported numerical decision follows the declared policy.

The comparator owns the declared whole-family criterion. The metadata layer does
not infer it by averaging member statuses, requiring every cell to match, or
choosing a threshold. A complete admitted comparison can declare a mismatch:
`criterion_satisfied` is then false while the scientific outcome remains unknown.
Missing comparison evidence, incomplete support or unresolved criteria yield a
null criterion and rejected admission, not a fabricated scientific failure.

Role names, hashes and a true criterion flag can be forged. Before any scientific
qualification, a trusted operator must authenticate the actual run, inspect/rerun
the submitted analysis, verify source-native derivation and independently execute
the frozen scientific comparison. Printing published curves or supplying a
candidate-authored verification record does not satisfy that requirement.

## Matched information conditions and task counts

The paired paper+data and paper+data+author-code conditions keep the same original
observations, task, evaluator, computational policy and budgets. Source code is
the only supplied-information difference. Candidate code, runtime, static
invocation, reference and comparator-program hashes may coincide across genuinely
independent runs. Run/trace/exposure/execution/freeze/evaluation and scientific
comparison receipts may not be reused across the two conditions.

Reproduction with author code may legitimately include executing that code;
success does not imply invention of the method. Both conditions receive the
paper, so their contrast measures the effect of supplied author-code access,
not learning from the paper. A separately designed paper-context ablation could
help address that attribution question; it is outside the current paired protocol.

`summary` still reports four outcome/condition cells for one task. Author baseline
calibration, software controls and historical attempts do not populate AI cells.
The improvement payload remains its existing version and comparison semantics;
an improvement receipt cannot carry a reproduction comparison as its decision.

## Source cases and current limits

The sequence-filtering proposal requires all 32 original fit rows—including its
18 null-input/null-target controls—and both complete Panel L and Panel M curve
pairs. It distinguishes the integration clock from the plotted linspace and
keeps selected readout counts nominal until actual ordered identities are
recovered. Source epoch/control conflicts, stochastic realization, full empirical
scope and justified comparison criteria remain unresolved.

The preactivation proposal requires complete participant, condition, fold,
train/test-time, omission, theoretical-control, most-likely, confusion, cluster
and Bayes families. Correctness depends on semantic labels, retained-event
support, denominators, source transforms and full inferential context. Adding
this representation does not recover publication-vintage axes, missing producers,
contrasts, references or a qualified scientific comparator.

This implementation migrates no task, changes none of the reviewed special-task
contracts, reads no numerical source payload and establishes no new AI result.
Source-specific adoption and actual verifier qualification require separate
review. Generated tests exercise metadata counterexamples only.
