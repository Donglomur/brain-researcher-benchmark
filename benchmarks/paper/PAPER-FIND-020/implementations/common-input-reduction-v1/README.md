# Biological common-input arithmetic

This component independently reduces supplied biological graph quantities for
Figure 5 and Extended Data 14 of PAPER-FIND-020. It fills a numerical part of the
restored biological reproduction target. It does not replace that target with
RNN accuracy or prospective edge prediction, and it cannot establish improvement
of a biological finding.

The [paper's common-input Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11981947/)
define postsynaptic similarity using products of the two outgoing edge weights.
The [pinned author implementation](https://github.com/cajal/microns-funconn-2025/blob/bc9302a21443453b1f39819676f2388e91bd43a3/funconnect/compute/common_inputs.py)
provides five weight families, a ten-connected-post selection, both post–post
and pre–post summaries, and three observed/expected contrasts. The implementation
here reproduces that reduction algebra independently; it neither fits the models
that generate expected weights nor supplies their historical values.

## Operator interface

`reduce_common_inputs(expected_support, group_records)` accepts an independently
frozen operator roster keyed by `(projection, pre_id)`. Each value lists the exact
postsynaptic IDs available for that group. A participant must not choose this
roster. Its presence does not authenticate the scientific cohort.

Each group record contains:

- `projection`, `pre_id` and `edges`. Every edge has `post_id`, `population`, and
  the five fields in `WEIGHTS`.
- `post_pairs`: every unordered pair of listed posts exactly once, with its
  correlation. Reverse orientation is accepted, duplicated reverse entries and
  diagonal entries are rejected.
- `pre_post`: one presynaptic–postsynaptic correlation per listed post.

The caller must provide the source-qualified correlations and graph rows. IDs
are exact strings with no implicit cast or cross-release join. Whole groups,
posts and pairs must match the operator roster. Unknown or missing fields, NaN,
infinities, negative weights, fractional observed synapse counts, self-edges,
duplicates and out-of-range correlations fail. Values are never clipped.
Numeric inputs must be built-in Python `int` or `float` scalars, excluding
booleans. Fractions, Decimals and library scalar subclasses need an explicitly
qualified upstream conversion; this interface does not coerce them. Integer
conversion that loses information also fails, before arithmetic. These rules
prevent coercion from erasing negative support, changing a count, or hiding a
correlation just beyond its allowed range.

The reducer reports each original group separately. It applies the recorded
connected-count threshold before filtering positive weights within each family.
Groups below that threshold remain explicit as ineligible. Groups whose positive
weight support cannot define a pairwise mean remain explicit as undefined;
they cannot become complete by disappearing from a report. This explicit
undefined representation is a verifier decision, not a claim that the author
program returned such an object.

For each eligible group the output contains five distinct weight summaries and
six within-group differences: total, axonal and synaptic comparisons for each of
the two relations. There is no pooled scalar, p-value, replication count,
acceptance tolerance, superiority threshold or improvement pass. Projection
labels in generated tests are illustrative spellings, not a recovered source
label mapping.

Positive weights are normalized in log space before summation to avoid overflow
in pair products. This preserves the mathematical weighted mean; bitwise parity
with the author's NumPy operations is not promised. The generated controls check
the ordered-pair equation independently, unequal weights, all-group identity,
source-threshold placement, zero support, reordered rows and malformed inputs.

## Remaining source and scientific limits

The pinned code's variable setup includes an in-vivo correlation in addition to
the three features described in the common-input Methods. The script passes that
list into its fitting routine. This observed difference requires adjudication
before an original-model rerun; the reduction module does not resolve it.

The node/edge revision, filtered identities, correlations, fitted predictions,
numeric reference tables, uncertainty implementation and justified reproduction
agreement remain independently unqualified. No raw pickles are opened here.
No R fitting or author program runs on import. A supplied expected-weight column
is not evidence of a competent pairwise-null fit. Same-input pre–post fidelity
controls must accompany any eventual common-input claim.

All groups remain observations from the original single reconstructed mouse;
different neurons, projections and edges are not independent mice. Higher
weighted similarity, a larger contrast or a smaller p-value is not an invented
improvement criterion. The two information conditions must eventually use the
same admitted data and evaluator in separately recorded episodes. Neither
condition, full original-data reproduction, nor a native execution environment
is delivered by this arithmetic component.

## Validation and integration

`test_common_input.py` has ten generated checks. The private construction ran
them through the existing shared test pool, followed by affected-method
checks for finite-float overflow and independent-review numeric-coercion cases. Evidence
and costs, including every attempt, are in the external task handoff. These
checks use no authentic observations.

For an integrated package, the direct command is
`python -I -S -B benchmarks/paper/PAPER-FIND-020/implementations/common-input-reduction-v1/test_common_input.py`.
The sole integrator still needs to enroll that command and these new files in
the component/ownership registry. No central binding or readiness field changes
are proposed. This is one new component of an existing task, not a new benchmark.
