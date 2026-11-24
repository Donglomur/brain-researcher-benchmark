# Released author-output reference rescore

This trusted operator route scores the original UMBRAE grounding outputs without fabricating the four-arm candidate/control contract. It was used, byte-for-byte, for the [complete released-reference rescore](../../docs/released-author-reference-rescore-20261124.md).

The input manifest has schema `umbrae-released-reference-inputs/v1`. It binds `annotation`, `category_groups`, `responses` (`S1`, `S2`, `S5`, `S7`) and `sources` (`grounding`, `source_alignment`, `author_evaluator`). Each file pin contains exactly `path`, `bytes`, and `sha256`; paths must be absolute, canonical, ordinary non-symlink files. The author evaluator is provided separately, with its [immutable identity](https://github.com/weihaox/BrainHub/blob/d8880b247465576715cf08dacbc5167851ed6820/eval_bbox_rec.py) recorded in the result. The annotation and response bodies remain operator-side.

The CLI is:

```text
python -s -B reference_rescore.py --manifest MANIFEST --manifest-bytes N --manifest-sha256 SHA256 --output NEW_OUTPUT
```

Use the declared compatible CPU Torch/torchvision environment, one numerical thread, a clean environment and an explicitly fixed `PYTHONHASHSEED`. Do not use `-I` or `-E` for the scoring child, because they ignore that hash seed. The measured operator used owned temporary/cache locations and an empty `-X pycache_prefix` with `-B`. The two prespecified passes were seed 0 with the full source and keyed diagnostics, then seed 1 with `--source-only`. Keep both results regardless of table agreement. This CLI itself supplies no timeout or operating-system resource isolation; the measured operation used a separately reviewed owned process guard with a complete 600-second work / 60-second closure budget.

The route requires the original 982-image / 2,419-query annotation support and fixed category groups. It preserves within-category first-box selection. Missing response identities remain incorrect on the keyed denominator; unknown identities are rejected. The original source's image-count assertion and independent dictionary/set traversal are retained separately, with no silent padding or reordering. Invalid geometry, source rejection, positional mismatch and precision differences remain diagnostics.

Output contains aggregate metrics, support/ordering diagnostics and input pins, including operator file paths. Sanitize local paths before publication. It contains no model generation or candidate improvement decision. A complete numerical panel alone does not authenticate historical model execution, the NSD/stimulus join, protected participant execution or benchmark readiness.

The six generated controls exercise input mutation/duplicate keys, symlink refusal, fixed-denominator missing answers, first-box/index scope, unrepaired source order and original extraction behavior. They do not establish scientific performance.

The observed agreement applies only to these released outputs; it does not establish interchangeability of the original float32 and keyed scorers for future candidate predictions.
