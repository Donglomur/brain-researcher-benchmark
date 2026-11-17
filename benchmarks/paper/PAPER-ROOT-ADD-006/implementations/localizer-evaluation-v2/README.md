# Localizer accuracy component

`localizer_score.py` scores the original three-outcome held-out localizer accuracy, all supplied train/test cells, class diagnostics, matched-time diagonals, participant SEM, and paired candidate-minus-author maps. It preserves all 21 source participants and reports the paper's 19-person figure cohort separately. The source/script discrepancies are documented in [SOURCE_AUDIT.md](SOURCE_AUDIT.md).

This is a useful arithmetic component at an unqualified operator-export boundary. It does not fit a decoder, manufacture folds, reproduce the paper, certify held-out access, or award an improvement. The old behavioral-prediction evaluator is preserved. The paper's seven folds and 19 participants differ from the deposited code's five folds and 21 participants; both remain visible. Full temporal coverage and exact native exports remain unresolved.

Use an existing Python with NumPy:

```sh
python3.11 localizer_score.py /absolute/operator/manifest.json /absolute/operator/result.json
python3.11 -m unittest discover -s tests -v
```

The output path must not already exist. All work in the parallel construction environment must use its shared test pool. Tests use generated data only.

The JSON manifest contains `schema: "localizer-score/v2"`, the pinned `source_revision` in `SOURCE_AUDIT.md`, `input_kind` (`generated_control` or `unqualified_operator_export`), integer `train_ms` and `test_ms` vectors, `fold_count` (5 or 7), and `participants` in exact `sub-S001` through `sub-S021` order. Times are exact increasing multiples of 10 ms. This interface retains all supplied cells; it does not certify that supplied cells exhaust the original figure. Sparse or cropped grids cannot claim full reproduction through this component.

Each participant provides 420 unique `trial_ids`, 420 `image_class` labels (60 examples each of 1–7), and 420 `fold_id` values. Every fold must contain every image class; five-fold packets must contain exactly 12 examples per class per fold. Seven-fold assignments are externally supplied declarations, not recovered originals. Source coding is `1=O1`, `2=O2`, `3=OS`, `4..7=C1..C4`.

`author_logits` and optional `candidate_logits` each specify a relative NPY `path`, its `sha256`, and `trial_order_sha256`. NPY files contain finite numeric arrays with axes trial × train-time × test-time × classifier. Either three outcome channels or seven source-storage channels are accepted; only the first three compete for outcome accuracy. Numeric read-only memory mapping avoids loading the entire multi-participant panel at once. Pickled objects and paths outside the packet directory are rejected. The schema assumes a trusted local operator preparing bounded files; it is not an untrusted-upload sandbox.

The order hash is SHA-256 of compact UTF-8 JSON (`sort_keys=True`, `separators=(",", ":")`) containing the participant's `participant_id`, `trial_ids`, `image_class`, and `fold_id`, plus the manifest's `train_ms`, `test_ms`, and `fold_count`. Each arm must independently bind to that identical ordering. Hashes detect changed bytes/declarations; they do not authenticate a claimed native join or prove that prediction training excluded held-out trials. Labels and folds belong to the operator packet and must not be supplied as candidate-time observations. Candidate predictions must cover all 21 participants if present.

The executable generated example is `tests/test_localizer_score.py::packet`. It uses small time axes solely to test arithmetic and refusal paths. No synthetic example is reported as an original full-map evaluation. Results retain participant maps and both cohort summaries. Paired differences use the 19 paper participants; their SEM is descriptive, without a confidence interval, multiple-comparison procedure, selected latency, minimum effect, or win threshold. Reported author values are supplied predictions, not an authenticated baseline. Paper reproduction, same-task improvement, and matched author-code access conditions require independent future qualification.
