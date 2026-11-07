# NEURAL-008: numerical component of an EOG investigation

Predict the five sleep stages for every 30-second epoch of two development recordings. Submit two complete probability panels: one named `EEG_clock`, intended to use EEG and the declared recording clock, and one named `EEG_EOG_clock`, intended additionally to use horizontal EOG. Investigate whether the second panel improves classification, including REM recall, without hiding either panel's absolute performance.

This component scores finished prediction files. It cannot verify which information a producer used, whether the two models had comparable training budgets, or whether an EEG-only model was deliberately weakened. Every output therefore marks training and information-access provenance as unverified. A larger difference is **not** a maximization reward or scientific success criterion. A physiological explanation and a controlled, independently audited ablation remain separate requirements for the full investigation.

## Available observations and fixed cases

The existing public source inventory is `benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/public_assets.json`, whose exact version is pinned in `PLAN.json`. It references six labeled training people, their engineered signal and clock features, and two unlabeled development people. EEG features occupy the first two channels of the existing `(epochs, 3, 6)` signal-feature representation; horizontal EOG is the third. The fixed RF reference used 12 EEG features and three clock features, with six EOG features added for its full arm. The shared public inventory also has trained-model output caches. These are a different information condition: do not describe full-modality cached outputs as EEG-only observations. This scorer neither supplies raw recordings nor enforces a program's observation access.

The required cases are `development-001` with 2,780 epochs and `development-002` with 2,670 epochs. IDs run from `<case>/00000` to the last epoch, in exact order. Include the full recording clock, including epochs later excluded by the private unknown-stage mask. Do not crop by true sleep labels. The two people are historical, publicly exposed development cases. The four reserved people are untouched. Epochs are not independent biological replicates.

The existing label mapping combines original stages 3 and 4 into N3 and masks unknown or movement annotations. This mapping and the source-aligned 30-second clock are inherited without changes.

## Submission

Provide a directory containing exactly:

- `EEG_clock.npz`
- `EEG_EOG_clock.npz`
- `claims.json`

Each NPZ is a stored, uncompressed ZIP of ordinary NPY arrays, at most 4,000,000 bytes. It contains exactly `class_order` and, for each case, `<case>__epoch_id` and `<case>__probabilities`. `class_order` is Unicode `['W', 'N1', 'N2', 'N3', 'R']`; REM is index 4. IDs are bounded Unicode strings with the exact full-clock identities and order. Probabilities have shape `(epochs, 5)`, dtype float32 or float64, and finite values in `[0,1]`. Every row must sum to 1 within absolute tolerance `1e-6`, using float64 summation. Neither clipping nor renormalization occurs. C- and Fortran-order arrays are accepted. Pickle, objects, structured arrays, linked files, duplicate/extra/missing members and incomplete headers or payloads are rejected before private labels are loaded.

The claim file is strict UTF-8 JSON, at most 16,384 bytes, without duplicate keys or nonfinite numbers. Claims are optional because a prediction submission should not have to guess unrevealed evaluation metrics. The valid no-claim file is:

```json
{"schema_version":1,"candidate_id":"NEURAL-008","reported_contrast":null}
```

An optional `reported_contrast` object has exactly `person_mean_macro_f1_delta`, `person_mean_rem_recall_delta`, and an ordered `per_person` list. Each list entry has `person_id`, `macro_f1_delta`, and `rem_recall_delta`. Differences are finite numbers in `[-1,1]`; REM differences may be null when unsupported. Boolean numbers are rejected. Numerical claim agreement uses absolute tolerance `1e-10`; it does not validate the scientific explanation or the model.

## Reported endpoints

Class decisions use the first fixed class index at a probability tie. For each arm and each person, the report retains the full confusion matrix, support counts, all five class F1 scores and recalls, fixed-five-class macro-F1, supported-class balanced accuracy, and REM recall. F1 is zero for a class with neither predictions nor support. Recall is undefined when a person has no true examples of that stage.

The paired direction is always `EEG_EOG_clock − EEG_clock`. The report includes each person's F1 and REM-recall difference and the equal-person aggregate. If either person lacks REM support, the aggregate REM contrast is null; the remaining person is not silently averaged alone. Positive, zero and negative differences are all valid. Both absolute arm scores remain visible. The small `1e-12` qualification tolerance checks replay arithmetic, not scientific performance.

The completed historical reference offers context, not an admission floor: fixed EEG+clock and EEG+EOG+clock RF recipes, clock-only, EEG without clock, EOG+clock, training-majority and a fixed within-person EOG displacement. The displacement is one prespecified manipulation, not a null distribution or causal test. YASA EEG-only and EEG+EOG models have different pretrained weights and cannot establish a matched EOG contribution. This new scorer does not retrain any reference.

## Execution and limitations

After qualification, the intended local command accepts `--submission`, a fresh `--output` under `artifacts-build`, and a new operator `--review` with current cumulative accounting and `--other-reserve-bytes`. Ordinary scoring is a separately reviewed 30-second operation. No future run is authorized by the qualification receipt alone. Both public probability panels and the claim schema pass before the isolated grader invokes its private target loader once. Candidate code is not run.

The output contains continuous metrics and claim discrepancies, with `score: null`, no scientific pass floor, no population confidence interval, and `scientific_improvement_verified: false`. This is an executable numerical component of the existing investigation ID, not a newly counted dataset, a native-LLM test, a complete controlled investigation, or an independent replication of the sleep paper.

## Submit a program

The [paired program contract](../../../authoring/sleep-eog/eog-program-completion-v1/README.md) now accepts one precommitted Python source and executes it independently on physically separated EEG+clock and EEG+EOG+clock views. Both predictions are committed before the unchanged scorer receives development labels. The same source and permitted inputs are enforced; scientific equivalence of an arbitrary program's training choices still requires review.

The [ordinary command guide](../../../authoring/sleep-eog/eog-program-completion-v2/accepted-cli-v1/OPERATOR_USAGE.md) gives the shared CLI, method/claim inputs and execution review. Four developer controls and an actual ordinary shared-command submission have been evaluated; the saved RF qualification correction is disclosed in the [results](../../../authoring/sleep-eog/eog-program-completion-v2/RESULTS.md). This adds program execution to the existing task. It does not establish native neural understanding, an LLM result or population generalization.
