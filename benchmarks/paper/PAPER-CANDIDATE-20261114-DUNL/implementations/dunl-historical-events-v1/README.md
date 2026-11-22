# Historical DUNL event endpoint

This component makes the registered missed-event/false-event endpoint executable on the complete **current-code default** geometry. It complements the existing response-reconstruction scorer. The earlier local historical-helper extraction and prospective event interface were inspected: the latter's one-to-one F1 is a different metric and is not reused here.

The fixed profile is 50 trials split 30 training/20 test, 11 allocated channels, one kernel, and 576 code samples (`3000/5 - 25 + 1`). Every channel and trial is retained, including the unfilled response channel. These are the pinned release's defaults, **not an authenticated original-paper cohort or split**. The ten selected neurons versus eleven allocations remain unresolved. This package does not change the canonical task or improvement contract.

The geometry combines the whisker preprocessor defaults with the explicit whisker configuration. The generic `prepare_data_and_save.py` command defaults select another assay and must not be treated as a working whisker invocation. Its allocation formula supports the 576-sample code length only with the stated whisker settings. The source's top-k16 standard and top-k18 group assistance remain disclosed; this evaluator does not require a candidate to copy the author's architecture or top-k selection.

For each row, positive codes are binarized. Predictions within the union of target neighborhoods at inclusive ±2 bins (10 ms on the 5 ms grid) count as hits. Several predictions may hit the same target; a prediction inside overlapping neighborhoods counts once. Hit count is divided by that row's target count, and outside-neighborhood predictions by that row's prediction count. A zero target count contributes hit fraction zero; an empty prediction contributes false fraction one. The source averages these row fractions and only then clips mean hit to one; missed fraction is one minus that clipped mean. This is not precision/recall or one-to-one matching.

The `standard` caller scores trial-major/channel-minor rows. The `group` caller takes channelwise L2 code norm, repeats the common prediction over every channel, and then scores the same rows. Here it evaluates the mathematical positive support of that norm as the union of positive channel supports. It does not perform floating-point norm calculations. Source dtype rounding, norm underflow/overflow, and exact Torch reduction parity are not established. Nonnegative finite codes are required, matching the selected whisker configuration; arbitrary signed helper inputs are outside this profile.

Both modes report train and test separately, with full row counts and a mandatory schedule-only control emitting bins `100 + 25*k`, `k=0,…,15`. There is no pooled train/test score, threshold selection, scalarization of the joint endpoint, confidence interval, or claim of independent biological samples. Exact rational row means document the mathematical convention; floating source runtime parity remains a separate qualification.

## Operator interface

Python 3.11+ and its standard library suffice. Inputs are JSON representations of already-exported source tensors; this component does not load pickle/Torch files or claim to authenticate a native exporter.

The owner JSON has exactly `profile`, `channel_ids`, `trial_ids`, and `target_codes`:

- `profile`: `dunl_current_code_defaults_30_20_11_576_v1`.
- `channel_ids`: the complete ordered 11 channel identities; do not label the extra allocation as an observed neuron.
- `trial_ids`: `train` and `test` ordered identity lists of lengths 30 and 20, disjoint across splits.
- `target_codes`: `train` and `test` arrays shaped `[trials][1][576]`.

The submission has exactly `profile`, `context_id`, `channel_ids`, `trial_ids`, and `codes`. Identity lists must exactly match the owner's ordered lists. `context_id(owner)` hashes only public profile and identities, excluding targets. `codes` contains `train` and `test` arrays shaped `[trials][11][1][576]`. Values are finite nonnegative numbers; every zero and bin is included. The source caller mode and whole owner-file SHA-256 are selected externally by the operator.

```sh
python3 -B historical_events.py \
  --owner /absolute/operator/owner.json \
  --owner-sha256 OPERATOR_SELECTED_SHA256 \
  --submission /absolute/operator/submission.json \
  --mode standard \
  --output /absolute/operator/new-report.json
```

The CLI rejects duplicate JSON keys, malformed dimensions, mismatched identities, negative/nonfinite values, symlink inputs and nonregular inputs. It reads at most 16 MiB per file and creates an output exclusively with mode 0600. It never executes submission code. Keep inputs and detailed reports in an operator-owned directory: the report contains target counts and row diagnostics. These checks do not provide a filesystem sandbox, access isolation, authenticated biological identities, or crash-atomic output publication.

## Evidence and limits

[Official code](https://github.com/btolooshams/dunl-compneuro/tree/23a34f40b122c3ccf3715995f0dd19fcbbcb46a2) is pinned by file digest in `SOURCE_PINS.json`. It supports the current preprocessor defaults, positive-code convention, caller reshapes, neighborhood counts, split-specific calls and clipping order. The [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12006907/) identifies Figure 4F's event endpoint, but its exact operating point, publication-aligned settings and output-producer join remain unresolved.

No new downloads, authentic tensor reads, neural preparation, trained model inference, candidate trial, Figure 4F reproduction or improvement occurred. No raw archive or historical private target was accessed. The smoothed-raster peak-finding curve, author checkpoint/output producer, exact publication split/cohort, biological grouping, resource/access protocol and paired final comparison remain necessary for full same-task qualification. The published schedule remains available to both access arms; perfect mathematical schedule scoring on generated labels is not neural understanding or a measured paper win.

`test_historical_events.py` provides generated mathematical and interface controls, including full 550-row geometry, group-versus-standard support, overlapping target neighborhoods, clip-after-mean and unequal row denominators. Run it through the coordinator's reviewed two-slot generated-test pool during construction. Test outcome and costs are recorded in the external handoff; tests do not establish scientific readiness.

## Whisker source identity follow-up (2026-11-22)

The paper's [Whisker thalamus spiking experiment methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC12006907/) explicitly selects ten pair/neuron IDs from the original 17-pair dataset: `1/2`, `2/1`, `4/1`, `5/1`, `6/1`, `8/2`, `10/2`, `16/2`, `17/1`, `17/2`. It specifies stimulus 3 and excludes nonresponsive or very-low-SNR neurons. These logical IDs match the pinned preprocessor's ten selections. This resolves the documented selection roster, but does not connect the IDs to animal/session identities or explain the eleventh allocated channel.

The same ten selections and eleven-channel allocation are present in the [initial 2024-02-02 source](https://github.com/btolooshams/dunl-compneuro/blob/95ea5294a47b53bc3c63ea28fc021409e7483071/src/preprocess_scripts/preprocess_data_whisker_into_dataformat.py). The [2025-01-08 source](https://github.com/btolooshams/dunl-compneuro/blob/1ad15cbb7401fff48b54eb93e91128bc3e38f552/src/preprocess_scripts/preprocess_data_whisker_into_dataformat.py) is byte-identical to the pinned preprocessor (8,718 bytes; SHA-256 `ec6665b0413bb35cb57caf8bc9ad20845fde81e97d47c98552bb6ba6ef3d0ca2`). This dates the source behavior; it does not establish the publication's invocation, override arguments or executed cohort.

The earlier metadata request's HTTP 401 remains a historical observation. On 2026-11-22, the publisher's [version-1 root files endpoint](https://data.mendeley.com/public-api/datasets/rzfyr2886h/files?folder_id=root&version=1) returned HTTP 200 and six ZIP records; its [version-1 folders endpoint](https://data.mendeley.com/public-api/datasets/rzfyr2886h/folders/1) returned an empty list. The publisher reports the following compressed sizes and SHA-256 values:

| Archive | Bytes | Publisher SHA-256 |
| --- | ---: | --- |
| `dopamine-spiking-eshel-uchida.zip` | 1,002,064 | `3b0801453ec31a815ba2c429e320441957ecb75dc85649353ea2a94b0a94a5ca` |
| `dopamine-spiking-simulated.zip` | 205,125 | `1a8f232c22dde83b4fe43fabc3ffccf63c2a3b88947128ce62bf134b653b16f2` |
| `local-2kernelfornmf-simulated.zip` | 28,971,339 | `dc631c5f15e1fe24b8005d95419f6e652f1f26b01a8032fe2790a4243c39eead` |
| `local-deconv-calscenario-longtrial-simulated.zip` | 919,544 | `f35e21e5c976f22d1da1828477f9f8aa08ece6b5dc660e9cb3636a4f19d5b6c0` |
| `local-deconv-calscenario-shorttrial-structured-simulated.zip` | 857,764 | `01a0652cccbe17808c82e80de72a4acd467b9044d9402b0f5039665c5e84e287` |
| `local-orthkernels-simulated.zip` | 59,704,578 | `d5534cff35bd14b9b789620d99d4c9cb0a0d8ea85fb536fb502fd3cb475f3c03` |

The listed ZIP sizes sum to 91,660,414 bytes. These are publisher metadata, not independently verified payload digests. No ZIP body or internal file listing was read. None of the six filenames identifies a whisker archive, and the paper states that only part of its data was deposited. This does not prove that the ZIP contents lack whisker members. A source-to-file join for the ten selected neurons, original trial roles and animal/session identities remains necessary; the metadata alone does not establish that the full whisker assay is available in this release. The original Figure 4F missed/false-event endpoint, its smoothed-raster comparators, the eleven-channel software profile and all scientific readiness claims remain unchanged.
