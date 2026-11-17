# Original-fold oddball AUROC scoring

This component supplies the missing prediction-to-AUROC path for the paper's all-shape-trained oddball decoder. It preserves six directional run folds, all eleven shapes, twenty sensor participants, and both smoothing branches. It computes shape-specific time courses from frozen predictions and evaluator-owned epoch metadata. It does not fit a decoder or establish a published-baseline comparison.

The predecessor [sensor RSA component](../initial-evaluator-v1/README.md) remains unchanged. RSA and regularity correlations remain companion analyses, separate from decoding accuracy.

## Recovered source behavior

The author snapshot is `133669b577b5ae341cd0842dfb0e7f0af85c0020`. Four cached public source files were checked against their retained source lock and an earlier public source copy; their exact identities appear in [source-pins.json](source-pins.json). No new downloads, raw recordings, neural targets, fitted models, or original decoder results were accessed for this component.

The operative shared-training decoder is `scripts/msm/_04_sliding_estimator_ref_out_decode_per_shapes.py` inside the author's [modified pipeline archive](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/MEG/mne-bids-pipeline.zip). It selects `is_early == 'late'`, concatenates reference and outlier epochs, trains one decoder jointly across shapes, and scores each shape separately. Its binary labels are **reference = 1, outlier = 0**. Scores in this interface must increase toward reference; no post hoc inversion or above-chance clipping occurs.

| Source behavior | Scoring implementation |
|---|---|
| Train 1,3,5,7 / test 2,4,6,8, then reverse | First two folds |
| Train 1,2,5,6 / test 3,4,7,8, then reverse | Next two folds |
| Train 1,2,3,4 / test 5,6,7,8, then reverse | Last two folds |
| Run 08 absent only for sub-10 and sub-11 | Exact twenty-person, 158-run inventory; no fabricated run |
| `np.mean(scores, axis=0)` after shape-specific scoring | Equal fold mean; predictions from overlapping folds are never pooled |
| `np.mean(all_decod_perf, axis=0)` in the plot script | Equal participant mean; all participant/fold curves retained |
| Decoder/config order starts rectangle, square | Explicit decoder order, distinct from the RSA component's square, rectangle order |

AUROC uses average ranks for exact ties, equivalent to the probability that a reference score exceeds an outlier score plus half the probability of equality. A missing class is undefined and raises an error. Unequal class counts do not change the weighting unit from folds to trials. The full output has `20 × 6 × 11 × 301` AUROCs per branch, alongside fold-averaged participant curves, group means and per-cell class counts. No scalar primary endpoint, selected time window, uncertainty claim or win flag is emitted.

## Input and execution

Use an existing Python environment with NumPy; no MNE, scikit-learn, network access or model is required by this scorer. From this directory:

```sh
python3 oddball_auroc.py packet.json result.json
```

The result is created exclusively and includes a SHA-256 of the packet bytes. Keep packets and result arrays outside Git. The command is an operator-side utility, not a participant sandbox or protected evaluation service.

`packet.json` contains exactly:

- `source_revision`: the pinned revision above.
- `score_orientation`: `higher_is_reference`.
- `times`: the pinned code's 301 seconds values, `-0.1 + index/250` for index 0 through 300.
- `subjects`: twenty entries, each with `subject`, `trials` and `branches`.

Each `trials` entry is a retained-epoch metadata row with exactly `trial_id` (unique stable string), `run` (integer 1–8), `shape` (source shape name), `condition` (`reference` or `outlier`), and `is_early` (`early` or `late`). Supply all retained epochs, including early epochs. The original metadata routine classifies the first six miniblock trials **before** applying `Epochs.selection`; numbering the retained rows after rejection would be wrong. This scorer consumes the resulting classification and does not pretend to reconstruct it from incomplete retained observations. Stable identifiers must bind to the prepared source epoch; their truth and full retained-epoch coverage require independent source authentication.

`branches` contains exactly `unsmoothed` and `smoothed`. Each maps to six objects containing `fold`, `trial_ids` and `scores`. `fold` uses the names in `FOLDS` in [oddball_auroc.py](oddball_auroc.py); `scores` is an array with one row per listed identity and 301 time columns. A fold must contain every late test epoch once and only once, with no training or early epoch. Row order may differ from metadata order. Fold names, participant identities and branches are checked explicitly. Every directional training set retains all shapes, and every shape-specific test set must contain both classes.

The Python `fold_plan(subject, trials)` API returns the corresponding training and test identity lists. Candidate architecture is unrestricted by this scorer. An independent execution protocol must enforce all-shape training on those training identities and prevent access to final targets. Prediction rows alone cannot prove training-fold isolation, honest preprocessing or model provenance.

## Remaining scientific limits

The exact published numeric baseline, authentic retained epochs, and Version-of-Record matching are still unresolved. This is a source-code scoring component, not an improvement-ready benchmark.

The cached decoder actively uses direct magnetometers, `StandardScaler` followed by liblinear logistic regression, and unsmoothed epochs. A 25-sample uniform filter is commented out; the plotting script expects both smoothed and unsmoothed result files. This does not establish which smoothing implementation produced the published smoothed results. This component preserves those branches separately without generating either one.

The pinned configuration specifies −0.1 to 1.1 seconds, while the improvement contract describes −0.15 to 1.15 seconds and epoch normalization. The archived decoder's scaling is fitted within each training fold, with no explicit per-epoch normalization in that script. These differences must be reconciled with the paper version and authentic preparation before author-calibration claims. The scorer's strict axis is deliberately labeled as the pinned-code axis; it does not silently replace the contract's preprocessing.

The plotting script selects significant positive clusters from participant-wise regularity correlations and then averages AUROC over their union. Those data-selected times are a descriptive source summary, not an independently fixed primary endpoint for a new candidate. It also uses `sqrt(19)` for one plotted AUROC error band despite loading twenty subjects. This component exposes participant curves and class counts and makes no choice about that display denominator, temporal selection, meaningful gain, paired uncertainty, or paper-win threshold. Recovery and predeclaration remain necessary.

Generated controls cover tie-aware AUROC against a pairwise oracle, below-chance retention, unequal fold sizes, metadata/prediction alignment, missing classes/runs, original folds, complete cohort and separate branches. They establish software behavior only. Test outcomes and resource receipts are recorded in the external handoff; no authentic model or data run is implied.
