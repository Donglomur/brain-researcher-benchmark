# LMU source recovery for native retrieval admission

The archive at [LMU record 596, file 5](https://data.ub.uni-muenchen.de/596/5/code.zip) was inspected directly from the existing cache. Its 68,222 bytes match SHA-256 `22f245506d4c8a87887e1bd6cfbb47c133223fa5c2989963c27449bc0fcdcd1c`. No authentic EEG, private targets, or author model were accessed for this component.

The inspected source establishes a more specific Figure 3a input path than the historical registration's generic epoched-data description:

| Source locator | Consequence for preparation |
|---|---|
| `figure_3a.m:47–55`; `+dataloader/load_cont_data.m:15–20` | Retrieval starts from continuous `ret1/<session>_ret1.mat` and `ret2/<session>_ret2.mat`, variables `ret1` and `ret2`. Merely loading `_segm_resp.mat` does not reproduce this branch. |
| `figure_3a.m:38–41,54–55` | Detect the last exhalation trough strictly between 0 and 3 seconds from cue onset, extract a ±3-second interval, and require a complete interval. The helper is shared with other branches, which may use different windows. |
| `+util/splitTrials_breathFeat.m:119–171` | Cue description is literal `S 41`; marker sampling rate is declared as 1000 Hz. The behavior file has 19 ordered columns. Trial labels are copied by positional row index. |
| `figure_3a.m:59–60`; `+dataloader/load_loc_data.m:16–23` | The independent localizer uses `<session>*_loc_segm.mat`, variable `loc`. This is separate training data, not retrieval cross-validation. |
| `figure_3a.m:16–21,123–135` | Training support is −0.15 to 1.5 seconds and retrieval support is −2 to 2 seconds. Both are downsampled to 100 Hz, giving nominal 166 × 401 time bins; that dimension is arithmetic from the declared grid, not observed data. |
| `figure_3a.m:193–225,227–234,264–270` | `Stimtype` 1/2 is object/scene. Remembered and nonremembered masks require old items and exact `ExemplarAccuracy` 1/0. `Answer1Accuracy` appears in a separate behavioral denominator, not these class masks. |

The standalone adapter implements the source metadata/class-mask portion. Respiratory-event extraction, filtering, interpolation and final numerical AUC evaluation are not implemented here. The original prospective evaluator is preserved unchanged.

Several details prevent calling the archived figure script a qualified author baseline:

- `phaseAxis` is referenced without a definition in the archived Figure 3a script. An operator must recover the intended setting from an authenticated version; choosing it silently would alter the analysis.
- Localizer and retrieval are separately standardized, and each outcome group is standardized again before classification. This differs from the earlier Python recipe's training-only transforms.
- PCA components are retained using `eigValsCum < 95`, not a cumulative-at-least-95% rule. `my_PCA` projects retained components back into channel space when `updateSens == 0`; the subsequent physical-channel searchlight therefore is not, by itself, a label/dimension defect.
- The script exposes a searchlight branch and later statistical construction, but neither a scalar published AUC comparator nor a complete native execution/dependency record has been recovered. A remembered-minus-nonremembered t-value is not decoding accuracy.

The prior package records immutable GitHub commit `b3ecba26b8820a3837f50e67fe4ccde7899dbc32`. Its previously inspected-view hashes for `+dataloader/load_loc_data.m` and `+util/splitTrials_breathFeat.m` exactly match this archive after CRLF-to-LF normalization. Figure 3a does not match after that normalization: the archive has 13,565 raw bytes and LF-normalized hash `eddcd6e055539fd6e3452a6d07ffc57fea0ca6f4ef90def6f0d51a51b7e12540`; the prior GitHub view has 11,124 bytes and hash `3556325823d8106f5a31e8314ffa2795d9116d2228df45fdd8f11740bc9b904f`. Thus a blanket “same code, different line endings” reconciliation is unsupported. The GitHub hash here is inherited inspected-view evidence, not a newly downloaded raw-file hash.

Native final-article qualification requires exact version reconciliation, authentic metadata/marker and EEG joins for the full 18-person cohort, native dependency pins and numerical checks, author AUC results on the original support, and a frozen participant-level improvement comparison. This audit narrows those requirements but does not complete them.
