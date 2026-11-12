# Neuroformer: reproduce a result, then test an improvement (V2)

This package provides the V2 scientific contract component and invented engineering examples.

This is an additive **build-only candidate contract component**, not a ready study or an executed benchmark. The assignment remains one paper, with all 46 slots, 85 condition cells and seven wider families retained in `scope.json`. Every cell retains its holds. The comparison checker currently handles scalar behavior Pearson reports; it does not replace unresolved classification, generated-neural or 5 ms metrics with a convenient score.

## Candidate brief

Reconstruct the declared method from the supplied paper and approved data. Explain the scientific question, preprocessing, temporal support, visible modalities, training/selection rule and metric. Submit runnable source, a configuration and environment specification, a method-change report, and the prescribed ordered prediction artifact. For the improvement stage, propose a change and compare it with a rerun reference under the same frozen protected protocol. Report regressions and undefined metrics as well as gains. A scalar number or a polished report alone is not a completed submission.

The operator must supply the selected cell ID and frozen packet/run contract before any attempt. This component does not invent missing input paths, prediction array shapes, actual split IDs or runtime eligibility. The existing native factory supports source for only two historical lateral cells: speed regression and joint speed/gaze at 100% budget. All other cells remain in the assignment; they are not silently removed from its denominator or advertised as executable.

| Phase | Required comparison | Permitted interpretation |
|---|---|---|
| Released workflow replay | Same historical 10 ms endpoint, row order, first-200 Pearson support, source selection quirks and reference recipe | Discrepancy from an exposed source workflow. |
| Published-result reproduction | A versioned paper target plus authenticated run/method/support/metric mapping, independently checked reference and justified tolerance | A reproduction decision only after those missing bindings are reviewed. |
| Protected improvement | Baseline and candidate rerun on the same protected 10 ms full-support endpoint, with frozen selection and isolated evaluation | A descriptive paired effect on the amended benchmark, pending independent qualification. |

Historical selection and evaluation use the same support. The released code forwards test labels in demonstrations and chooses checkpoints using test losses. This audit does **not** show optimizer updates on test examples. Do not silently repair that path and call the changed result a source replay. Its first-200 metric and a protected all-row metric have different support; comparing their numbers does not establish improvement.

## Access arms

**A — paper and data:** the versioned paper, approved training data and labels, approved validation resources, permitted scientific resources, task contract and permitted query interface.

**B — paper, data and official code:** exactly A's resources plus the selected official repository snapshot. Access to checkpoints is a separate pretraining-resource decision that must match; code access does not silently grant weights, labels or past attempts.

Both arms must have the same data version, split/support, feature policy, noncode resources, evaluation feedback budget and resource budget. Evaluator source, private targets/reference answers and other attempts are excluded from both candidate packets. Full source arrays and operator tools cannot be mounted into a candidate process merely because they exist on the host. Public paper/data exposure and prior code knowledge must be recorded; public data do not become unseen by moving their labels behind an API. An A/B difference is descriptive, not proof that code access caused it. The checker requires protected endpoints for the A/B effect; historical A/B workflow results may still be reported separately as exposed descriptions.

## Frozen protected behavior endpoint

The next concrete implementation priority is the lateral speed-decoding cell under `protected_support_source_amended_10ms`. This prioritization does not reduce the full assignment. Before a run, the operator must resolve:

1. Exact dataset/recording identity, ordered train/selection/evaluation supports, neural and video footprints, temporal exclusion and training-only preprocessing. Medial/lateral labels do not establish independent animals.
2. Feature and target timestamps, permitted modalities and target visibility. Current neural windows and the historical video convention make this retrospective decoding. Neither disjoint endpoints nor a causal transformer mask establishes online forecasting.
3. Training/label/pretraining budgets, actual permitted model resources, baseline recipe, candidate freedom, random seeds and adaptation limits. The case method names the comparator family; `method_identity` records the actual baseline or candidate implementation.
4. A validation-only checkpoint selector with metric, direction, schedule and tie rule; freeze all choices before final queries. Full context must be purged across roles. Selection and evaluation cannot be renamed copies of the same rows.
5. An isolated provider/runner, hidden target store, prediction commitment before scoring, and a fixed evaluation-query/feedback budget. Existing callback ordering and target-free heads are useful components, not proof of isolation.
6. The same full ordered support and metric implementation for both methods. Speed is primary; phi/th are separate unqualified scalar diagnostics until units and appropriate circular treatment are resolved. Do not average gaze and speed, or recordings without biological identities.
7. Before claiming a scientific gain: an independently checked reference, runtime/provenance qualification, exposure review and a prespecified uncertainty unit/design. A single paired seed's positive delta is not significance or SOTA.

The 5 ms bridge is a distinct unqualified contract. Neural generation needs a distinct generated-history and metric/ablation mapping; `true_past=False` in the released path is insufficient because source interval lookup replaces the passed generated history. Those held components must not be collapsed into the speed endpoint.

## Published target versus benchmark target

Two primary versions disagree. [arXiv v4, Table 1](https://arxiv.org/html/2311.00136v4#S4.T1) reports Neuroformer lateral/medial Pearson .95/.97; the [official proceedings PDF, page 8, Table 1](https://proceedings.iclr.cc/paper_files/paper/2024/file/b16e55ac49f93d33a4b87747d5121b64-Paper-Conference.pdf) reports .97/.97. The accompanying `TABLE1_VERSION_AUDIT.json` records text extraction and visual inspection of the proceedings table by the benchmark maintainer. Other table rows agree. `published_targets_v2.json` retains both complete ten-row versions under distinct target IDs, with the accompanying portable audit as an explicit provenance dependency. These are 20 versioned target records, not 20 tasks or results.

No single target is silently chosen. The cause of the discrepancy, associated run/support/recipe identities, tolerance and qualified replay remain unresolved. The paper's bidirectional GRU is not automatically the local released GRU recipe. An exact numerical match on different support does not establish reproduction. This component does not alter the original task package or its canonical manifest. No PDF or rendered page is copied into this component.

## Operator comparison interface

`compare_v2.py` accepts **trusted operator observations**, not candidate self-certifications. `examples/` contains entirely invented records that demonstrate the format. Strings naming support, policies and budgets must refer to the actual frozen study objects outside this checker. Matching those strings or setting a boolean does not independently prove any fact.

Run the small declared-comparison check:

```sh
python3 compare_v2.py examples/reference.json examples/candidate.json --intent protected_improvement
```

Reports retain run, arm, seed, metric/profile, support counts and declared protocol/target identities so speed and gaze cannot become indistinguishable downstream. Native gaze key `th` is retained; an unverified `theta` alias is rejected. The result retains signed candidate-minus-reference Pearson and absolute difference only when declarations match. It blocks historical/protected mixing, different supports/resources/selection policies, unresolved exposure, fake forecasting, undefined scores and unresolved metric substitutions. CLI exit 2 means blocked; malformed records raise a validation error. Exit 0 means internally comparable declarations, **never scientific qualification**. All outputs leave `claim_awarded` and `scientifically_qualified` false and retain the cell's scientific holds.

The API `published_target_gap(observation, target_id)` requires an explicit version, for example `arxiv-v4-table1-lateral-neuroformer` or `iclr-proceedings-table1-lateral-neuroformer`, and can report an explicitly unmapped descriptive gap. It always leaves reproduction pass/tolerance unset. Neither function loads neural observations or computes a scientific metric. Observations use `n_total` for all evaluation rows and `n_scored` for metric support; historical Pearson uses `min(200, n_total)`, protected Pearson uses all rows. Null scores require a reason and yield no effect. These records are not independent evidence of provenance.

Engineering tests: `python3 -m unittest -v test_compare_v2.py`. Tests use invented numbers only; they do not count as baseline or candidate runs. Across-paper denominators and missing-run reporting are handled separately from this task-specific comparison component.
