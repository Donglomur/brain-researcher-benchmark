# Prospective WFCI1 paired output scoring

This owner-side join turns two complete held-role prediction streams from the existing whole-trial inference interface into comparable endpoint vectors. It does not run models or choose targets. The full prospective 248-trial WFCI1 and 412-trial WFCI2 census and ten folds are admitted before scoring one WFCI1 validation or test role.

`score_pair` takes independently frozen owner binding bytes and SHA256, the census and split bytes, the existing normalization receipt, both existing inference receipts, an explicit owner mask declaration, and four seekable binary streams: normalized held neural input, complete owner behavior targets, candidate predictions and comparator predictions. The owner binding pins every metadata operand, selected fold/role and both method labels. Input and target hashes and extents come from the pinned normalization receipt. The prediction receipts must identify the same input and complete support. Hash agreement binds bytes supplied by the owner; it does not authenticate their scientific origin.

Both prediction streams are checked completely before protected behavior targets are read. Every prediction must match the exact original source index, trial, offset and role, with a full 1×128×128 field and fourteen behavior outputs. Neural truth is the authenticated selected input. The existing owner target format contains behavior only; both validation and test target roles authenticate even when only one is scored. Held targets and the evaluator must remain outside candidate processes and mounts. This trusted Python API does not enforce that isolation.

The explicit mask document has schema `sbind-owner-brain-pixel-selection-v1`, task and assay IDs, the census's original `source_sha256` and `representation_sha256`, and an ordered `pixel_indices` array. The owner must precommit its complete bytes and hash before candidate evaluation. The consumer cannot choose a mask. This new declaration binds a supplied selection; it does not establish that selection as the historical paper mask.

The return value preserves the existing endpoint kernels' exact `MetricResult` fields for each candidate/comparator: fourteen per-channel behavior MSEs and one neural MSE per supplied brain pixel, in normalized units. There is no pixel/channel averaging, threshold, scalar winner or claim of improvement over the paper. Method IDs are labels, not evidence that a comparator reproduces the authors' method. Historical folds, reset/preprocessing provenance, authentic data, author-model parity, comparator competence and process isolation still require separate qualification.

All metadata and record sizes are bounded. The owner supplies maximum total serialized stream bytes and complete role frames. Exceeding a limit rejects the entire evaluation; it never trims frames. Parsed role operands are materialized, so these limits are not a qualified resident-memory bound for authentic data. Failed evaluation returns no score; the caller handles durable publication externally.

Dependencies are exact reviewed sibling modules listed in `DEPENDENCIES.json`. The owner runner must install only these frozen source paths on its Python import path. The maintained test checks their byte identities before import and runs with the isolated standard-library Python configuration:

```
python3 -I -S -B test_paired_scoring.py
```

The test builds generated in-memory records and complete metadata, checks paired vectors against independent arithmetic, and attacks receipt/support/hash/role/normalization/mask boundaries. It performs no authentic-data run, model inference or fit. No existing producer/kernel suite is replayed.
