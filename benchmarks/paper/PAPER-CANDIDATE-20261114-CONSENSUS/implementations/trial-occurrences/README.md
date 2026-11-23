# Consensus trial-occurrence adapter

A Python standard-library component for reconstructing the ordered trial occurrences consumed by the released Consensus loader. It requires supplied records for all seven animals and all three folds per animal. Repeated indices remain separate occurrences; counts and train/test overlap are grouped by original source-trial identity.

This is a supplied-record adapter with invented unit controls. It does not decode or authenticate scientific files, fit a model, score predictions, or establish a completed benchmark.

## Source behavior

The method is tied to [the official v1lm_nn revision eec6021](https://github.com/marineschimel/v1lm_nn/tree/eec6021e8b9f9031eb775fc1a10a07e583cf0e29), specifically the fitting and analysis entrypoints and `lib/data.ml`.

The released loader first indexes original arrays by P. Without a condition selection, it indexes those reordered arrays by P again, producing source identities P[P[k]]. For explicit condition pairs, it enumerates positions in the reordered condition rows, keeps selected positions in ascending order, and appends all nonselected positions. Training uses the first floor(2*m/3) occurrences, where m is the selected count; testing uses the entire remaining suffix. No repeated occurrence is deduplicated and no omitted source trial is filled.

The fitting and analysis entrypoints derive condition-code maxima at different stages relative to P. When P omits a maximum, the same CLI code can describe different pairs. This adapter therefore requires explicit selected pairs and does not claim historical CLI conversion parity.

## Supplied records

The top-level JSON has exactly `schema: "consensus_occurrence_input_v1"` and an `animals` list. Include each of:

- MPV17_FB_5
- MPV18_FB_5
- MPV31_FF_5
- MPV33_FF_5
- MPV34_FF_5
- VL63_FF_5
- VL66_FB_5

Every animal has exactly `animal_id`, `source_trial_count`, `source_condition_pairs`, and `folds`. Trial count is an integer from 1 to 10,000. This is an engineering bound, not evidence that every authentic source axis fits it. Original condition rows are either null or all n pairs in original source order, with finite numeric magnitudes at most 2^53.

Every animal requires folds 0, 1 and 2. Each fold has exactly:

| Field | Required value |
|---|---|
| `fold_id` | Integer 0, 1 or 2. |
| `companion_indices` | n integers or exactly integral finite floats in [0,n). |
| `native_indices` | n true integers in [0,n), or null when unavailable. |
| `configuration` | The object below, or null when unavailable. |

Configuration has exactly `branch`, `selected_condition_pairs`, `entrypoint`, and `basis`. Branch `no_condition` requires null selected pairs; `condition_pairs` requires an explicit list, which can be empty. Entrypoint is `fit`, `analyze`, or null. Basis is `declared_scenario` or `supplied_historical_record`. Those labels do not authenticate the supplied records.

The native sequence determines the reconstructed order. Missing native/configuration/condition evidence remains explicit; companion disagreement never silently replaces the native sequence. All 21 folds remain represented. Three-fold aggregates are null unless all three mappings are reconstructable. Folds are not independent animals.

## Use and controls

From the repository root:

```sh
python -I -S -B benchmarks/paper/PAPER-CANDIDATE-20261114-CONSENSUS/implementations/trial-occurrences/occurrence_adapter.py < supplied-records.json > occurrence-audit.json
python -I -S -B benchmarks/paper/PAPER-CANDIDATE-20261114-CONSENSUS/implementations/trial-occurrences/run_invented_controls.py
```

The first command accepts at most 8 MiB of JSON (reading one extra sentinel byte to reject larger input) and checks a 64 MiB serialized-output limit. It reports each occurrence's unique within-fold index, loader position, original source-trial index, selection group and partition. It also reports multiplicity, omissions, source-ID overlap and complete three-fold coverage. Authentic output contains supplied trial identities.

The second command runs exactly 27 invented controls with no third-party dependency. Fixtures use fabricated arrays, never authentic neural values or held benchmark answers. Controls cover nonidentity double indexing, repetitions, condition ordering, native/companion disagreement, missing evidence, complete scope, empty support, strict JSON/types and CLI serialization. The workflow retains complete test streams and exit status.

## Scientific and runtime limits

Supplied-record consistency does not prove native/NPY byte correspondence, original neural trial-axis alignment, historical configuration, target isolation, reference scoring, predictive performance, or full-paper reproduction. Source-ID disjointness alone does not establish leakage safety: the released condition-average computation uses a full original pool before splitting, and held-neuron/cache choices require separate evaluation. This component never repairs the original folds or qualifies a scientific result.

The adapter has no hard memory or process-isolation boundary. The control runner sets a 25-second CPU limit and a 29-second alarm after its standard-library imports; the workflow supplies a separate 35-second command deadline. These controls concern invented indexing cases and do not increase the number of completed benchmarks.
