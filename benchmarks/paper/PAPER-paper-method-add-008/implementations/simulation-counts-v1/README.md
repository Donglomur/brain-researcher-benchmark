# Original Figure 7 native-count reduction

This component computes the paper's corrected per-ground-truth-unit accuracy from evaluator-owned TP, FN and FP counts. It enforces the full main Figure 7 population: `Neuropixels1-384_500_1800.s`, seeds **2205, 2406, 2308, 1110, 2512**, each with the same 500-unit ground truth in static and drifting recordings, and all four source sorters: Kilosort4, Tridesclous2, SpyKING CIRCUS2 and Lupin. A source-only export has 40 cases and 20,000 unit rows. An optional candidate adds all ten corresponding cases; it cannot replace a source method or select favorable seeds, units or motion conditions.

The old `initial-evaluator-v1` remains a separate Figure 8 real-data curation component. Its yield, curator labels and raster are not simulation accuracy. Neither implementation nor historical evidence was changed.

## Calculation and information boundary

For each source-matched ground-truth unit, the corrected ratio is

`accuracy = TP / (TP + FN + FP) = TP / (Ni + Nj - TP)`.

Every exported unit must satisfy `TP + FN = Ni`, where the independent owner manifest freezes the original ground-truth spike count. Unmatched units remain present and have zero accuracy when `FN > 0`. A zero denominator is retained as JSON `null`: this component does not guess the publication-compatible library's empty-unit convention. No undefined or low-SNR units are discarded.

The owner also exports the native `num_well_detected`, `num_false_positive`, `num_redundant`, `num_overmerged` counts and runtime for each case. These values are preserved, not regenerated from guessed thresholds; the four categories are not assumed to form a partition. Candidate comparisons report every paired unit's accuracy difference, each companion-count difference and runtime difference for each source method, seed and motion condition. There is no new pooled scalar, uncertainty estimate, ranking or success threshold.

**Inputs are trusted evaluator outputs, not candidate self-reports.** This code does not match raw spike trains, verify native run receipts, or prove the supplied assignments and counts were computed correctly. Before using authentic exports, the evaluator owner must independently resolve and pin the publication-compatible SpikeInterface comparator, its complete effective matching and count parameters, the generator/sorter dependencies, and native artifacts. The external manifest digest is supplied independently of candidate outputs. Hash agreement binds files and declarations; it is not attestation of source execution.

Candidate programs may receive the original traces, geometry and permitted metadata, but not this owner manifest, ground-truth unit inventory, match results or reference counts. No participant transport is provided here. The original seeds and source are public, so an access-restricted local evaluator does not make them scientifically unexposed.

## Exact interchange

The schema is defined by `reduce_panel.py`; extra or missing fields fail closed. The generated control in `test_reduce_panel.py` is an executable schema example, with conspicuous placeholder hashes and generated counts. Do not use it as a native assessment manifest.

The owner manifest contains:

- `schema: figure7-native-counts-owner/v1`, the exact `dataset`, and `candidate_method` (a distinct method name or `null`).
- `evaluator_identity`: SHA256 of the audited SpikeInterface source and environment, plus nonempty dictionaries of **resolved** effective matching and unit-count parameters. Merely recording `{}` would leave source defaults unspecified.
- `seeds`: all five integer seeds, each with `sorting_sha256`, both `recording_sha256` values (`static` and `drifting`), and exactly 500 `{unit_id, num_spikes}` records. IDs are losslessly represented as nonempty strings, are local to their seed, and must retain original native identities.

The export contains `schema: figure7-native-counts-export/v1`, `owner_manifest_sha256`, and all cases. Each case carries `method`, `motion`, integer `seed`, `status: computed`, ground-truth and recording hashes, `evaluator_identity_sha256`, `native_output_sha256`, positive `runtime_seconds`, the four `unit_counts`, and all 500 `{unit_id, tp, fn, fp}` records. Counts are nonnegative integers, never booleans. Failed sorter runs cannot be represented as successful empty results. Unit and case order may differ in the input; output follows the owner inventory and fixed source order.

Canonical digests use UTF-8 JSON with sorted keys, compact separators and nonfinite values forbidden. JSON input also rejects duplicate keys. Example invocation, using independently frozen external files:

```sh
python3 -I -B reduce_panel.py \
  --owner-manifest /absolute/operator/owner.json \
  --expected-manifest-sha256 OWNER_DIGEST \
  --native-export /absolute/operator/native-counts.json \
  --output /absolute/operator/accuracy-report.json
```

The output must not exist. All validation and serialization finish before it is opened. The report retains all count triples, unit identities, case identities and native output hashes. This is an operator artifact and must stay outside public Git when it contains authentic counts or private identities.

## Reproduction and improvement outcomes

The latest project objective treats reproduction and improvement as separate first-class outcomes. This component supplies the same count-based endpoint for both. It does **not** yet issue a reproduction score against published arrays or an improvement decision: exact numerical references, native matching/dependency fidelity, source figure aggregation, tolerance/effect rules and dependence-aware uncertainty are unresolved. A candidate's difference from an unqualified replay is not evidence of exceeding the paper.

For future paired **paper + data** and **paper + data + author code** conditions, use the same original recordings, evaluator and endpoint. Author code access is an experimental condition, not a change in cohort, metric or benchmark count. This component does not implement either delivery condition or provide any candidate/model performance evidence.

## Source recovery and remaining limits

The immutable author revision is [`d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1`](https://github.com/SpikeInterface/sorting_components_benchmark_paper/tree/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1). Exact file hashes are in `source-provenance.json`. The recovered notebook records ten datasets and forty computed cases. Its Figure 7 calls group by sorter and motion; request accuracy-versus-SNR averages, ordered accuracy, runtimes and the four companion counts; and keep static and drifting plots separate. However, the bin edges, weighting, matching rules and count thresholds are delegated to SpikeInterface and are not fixed by these files. This reducer therefore does not substitute a guessed reproduction of those plots.

The notebook's saved textual outputs contain case summaries and a figure representation, not exact score arrays. No graph was digitized. The author tree contains no main simulation dependency lock; the separate real-data environment cannot establish simulation dependency identity. The source README links the first reviewed preprint, while the task cites the version of record, so matching code bytes alone does not establish publication-version fidelity.

The official [Zenodo record](https://doi.org/10.5281/zenodo.20407862) metadata identifies a May 27, 2026 `v2` script/notebook archive, 3,430,815 bytes. Only its metadata was acquired; no assertion about the archive's internal files is made. Initial raw-host source requests failed TLS, but immutable official GitHub blob requests recovered the required files. A later SpikeInterface revision-metadata request was rate limited; no latest revision was substituted for the missing publication dependency. Failed response bodies are accounted for in external acquisition receipts.

No authentic recordings, target arrays, simulation generation, sorter execution, model inference, fitting or candidate trials were performed. The original supplemental probe panels remain outside this complete main-panel component.

## Verification

Run the standard-library controls through the project's shared two-slot test pool:

```sh
python3 -I -B test_reduce_panel.py
```

Nine generated controls verify the corrected denominator, all 25,000 rows with a candidate, the source-only 40-case route, missing/failed/duplicate cases, seed/recording/unit mismatches, ground-truth spike conservation, unmatched and empty units, independent manifest/evaluator binding, reordered inputs, and duplicate/nonfinite JSON rejection. They test count arithmetic and population accounting, not native comparator correctness or scientific performance.
