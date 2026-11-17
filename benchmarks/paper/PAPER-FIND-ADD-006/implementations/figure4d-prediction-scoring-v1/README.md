# Figure 4D prediction scoring component

This component calculates binary context-decoding diagnostics from operator-owned prediction exports for **context conditional on actual position**, the original Figure 4D endpoint. It does not use the unfilled accuracy array returned by the released conditional decoder. It is separate from the unchanged historical Ward-tree reconstruction implementation.

`scorer.py` uses only the Python standard library. It performs no training, data preparation, download, model call or private-target discovery. It is an operator analysis tool: the CSV itself supplies `Real_label`, so this is **not a secure candidate-facing grader**. No authentic predictions have been scored during development.

## What is executable

For each of the original 100 bootstrap repetitions, the scorer calculates:

- Exact-match binary context accuracy and normalized absolute label error. These are complements for any two distinct context symbols; no numeric ordering of `A` and `B` is needed.
- Conditional scores as an equal-weight mean of the per-position scores, following the paper's Methods. The pooled observation score is retained separately to expose occupancy weighting errors.
- Global scores over all prediction observations, consistent with the released `SVM_global` call to `accuracy_score`.
- Counts, mismatch totals and missing-condition support for every repetition. Repeated bootstrap observations remain repeated observations. No deduplication occurs.

A missing conditioning group leaves the conditional score undefined. It is never silently removed, counted as zero error or replaced by the pooled observation score. This conservative diagnostic policy is **not asserted to be the historical paper's missing-group policy**. A completely missing repetition is rejected. The mean across all 100 repetitions is explicitly a descriptive summary, not a recovered paper aggregation.

The full-panel entry point requires all five named rats and all 25 source recording dates, plus global, conditional, global shuffled-context, conditional shuffled-context and conditional shuffled-position exports for every session. It produces per-session results; it does not invent a cross-session aggregate, baseline value, uncertainty interval, minimum gain or improvement decision.

## Operator input

Run from this directory with an external manifest and redirect output to external operator storage:

```sh
python3 -I -S -B scorer.py /operator/figure4d-exports.json > /operator/figure4d-diagnostics.json
```

The manifest has exactly these top-level keys:

```json
{
  "schema": "hierarchy-figure4d-export-panel/v1",
  "context_labels": ["A", "B"],
  "condition_labels": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
  "sessions": []
}
```

Populate `sessions` with all 25 `(animal, date)` identities in `scorer.ROSTER`. Each entry has `animal`, `date` and `exports`. Every export key in `scorer.ARMS` is mandatory. An export specification has exactly `path`, `condition_column` and `selectors`, for example:

```json
{
  "path": "jc233_170220_conditional.csv",
  "condition_column": "Conditional",
  "selectors": {}
}
```

Paths resolve relative to the manifest. The minimum CSV columns are `Real_label`, `Pred_label`, `Boot_rep` and the explicitly selected condition column. `Boot_rep` must be an integer string from `0` to `99`. Extra monitored columns are permitted but do not supply a trusted identity or change the score. Malformed row lengths, duplicate column names, undeclared labels, padded empty prediction rows and omitted repetitions fail.

For the released combined `SVM_both_perPC` export, use `condition_column: "Cond_label"` and selectors such as `{"Decoder":"cond","PC":"92"}`. **92 is only a format example, not an authorized neuron count.** Each session's intended full-feature count must be recovered and independently verified. The source arm labels are `single`, `single_decshuffle`, `cond`, `cond_decshuffle`, and `cond_condshuffle`. Explicit selectors prevent accidental averaging over feature counts or mixing decoder arms. Selectors cannot filter labels, predictions, repetitions or conditioning support. Reusing the same resolved export and selectors for multiple sessions/arms fails.

The nine condition strings shown above are a schema illustration. The paper discusses coarse position labels, while the example defaults to a different fine-position field. A concrete Figure 4D support choice has **not** been recovered. The operator must declare the expected labels; the scorer deliberately does not infer a smaller support from whatever rows happen to appear. Successful scoring does not verify that declaration.

## Scientific limits

The original protocol remains 100 stratified 70/30 PV splits with stratified replacement sampling **after** partitioning, matched across global, conditional and shuffled conditions. Matching `Boot_rep` values do not establish matching source PVs. Released exports omit the full draw identity ledger, so this scorer cannot verify partition separation, shared draws, 40-trial/90-bin input support, speed equalization, cell identity, or any training boundary. It generates no substitute split.

The source Methods describe a mismatch quantity as “accuracy,” while source global code reports exact-match accuracy. Both mathematical quantities are reported without deciding which was plotted. The exact published baseline, complete speed-equalized preparation route, conditional position resolution, source missing-group policy, original session/rat aggregation and rat-level uncertainty remain unresolved. The original five-rat biological replication is retained; 100 bootstrap repetitions are not 100 animals.

`SOURCE_AUDIT.md` records the inspected defects and source locators. `SOURCE_PINS.json` binds the reused local source bodies; no download was needed. This component advances prediction-derived scoring only. The task remains source-unresolved, with no new author calibration, candidate trial, paper win or SOTA claim.

## Generated checks

`test_scorer.py` uses invented CSV rows and temporary files only. Its unequal-occupancy oracle distinguishes conditional group averaging (`1/9` accuracy) from pooled observation averaging (`1/2`), tests multiplicity, missing groups/repeats, corrupted exports, explicit feature/arm selection, binary relabeling and the complete 25-session/five-arm path. Execute it only through the reviewed shared lightweight test pool during this revision. Test results and exact component hashes are recorded in the frozen handoff.
