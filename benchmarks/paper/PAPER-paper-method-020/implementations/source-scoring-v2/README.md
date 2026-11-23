# NEURONA source scoring paths

This additive component makes the two author scoring paths executable from complete, operator-held traces. It preserves the prior all-query evaluator and original contract. It does not run the author model or establish Table 1 reproduction or improvement.

The `train_hop=all`, CSI1 source training monitor omits queries whose parsed concepts are absent from the training domain. It counts a returned null execution as incorrect and has no catch around the model call: an exception prevents a completed score. Each eligible question is evaluated separately, so the monitor is question weighted.

The source posthoc functions omit exceptions, additionally restrict T/F questions to one through three domain concepts, and construct T/F confusion matrices by mapping every prediction except the literal token `yes` to `no`. Vocabulary scoring uses exact token equality and includes predictions outside the observed answer set in its denominator, although those predictions are absent from its confusion-matrix visualization. `Movement` supplies the paper's Action companion; `Thing` and unclassified vocabulary answers remain in the overall denominator. Combined posthoc accuracy weights T/F and vocabulary by their retained question counts. These distinctions can change scores without changing model predictions. The source creates each branch's accuracy only when that branch retains a query. If either T/F or vocabulary is empty, its combined calculation has a missing metric. Accordingly, `posthoc.Overall.accuracy` is null, `source_aggregate_defined` is false, and `missing_source_branches` names the missing branches. Counts, query identities and category results remain available; `pooled_accuracy_diagnostic` retains the arithmetic over surviving queries separately. This diagnostic is not substituted for the unavailable source Overall. Both standalone and six-cell comparisons withhold Overall deltas in this case, even when surviving query IDs match. Nonempty branches establish only that the combined arithmetic is defined, not that plotting, logging or native execution completed.

The scorer reports both paths, every inclusion/exclusion decision, and the original category companions. `compare` reports reproduction distances from the published anchors separately from candidate-minus-reference differences. It withholds each paired difference when its included query IDs differ. These are numerical diagnostics; the publication-identical query population, checkpoint and invocation are still unauthenticated. No tolerance, win threshold or confidence interval is invented.

## Operator interface

Python 3.10+ standard library only. Run from this directory:

```sh
python3 source_score.py manifest.json candidate-run.json vocabulary.json > operator-score.json
python3 source_score.py manifest.json candidate-run.json vocabulary.json --reference reference-run.json > operator-comparison.json
```

All manifests, source traces and output reports are operator-only. They contain answers or identifying metadata and must remain outside Git and participant environments. The CLI reads JSON with duplicate-key and nonfinite-literal rejection. It never loads NPY/pickle, contacts a service or executes a model.

`manifest.json` contains:

- `schema`: `neurona-source-trace/v2`; explicit Boolean `engineering_fixture`; the pinned `source_code_revision` and `data_revision` from [provenance.json](provenance.json).
- `training_manifest_sha256` and `train_domain_functions`: the frozen complete training-input binding and the author's ordered `list(train_domain.functions.keys())` output after the actual query transform. These declarations need independent authentication.
- `records`: every original test record, each with its `path`, native payload `source_sha256`, and complete ordered `queries` array. Each query has a unique opaque `id`, `query_sha256`, original string `answer`, and ordered `domain_functions` from `create_domain_from_query([query])`. List position is its original query index. Do not deduplicate repeated query strings.

The first three domain functions must be exactly `equal`, `greater_than`, `less_than`; the remaining names define the source's concept count and eligibility. A source parse failure can leave a zero-concept or partial domain. Preserve the actual returned function list. This component deliberately does not replace the native parser with a regular-expression approximation. The production manifest must match the exact 84 CSI1 test paths bound by the historical inventory. Its observed question count is reported against the paper's 2,095 count, never forced to match or presented as payload authentication. Reduced generated fixtures require `engineering_fixture: true`.

Completeness here means every query declared by the caller is scored or accounted for. The 84-path check and caller-supplied hashes cannot prove that per-record questions were not dropped, that answers/queries match native bytes, or that a count of 2,095 identifies the publication set. An independently authenticated conversion and query census are still required.

`vocabulary.json` is the exact ordered decoder vocabulary. Each run includes `manifest_sha256` and `vocabulary_sha256`, calculated as SHA-256 of UTF-8 JSON with sorted object keys, compact separators, unescaped Unicode and no nonfinite values. It also includes `checkpoint_sha256`, an explicit `selection_policy`, `train_hop: "all"`, `neural_condition` (`neural`, `no_neural`, or `shuffled_neural`) and `access_condition` (`paper_data` or `paper_data_author_code`). These record separate participant conditions; they do not attest isolation, permitted access, model execution or source policy equivalence.

Each run has two complete arrays, including entries for skipped queries:

- `training_monitor`: objects containing exactly `id`, `outcome`, and `execution`. Execution uses the [predecessor's structured decoder interface](../initial-evaluator-v1/README.md). A `returned` null execution scores zero. A `raised` call aborts this pass; all subsequent entries must be `not_called`.
- `posthoc`: objects containing exactly `id`, `outcome`, and `pred_answer`. `returned` carries the source's `outputs['pred_answers'][0]` string. `raised` records a caught exception, including the indexing failure caused by a null execution's empty `pred_answers` list. `not_called` is required for questions the source excludes.

The allowed outcomes are `returned`, `raised`, and `not_called`. Uncalled/raised rows have null values. Both passes must cover every declared query exactly once. Preserve separately observed passes: the training monitor and final posthoc functions need not have used the same checkpoint or execution outcomes historically. To use this single-checkpoint interface for a source reconstruction, collect both passes at the same frozen checkpoint; it does not reconstruct an earlier checkpoint-selection trajectory. The source's historical best-test selection remains disclosed and is not silently imposed on a new candidate.

## Verification and remaining qualification

Twelve generated controls exercise independently calculated 5/10 training-monitor versus 5/6 posthoc accuracy, T/F token coercion, asymmetric hop gates, exact category denominators, source aborts, missing/duplicate records, bindings, production population refusal, false improvement caused by dropped failures, and missing-branch aggregate refusal. They run through the wave's shared lightweight test pool. No authentic data or model execution was used.

Native payload conversion, the complete 2,095-query reconciliation, stimulus/image aliases, native parser traces, original selected checkpoint and configuration, source transforms/atlas, participant isolation, matched no-neural/shuffled-neural resources, a separately trained text-only baseline, clustered uncertainty, and a scientific acceptance rule remain unresolved. Source-code inspection and this scorer close a software-semantic gap; they do not qualify the benchmark, reproduce the paper, demonstrate improvement or establish current SOTA.

One `score` call covers one declared neural/access condition. A full evaluation still requires matched neural, no-neural and shuffled-neural executions in each intended paper+data versus paper+data+author-code access arm, with independently checked resource equality and delivery. This component has no complete-suite aggregator or execution attestation. The predecessor's prospective control preparation remains available, with its distinct denominator/domain policy preserved.
