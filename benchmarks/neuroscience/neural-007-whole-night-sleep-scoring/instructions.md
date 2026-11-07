# NEURAL-007 — whole-night sleep scoring

Predict the five sleep stages for every 30-second epoch of each complete development recording. Use the six labeled training participants to develop a method. The observation condition consists of engineered EEG/EOG/clock features and shared, fixed pretrained YASA model outputs. This is an executable development scoring adapter for the existing whole-night sleep assignment; it does not complete the wider neural-investigation or four-cell agent study.

`public_assets.json` is the exact public input allowlist. Its paths are lazy references relative to this repository, with exact sizes and SHA256 digests. Do not mount their parent directories wholesale: some contain other cases, operator metadata or private material. The evaluator has a separate allowlist in `operator_assets.json`; that file, scoring sources, reference reports, private targets and operator evidence must not be mounted into a candidate environment. No waveform copy is required.

There are six training participants (`train-001`…`train-006`, 16,290 epochs) and two exposed development participants: `development-001` has 2,780 epochs and `development-002` has 2,670. The development people differ from the six fitting people. They have already been used during benchmark construction; this is not a pristine confirmation panel. Four reserved people are outside this package.

For each case, feature files contain `epoch_id`, `epoch_start_seconds`, `clock_features`, `signal_features`, `channels`, `feature_names`, `sample_rate_hz` and `epoch_seconds`. The source was sampled at 100 Hz. There are three channels (EEG Fpz-Cz, EEG Pz-Oz, horizontal EOG), six signal features per channel, and elapsed-hour/circadian sine/cosine features. Use the stored names. Training label files contain epoch IDs, integer stage labels and the training scoring mask. Unknown/movement epochs have stage −1; retain the complete clock. Never trim development recordings from their hypnograms or use development labels to select a method.

Common-model files contain `epoch_id`, `class_order`, `component_order` and float64 `component_probabilities` of shape epochs × 4 × 5. Components are Fpz EEG, Pz EEG, Fpz EEG+EOG and Pz EEG+EOG. The two ensembles are equal arithmetic means of the corresponding two components; the anchor equals Fpz EEG+EOG. The pinned `cache_core.py`/`cache_io.py` helpers document the interface. All participants receive the same available model views. Their pretrained weight variants and full-recording context differ from a newly fitted feature model, so differences do not isolate a causal EOG effect. Full-night information is allowed; online forecasting is not the estimand. A separately qualified raw condition supplies the six training recordings and both development recordings alongside the same model caches. Use its dedicated program contract; the feature condition described here does not expose those waveforms.

Freeze a method using training participants only, then apply it independently to each development person. Any tuning should use participant-grouped training validation. Do not carry mutable development-case state between people. This scoring adapter accepts a finished probability file and does not itself enforce training provenance, program replay, model budgets or per-case reset. The qualified fixed-program runner enforces source commitment, fresh per-person process/scratch/output, and prediction commitment before grading. The finished-file scoring command below does not itself enforce those program guarantees.

Submit one ordinary, single-link, uncompressed `numpy.savez` file (at most 4,000,000 bytes), with exactly:

- `class_order`: Unicode `['W','N1','N2','N3','R']`.
- `development-001__epoch_id`: canonical Unicode IDs `development-001/00000` through `development-001/02779`.
- `development-001__probabilities`: shape `(2780,5)`, float32 or float64.
- `development-002__epoch_id`: `development-002/00000` through `development-002/02669`.
- `development-002__probabilities`: shape `(2670,5)`, float32 or float64.

Every probability must be finite and between zero and one. Each row must sum to one within absolute tolerance 1e−6 (float64 summation). No correction is applied. C- or Fortran-layout arrays are accepted. No extra arrays, compressed members, object dtypes, missing epochs or duplicate identities are allowed. Exact ties choose the first class in the declared order. Submit all epochs; the private scorer applies unknown/movement masks only after validating the complete submission and both comparators.

The primary score is the equal-participant mean of macro-F1 over the fixed five classes. An absent, never-predicted class contributes zero F1. Secondary outputs include each participant's confusion matrix, per-stage F1/recall, balanced accuracy over truth-supported classes, and signed candidate-minus-YASA and candidate-minus-RF differences. A negative difference remains a valid result. There is no pass floor, binary scientific-success reward or requirement to equal reference coefficients. Copying the shared YASA ensemble is an allowed baseline: it receives its measured F1 and zero improvement, not a perfect score.

Run from the repository root with a fresh output directory:

```sh
python3 benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/score.py --submission /absolute/path/predictions.npz --output /absolute/path/new-score
```

The operator CLI uses the existing pinned local Docker image, a fresh offline nonroot read-only container, two CPUs, 4 GiB RAM, bounded scratch/output and an 18-second whole-call limit including independent cleanup. It never imports or runs candidate code on the host. Results are `score.json` and an operational receipt. Exit 0 means a valid descriptive score, exit 2 means invalid submission, and exit 1 means an operator/runtime failure. The score is meaningful only for this exposed two-person development sample; epochs are not independent participants. No confidence interval, population superiority, neural understanding, blind model performance or expert validation is established.

This is a local-workspace package, not a standalone redistributed dataset or hosted Terminal-Bench submission. Source/data rights and existing notices remain applicable. Docker availability and the exact existing artifact hashes are prerequisites. Fixed-program execution is qualified in both feature and raw conditions. A bounded two-step investigation interface has also passed developer controls. Scientific reasoning assessment, actual paired agent comparisons, and an independent confirmation panel remain unfinished.

## Submit a program

The [condition-aware run guide](../../../authoring/sleep-eog/raw-program-cli-v1/README.md) provides an executed command and the correct per-person program output contract. Select `features` or `raw`; both retain the same task ID, training/development people and scorer. These observation conditions are distinct from the finished combined-probability file described above.

The [two-step workflow guide](../../../authoring/sleep-eog/completion-v1/README.md) specifies matched fixed-program and investigator tools, observation feedback, per-person reset, and report submission. All four raw/feature × fixed/investigator developer controls passed. The external investigator caller must enforce its own fresh model context and token budget; the file exchange does not isolate that caller. These controls establish execution mechanics, not an LLM comparison or scientific reasoning quality.
