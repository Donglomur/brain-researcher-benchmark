# Published Figure 2 reference

The exact publisher-linked [Source Data Fig. 2 CSV](https://static-content.springer.com/esm/art%3A10.1038%2Fs43588-025-00826-5/MediaObjects/43588_2025_826_MOESM4_ESM.csv) is now recovered and authenticated. It contains **240 rows and 480 normalized pair-axis means**: all five Deeprecon subjects, all 20 directed nonself pairs, six ROIs, both source methods, and both pattern and profile endpoints. The 15,637-byte source has SHA256 `f6beffbcad700f3e24208016daabe18d802805404f32a0585e2f9333fd4968fb`. The original CSV and generated numerical reports remain outside Git.

`published_reference.py` authenticates those exact bytes, verifies the complete panel, and calculates 24 equal-pair summaries. It also compares the existing evaluator's complete **normalized** pair results against the corresponding publication values. Every pair is checked individually; compensating errors cannot pass merely because their mean is zero. Per-group reports include signed error, maximum absolute pair error, RMS pair error, and count within a supplied absolute tolerance. The operator must provide the tolerance and its rationale; this component does not invent or independently qualify a tolerance.

The source table reports the within-pair means after noise-ceiling normalization. It does not contain individual voxel/image correlations, ceiling values, threshold masks, native arrays, converter weights, or uncertainty samples. Table summaries here are observed equal-pair means. The pinned author's plotting script instead displays the mean of 1,000 pair-bootstrap means and its percentile interval; those are separate statistics, and the pairs share only five human subjects. This component does not substitute its arithmetic summaries for the figure's bootstrap bars or propose independent-subject uncertainty.

The source experiment remains the original Figure 2 shared-training-stimulus Deeprecon condition: 1,200 training images repeated five times and 50 natural test images repeated 24 times, whole-VC conversion, and VC/V1/V2/V3/V4/HVC reporting. Category-disjoint conversion, inter-site transfer and image reconstruction are distinct analyses. Source normalization and both conversion controls remain unchanged.

## Use

Use an existing Python 3.11+ interpreter; there are no third-party dependencies. Supply the exact downloaded CSV outside the repository. During the parallel build, run commands through the shared pool described in `TEST_POOL.md`.

```sh
python published_reference.py /external/source/43588_2025_826_MOESM4_ESM.csv \
  --output /external/reports/published-reference.json
```

For a separately authorized, provenance-qualified replay from `initial-evaluator-v1`, pass its JSON output, a predeclared absolute tolerance, and a rationale. No tolerance value is supplied as a default:

```sh
python published_reference.py /external/source/43588_2025_826_MOESM4_ESM.csv \
  --replay /external/replay/result.json \
  --absolute-tolerance "$DECLARED_ABSOLUTE_TOLERANCE" \
  --tolerance-reason "$DECLARED_TOLERANCE_RATIONALE" \
  --output /external/reports/reproduction-comparison.json
```

The CLI refuses an existing output, altered publisher CSV bytes, raw-only or generated-population results, missing/duplicate panel keys, nonfinite values, empty eligible support, and undefined eligible correlations. It requires the original image/repeat/pair dimensions, all six ROIs and both methods. It accepts the existing evaluator's `normalized.pair_rows` interface without changing that implementation. Result-file hashes bind bytes; they do not establish native execution or validate declared feature masks. The pure `parse_source_csv`, `source_summary`, and `compare` helpers accept supplied values for software controls; only `load_reference` authenticates publisher bytes, and only the CLI attaches its verified reference-artifact receipt.

The replay reader is bounded to 64 MiB. Full per-voxel reports can be larger: after an independently authorized evaluator run, call `export_replay_summary(result, external_path)` on its returned dictionary to retain only the required metadata and 480 normalized pair rows. This runs no inference, omits per-feature/raw output and extra fields, and refuses overwrite. The compact export is directly accepted by `--replay`; it does not authenticate the run that produced the values.

## Evidence and remaining work

Ten generated tests passed, including an analytic directed-pair mean, cancelling-error counterexample, source tampering, panel omissions/duplicates, wrong population, raw-only substitution, undefined support, tolerance validation, and compact export. The CLI was also run on the authentic publisher CSV and confirmed all 240 rows/480 values. No fMRI, feature, decoder or weight payload was read and no model was run.

This recovers an exact published numerical reference and provides an executable reproduction comparison. **Scientific reproduction and scientific improvement are not established.** Authentic ceiling/mask recovery, native author data/model lineage, evaluator parity, source-conformant tolerance, and controlled replay remain necessary. Paper reproduction and exceeding the source result are separate outcomes; paired paper+data versus paper+data+author-code attempts still require matched access and budgets. Improvement additionally needs a frozen complete endpoint, matching source-method baseline, justified effect and subject-dependent uncertainty. The new source reference does not select favorable ROIs or turn the brain-loss control into the content-loss baseline.

Canonical task/contracts and predecessor implementation files are preserved. Integration should revise only the formerly unresolved *published pair-mean source-data* statement after independent review; the noise-ceiling, replay, uncertainty and outcome-admission gaps remain.
