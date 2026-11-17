# Original Volume row and channel binding

This component reads the original author's metadata formats and binds native
prediction arrays to saved test rows and ordered electrode ensembles. It retains
all seven downstream participants, the 90-electrode Table 1 primary, and the
1/10/20/30/40/50-electrode Figure 3 conditions. It does not regenerate splits,
recompute quartiles, extract features, load neural arrays, or run a model.

The original random-row task permits overlapping neural contexts. Unlike the
preserved `initial-evaluator-v1` prospective profile, this binder accepts that
split design. It does not treat word onset as the five-second neural support.

Reproduction of the original findings and improvement beyond them are separate
benchmark outcomes. This metadata component awards neither outcome. The paired
paper+data and paper+data+author-code conditions still require controlled delivery,
execution and scoring. No participant/model trial was run here.

## Recovered source and consequential details

Fourteen author files were recovered at revision
`d237755bbdea123c60bface0cecbb48bab6f42de`; exact byte/hash pins are in
[SOURCES.json](SOURCES.json). Raw source stays outside Git.

- `data/write_multi_subject_multi_channel.py` emits retained low-quartile rows
  followed by high-quartile rows. A feature's numeric filename is its index
  **after** this selection, not the original transcript word index.
- `data/make_subject_specific_manifest.py` filters the combined manifest and
  labels together while retaining row order. Its `zip` can silently truncate
  unequal files; this binder rejects unequal lengths.
- `datasets/pt_supervised_task_coords.py` reads two-column `manifest.tsv`
  (feature path, subject), and the first column of `labels.tsv`. The RMS writer's
  second label column contains word onset in seconds. The raw labels are
  `False`/`True`. The loader enumerates a Python set to assign native class
  indices, so high RMS is not assumed to be native class 1.
- `tasks/utils.py` saves `splits.json` with `train`, `val`, `test` integer lists.
  `tasks/base_task.py` constructs `Subset` objects in those saved index orders.
  The task-specific batch loader uses the default nonshuffled DataLoader.
- The .1 validation and .1 test defaults yield a held-out count
  `ceil(.2*n)`, then a test count `ceil(.5*held_out)`; training uses the remaining
  rows. This component rejects few-shot or incomplete partitions. It checks sizes
  and saved membership integrity, not whether the historical seed generated them.
- Selected channel files define membership. The native loader retains the
  original feature-column order, even when the selection list uses another order.
  The binder emits those original column indices as well as channel names.
- The criterion's BCE path applies sigmoid and `squeeze()` before the task
  concatenates predictions. Scalar batches are wrapped before concatenation,
  yielding the flat probability list consumed here. The alternate MSE path is
  outside this binary Volume interface; custom/native shape changes need an
  explicit adapter rather than automatic flattening.

The previously unacquired `clean_laplacian.json` is now content-pinned. Its clean
channel counts are 91, 100, 91, 152, 135, 205 and 173 for subjects 1, 2, 3, 4, 6,
7 and 10 respectively. All names are unique within subject; every subject has
at least 90 eligible names. This is source metadata, not confirmation that any
historical selected ensemble or extracted feature array is available.

The pinned repository root has no `saved_data_splits` directory; querying that
documented path returned 404. The pinned `electrode_selections` directory lists
only `clean_laplacian.json` and `debug_electrodes.json`. Thus these documented
repository locations do not supply the historical split and ranked-ensemble
artifacts. This scoped inventory finding does not claim that the artifacts are
unavailable from every possible author release.

## Operator interface

Python 3.10+ and the standard library suffice. Keep the plan and prepared binding
outside participant packets: they include labels and original test identities.
Use the shared test pool for generated checks in the parallel build environment.

```sh
python3 -B binding.py prepare operator-plan.json operator-binding.json
python3 -B binding.py bind-native operator-binding.json native-runs.json bound-predictions.json
python3 -B test_binding.py
```

The plan contains `source_revision` (the exact revision above), `endpoint: "rms"`,
`clean_laplacian_json` (path to the exact source file), and `subjects`, keyed by
exactly `sub_1`, `sub_2`, `sub_3`, `sub_4`, `sub_6`, `sub_7`, `sub_10`.
Each subject entry has these operator paths:

| Key | Author artifact |
| --- | --- |
| `manifest_tsv` | Subject-specific `manifest.tsv`, path and subject columns |
| `labels_tsv` | Corresponding `labels.tsv`, Boolean text and onset seconds |
| `splits_json` | Actual saved `splits.json`; all three ordered index lists |
| `ordered_electrodes_json` | `all_ordered_electrodes.json` containing that subject |
| `selection_files` | Object keyed by `"1"`, `"10"`, `"20"`, `"30"`, `"40"`, `"50"`, `"90"`; values are paths to native subject-keyed channel-selection JSON files |

Feature paths must end in the registered subject/trial and the author-generated
integer `.npy` filename. Prefixes are not retained in the binding. Feature
ordinals must cover the complete supplied subject manifest, and all saved splits
must contain both RMS classes. Native TSV bytes, saved split bytes, channel-order
bytes and selection-file bytes receive SHA-256 receipts. The caller-supplied
files' historical authenticity is not established by these receipts.

The native input has `binding_sha256` and `runs`, with exactly 49 keys such as
`sub_1/90`. Each run contains:

- `manifest_indices`: the actual native output row order, equal to the saved
  `test` list, including order;
- `channels`: the actual native channel names in feature order;
- `label2idx`: the actual runtime mapping, such as `{"False": 1, "True": 0}`;
- `predicts` and `labels`: the author's native probability and integer label
  arrays, with every expected test row present.

The author result arrays alone omit row identities and channel order. These
additional fields must come from audited runtime instrumentation or existing
artifacts; the binder must not be used to fabricate them from the intended plan.
It validates native labels against the independently supplied labels TSV. Swaps
within the same label class remain indistinguishable without trustworthy runtime
row evidence.

Output records include portable retained-feature identity, subject, count,
`probability_native_index1`, and `native_high_rms_index`. The original probability
is preserved exactly. Subtracting tiny probabilities from one can collapse
distinct scores; a future original-panel scorer must use the explicit class
orientation when computing ROC-AUC, rather than silently treating native index 1
as high RMS. Output prediction records exclude target labels; the complete
prepared binding remains operator-only. These predictions are not compatible
with the predecessor's prospective reference without an explicit new evaluator.

## Validation and remaining scientific gaps

Generated tests cover reordered manifests and saved test indices, uneven split
rounding, complete subject/count coverage, both native class orientations,
probability preservation near zero, mismatched lengths/labels/channels,
unknown/duplicate channels, duplicate JSON keys, invalid indices, nonfinite
onsets/probabilities, clean-source pin mismatch and rehashed structural corruption.
Two additional generated controls executed only the recovered author's channel
selection method and confirmed the feature-order convention. No tensor/model
code was imported or executed in that source-method control.

Still missing: authentic historical TSVs, saved splits and selected channel
ensembles; transcript/timing/tie handling reconciliation; numerical Figure 3
references; BrainBERT/PopT weight and feature identities/rights; native output
instrumentation and validation selection evidence; original-panel scorer and
matched comparator runs; separate reproduction tolerances and improvement
effect/uncertainty rules. Shared movies and temporal dependence still constrain
uncertainty. Passing this component does not authenticate a historical split,
establish a reproduction, demonstrate improvement, or establish current SOTA.
