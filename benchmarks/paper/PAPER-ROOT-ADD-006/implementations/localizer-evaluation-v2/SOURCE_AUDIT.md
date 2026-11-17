# Original held-out localizer endpoint

This component concerns Fig. 3B–D of [Russek et al. (2024)](https://www.nature.com/articles/s41467-024-48547-z). The earlier `initial-evaluator-v1` implements a prospective participant-held-out behavioral prediction extension. Its MSE cannot evaluate this endpoint.

The cached primary article fixes the Fig. 3 independent sampling unit as participant, with 19 participants after the two behavioral exclusions from 21 recruits. Localizer trials, seven cross-validation folds, classifier training times, and test times are dependent measurements within each participant. Fig. 3C reports the group mean accuracy and participant SEM along matching train/test timepoints; Fig. 3D reports the group mean train-by-test accuracy map. Accuracy concerns the three outcome stimuli: a held-out example is correct when its matching outcome classifier has the highest activation.

The paper trains each outcome classifier against the other six images and an equal number of null examples. Seven-fold cross-validation supplies six sevenths of examples for training and one seventh for evaluation. The paper selects the lasso penalty by the mean diagonal accuracy of the same cross-validation map, obtaining 0.002. Consequently that selected-penalty map is a reused model-selection estimate; it is not an independent final holdout. Neither a newly invented participant split nor a nested behavioral target is the original endpoint.

## Time domains must be reconciled

The Fig. 3D caption states test times from −350 to 800 ms. The pinned `MEG_Code/Epoch_Train_Data.m` instead creates −250:10:600 ms epochs. The task-decoding script creates classifiers at 0:10:500 ms, containing 51 times, while the article methods also describes 50 timepoints and 10–500 ms. These are distinct source statements. This component must not silently crop the figure domain, interpolate unavailable epochs, or describe any chosen smaller map as the complete original Fig. 3 evaluation.

The epoching script retains the first three localizer runs, checks 140 events per run, and concatenates three run arrays. The paper describes 20 presentations per image per block for seven image identities: 420 presentations per participant. Subject 1 had additional localizer runs, but the pinned epoching script still retains three. Each native event-to-epoch and sensor identity join requires authentic validation; these counts do not supply that validation.

## Existing exact source evidence

All code references use author revision `1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612`.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| [Primary article XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11106265/fullTextXML?format=xml) | 266725 | `11487db38d3e9be58baa042ca5a09c6fb13cd10eb67bb5dcc19443ec370a5505` |
| [Pinned source inventory](https://data.jsdelivr.com/v1/package/gh/evanrussek/MEG_Heuristics_Risk_Preferential_Information@1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612/flat) | 5055 | `a4bdbe37cbd3ca705bfd9c49dd273b5579f23d391da855c5a06421005e5c9339` |
| [Epoch_Train_Data.m](https://github.com/evanrussek/MEG_Heuristics_Risk_Preferential_Information/blob/1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612/MEG_Code/Epoch_Train_Data.m) | 5237 | `ddf33f460808c6bfa525483e7d2b8cd44522ccc2f50e14f1bacee023ab87272d` |

| [Train_Classifiers_Apply_To_Heldout_Loc.m](https://github.com/evanrussek/MEG_Heuristics_Risk_Preferential_Information/blob/1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612/MEG_Code/Train_Classifiers_Apply_To_Heldout_Loc.m) | 11042 | `8b9bbdd1f04121aa924fc5afa5d7304b3a89d6e934469c8e76371394bc9f97ba` |
| [Classifier_Analysis.m](https://github.com/evanrussek/MEG_Heuristics_Risk_Preferential_Information/blob/1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612/MEG_Code/Classifier_Analysis.m) | 5374 | `51c2cf388b968a3bf5fde258517c63e9bdaf7278a3a160e16bf418406ceccecb` |

The two localizer-specific scripts were recovered by exact-revision public CDN transport and inspected statically. Their hashes match the previously retained pinned inventory. Both requests returned HTTP 200; acquisition totaled 16416 bytes, with no failed bodies or dataset acquisition. Author code is not redistributed here.

## Recovered protocol discrepancies

| Item | Article | Deposited localizer training script | Deposited analysis script |
| --- | --- | --- | --- |
| Folds | Seven | Five, with 12 held-out examples per image class per fold | Consumes pooled held-out predictions; does not store/reconstruct fold identities |
| Cohort | Nineteen for Fig. 3B–D | All 21 recruits | All 21 recruits, including SEM denominator |
| Train/test grid | Multiple descriptions; Fig. 3D test domain −350 through 800 ms | Both −350:10:850 ms | Both 0:10:500 ms |
| Penalties | Selected 0.002 using mean diagonal CV accuracy | Active grid 0.005:0.001:0.010, with 0.001:0.001:0.004 only in a comment | Expects 0.001:0.001:0.010; plots index 2 (0.002) |

The training script randomizes each image's 60 trial indices and partitions them into five groups of 12, reusing the assignments across train times within each participant/penalty. The randomization occurs inside the penalty loop, so different penalties can use different fold draws. No seed, trial IDs, or fold assignment is saved with the logits. Null examples are taken from the training rows at −200 ms; each fold has 336 image examples and 336 null examples. `scaleFunc` is called independently for the augmented training matrix and each held-out image-class matrix across test times. This class-conditioned preprocessing must be exposed in a future author comparator; replacing it with train-only scaling changes the historical recipe.

The training script references `pred_reg_epoch_im` when creating labels, but that variable is never defined. Its expected revised epoch directory differs from the directory populated by the retained epoching script. The analysis script expects the older activation directory, does not subset a wider loaded time axis to its 51 declared bins, and ends with undefined `this_subj_mn_class`. These are executable reproduction blockers, not permission to silently edit the scientific design.

The recovered metric is unambiguous: take the first maximum over classifier channels 1–3 in **logit space**, then pool correctness across all 180 held-out outcome trials. All seven stimulus classes remain required in the source panel and training history; choice trials are not part of the outcome-accuracy denominator. Equal class counts make pooled outcome accuracy equal the three-class mean. Group summaries give each participant equal weight, with sample-standard-deviation SEM. The source computes a seven-channel classification diagnostic too, but its untrained choice channels contain zero logits; this is not the paper's three-outcome accuracy and is not promoted as a control here.

`localizer_score.py` implements this recoverable metric and separate 21-person source-script / 19-person paper-figure summaries. It accepts externally supplied five- or seven-fold identities without generating, converting, or authenticating them. Five-fold class counts are checked against the released script; the exact seven-fold allocation remains unrecovered. No grid is selected, cropped, interpolated, or averaged into a newly invented scalar endpoint. Each declared map cell is retained. The public arithmetic interface therefore cannot establish that the original complete Fig. 3 time domain or original split was delivered.

Reproduction and improvement are separate first-class future outcomes. Neither is qualified by this arithmetic component. Native event-table conversion, authoritative event and sensor joins, exact original seven-fold assignment, missing scaling implementation, temporal-domain reconciliation, full author baseline, companion permutation threshold, paired paper+data versus paper+data+code delivery, access controls, and a frozen improvement comparison remain unresolved. The plotted threshold 0.3594 refers to another script that is absent from this pinned tree; it is not treated as a candidate success threshold. No native preparation, model fit, new solver trial, or scientific qualification has occurred.
