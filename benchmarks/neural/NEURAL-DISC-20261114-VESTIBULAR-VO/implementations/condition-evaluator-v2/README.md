# Distinct-pair vestibular evaluator

This revision repairs a census identity defect in the preserved
[condition evaluator](../condition-evaluator/README.md). The registered endpoint
requires 35 genuine pair relationships. Previously, different `pair_id` values
could name the same two neurons, even in reversed channel order, while still
satisfying the nominal 35-pair count. The predecessor's generated fixture itself
contained only 28 distinct unordered neuron pairs under its 35 pair IDs.

`evaluate.py` now rejects duplicate `(animal_id, unordered neuron_ids)`
relationships before scoring. A relationship can still have multiple genuine
recording groups, distinguished by session/recording identity. This preserves the
distinction between 35 pair relationships and the number of recording groups.
It does not authenticate a submitted neuron identity or prove simultaneity.

The [normalized v1 schema](../condition-evaluator/SCHEMA.md), command-line
arguments, prediction format and outputs are unchanged. The additional reference
constraint is that every census pair must represent a distinct unordered neuron
relationship. Repeated acquisitions use one census pair ID and separate recording
groups. No source-derived identity may be merged or relabeled to satisfy this
rule without independent acquisition evidence.

The primary endpoint remains per-repeat valid-sample MSE, equal-repeat means
within recording group, and equal-group means within animal-condition. There is
no cross-animal primary aggregate. Singleton diagnostics, exact sample clocks,
training-only prior declarations, whole-submission failure, and unverified
execution/provenance status are unchanged. Mode strings still do not establish
direct, viewer, tool-assisted or frozen-program execution.

Run the evaluator with the same arguments documented for its predecessor,
selecting this directory's `evaluate.py`. Python 3.11+ and the standard library
are sufficient. Run the generated controls with:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-DISC-20261114-VESTIBULAR-VO/implementations/condition-evaluator-v2/test_evaluate.py -v
```

The controls preserve the earlier arithmetic, coverage and failure tests with a
corrected generated census. They also demonstrate that same-order and reversed
pair aliases pass the predecessor and fail this revision, that channel ordering
does not change a valid score, and that separate recordings of the same pair
remain admissible. These are software controls, not neural performance results.

No authentic data or private targets were read to make this repair. The original
MATLAB intake and earlier logical packet work were inspected through source and
closed receipts only. Actual animal/cell/recording identities, repeat clocks,
velocity units, source-to-case preparation, competent comparator production and
protected participant delivery remain unresolved. This component does not qualify
the benchmark or establish a model result. Canonical enrollment is an integration
decision; the predecessor and current task/understanding definitions are preserved.
