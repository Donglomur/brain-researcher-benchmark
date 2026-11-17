# Initial word-responsiveness evaluator

This independently written component computes the Brain Treebank paired word-response endpoint from aligned, processed epochs. It implements the canonical task's next action of defining one electrode-response endpoint. It is **not** a complete paper evaluator, a native-data loader, an authentic reproduction, or a qualified benchmark. Sentence-position effects, joint confound adjustment and time-resolved decoding remain required parts of the broader task.

## Source and meaning

The canonical contract is `task.json` (SHA256 `43a4653f5da2600d6df0733d2fff6a821aee5d9588234f236c5f147a6d302b12`). The paper is [Wang et al., NeurIPS 2024](https://proceedings.nips.cc/paper_files/paper/2024/hash/aefa2385b3f33abf1526ae4e2c208cd9-Abstract-Datasets_and_Benchmarks_Track.html), with [versioned primary text](https://arxiv.org/html/2411.08343v1). The official code pin is `c54ba38eab7814538bc03b1b6d29a3f50f034e12`. This package contains original implementation code; no official code is vendored because its standalone reuse license remains unresolved.

The fixed five 100 ms pre/post pairs follow paper section 4/Appendix A.6 and the pinned word-onset configuration. They compare -500..0 ms with 500..1000 ms, pair by pair. Epochs use 2048 Hz; offsets truncate decimal endpoint products toward zero as in [`stats/word_onset_tests.py`](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/stats/word_onset_tests.py). Half-open sample offsets are:

| Pair | Pre | Post |
|---|---|---|
| 0 | [-1024,-819) | [1024,1228) |
| 1 | [-819,-614) | [1228,1433) |
| 2 | [-614,-409) | [1433,1638) |
| 3 | [-409,-204) | [1638,1843) |
| 4 | [-204,0) | [1843,2048) |

Each window is averaged within each word. The paired difference is pre minus post. A two-sided Student t statistic uses sample variance of paired differences and n−1 degrees of freedom. The source-style standardized effect divides the mean difference by the population SD (`ddof=0`) of concatenated pre and post word means; it is **not paired Cohen dz**. Every window is retained. The minimum p-value and its effect always refer to the same window. Stable mergeable moments combine all declared runs for each subject/electrode, with per-run statistics retained as descriptive diagnostics. Words, runs and electrodes are not interchangeable independent subjects.

Global Bonferroni over **all declared retained subject/electrodes × five windows** is an explicit prospective policy at alpha 0.05. It includes degenerate windows in the denominator, and never corrects only a selected subset. The exact historical correction family and published numerical targets are still not qualified. Constant paired differences have an unestimable noise variance; their t and p are null, with a status, rather than silently reporting p=0. Threshold flags describe this computational policy only. Temporal dependence, overlapping word epochs and naturalistic confounds prevent interpreting them as qualified scientific decisions.

## Input and command

Use the installed NumPy and SciPy environment; no dependency installation is required by this package:

```sh
python -B benchmarks/paper/PAPER-paper-method-replacement-011/implementations/initial-evaluator-v1/evaluator.py manifest.json --input-root /absolute/input --output result.json
```

The JSON manifest has these fields:

- `schema_version: 1`, `task_id: "PAPER-paper-method-replacement-011"`, `sample_rate_hz: 2048`, and integer `epoch_first_sample` relative to onset (normally -1024).
- `scope`: `engineering_control` or `declared_source_population`. The latter requires all 10 subject identifiers and all 26 source runs from pinned [`data/all_trials.json`](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/data/all_trials.json). Neither scope authenticates membership or qualifies results.
- Lowercase SHA256 fields `timing_sha256`, `electrode_inventory_sha256`, `processing_sha256`, plus nonempty `processing_description`. These identify caller-declared external evidence; this component does not read or independently verify those three artifacts.
- `selection_policy: "all_declared_electrodes_and_words"` and `subjects`, each with a `subject_id`, ordered unique retained `electrode_ids`, unique `run_ids`, and optional `excluded_electrodes`. Each exclusion has `electrode_id`, nonempty `reason` and `evidence_sha256`; exclusions and retained IDs must not overlap.
- `recordings`, exactly one per declared subject/run, with `subject_id`, `run_id`, a relative NPZ `path`, its `sha256`, `n_words`, and `word_ids_sha256`. The last is SHA256 of UTF-8 compact JSON of the ordered word-ID list (`ensure_ascii=False`, separators `,` and `:`).

Each NPZ contains exactly `epochs` (real finite E×W×T), `electrode_ids` (unique Unicode vector matching manifest order), `word_ids` (unique Unicode vector), and `onset_samples` (nonnegative chronological integer vector). At least two words are required per run. Every epoch must cover all five complete pairs. No shortened windows, missing runs, reordered electrode identities, failed checksums, object arrays or paths escaping the input root are accepted. Word IDs are unique within their recording; repeated movie presentations retain distinct run identity. The tests include a complete generated input builder and CLI example.

The native path must separately establish raw-file and timing hashes, seizure/corrupted-channel exclusions, source filtering and word inclusion. A claimed processing description is insufficient. This evaluator preserves all supplied words; it cannot determine whether the upstream loader omitted words. Input NPZ bytes and manifest are hashed; actual input receipts accompany output. No inputs or generated outputs are shipped as biological evidence.

## Source discrepancies and retained requirements

Inspection of the pinned entrypoints established these active-path concerns:

- `stats/word_onset_tests.py::uncontrolled_ttest` tracks a minimum p-value but returns the last loop p-value alongside the minimum's effect. The new evaluator emits all pairs and a matched minimum/effect; it does not claim numerical equivalence to this defect.
- [`run_time_tests.py`](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/run_time_tests.py) shuffles words in its NN cross-validation helper and exchanges the train/validation assignments. Its last time windows can be truncated. This does not establish chronological holdout and is not the paper's independently verified linear-decoder execution.
- [`run_glms.py`](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/run_glms.py) references unresolved names in the result path. A working author GLM reference is not demonstrated.
- [`stats/sentence_position_tests.py`](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/stats/sentence_position_tests.py) overwrites the iterated subject/electrode with one pair. Its presence cannot establish full-population execution.

The output always sets research qualification, full-contract completion, native reference verification and binary-reward registration false. It also records the following unresolved requirements: authentic full electrode/word population; independent native timing/filtering checks; temporal dependence; exact historical grading tolerance/reference; joint acoustic, visual, speaker and scene controls; sentence-position and decoding endpoints; participant/movie/temporal protected splits and train-only feature/electrode selection; equal candidate access and isolated replay; movie/transcript rights and official-code reuse rights. Dataset CC BY 4.0 does not resolve those other rights. Brain Treebank tasks including NEURAL-016 share the declared `braintreebank-human-movie-ieeg` exposure family; these results do not establish an independent cohort.

## Engineering verification

```sh
python -B -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-011/implementations/initial-evaluator-v1/tests -v
```

Controls check independently derived Student t and effect values, streaming moments against SciPy, integer window endpoints, complete inventory and multiplicity, the original minimum-p/effect failure, degenerate/nonfinite arrays, checksums/path boundaries and CLI receipts. These bounded generated checks measure engineering correctness only. No dataset archive, scientific model, native analysis or paid service was run.
