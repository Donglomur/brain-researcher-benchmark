# Global rate-gain calibration for restricted VALID predictions

This source component defines a modest calibration baseline for the original MC_Maze 20 ms task. It selects one positive scalar using correctly restricted VALID predictions from the released author checkpoint, then applies that frozen scalar without accessing labels. It is not a new model, a reproduction of an identified Table 2 checkpoint, or evidence of state-of-the-art performance.

## Fixed method

The prospective, ordered gain grid is `1, 8/9, 9/8, 4/5, 5/4, 2/3, 3/2, 1/2, 2`. The selector maximizes the original canonical VALID co-bps metric. Exact ties choose the first grid entry, so identity wins an exact tie. There is no search beyond this grid and no tolerance-based tie rule.

The same transformation kernel is used for selection and output: it preserves the rate dtype, so selection evaluates the rounded values that would actually be written. Gain 1 copies the entire prediction file byte for byte. Other gains scale all eight declared rate fields consistently, including the TRAIN rates used by the canonical velocity decoder; dimensions, trial order, units and non-rate metadata remain unchanged. Redirected HDF5 links, virtual datasets and external storage are refused.

Canonical zero-rate flooring and NaN-target masking are evaluated on disposable copies. They cannot mutate the frozen reference or later grid candidates. These evaluator rules do not authorize substituting old unrestricted `train_rates` for restricted VALID predictions.

## Prediction and label boundary

Method, source and reference lineage are frozen first. The protected selector authenticates and privately snapshots the complete reference prediction before admitting VALID target content. Its source-only preparation does not read targets or qualify model inference. The production transform requires authenticated saved selection and bounded-owner closure evidence; it has no target operand.

Method, source and runtime descriptors are trusted operator configuration. A participant-supplied manifest or success flag is not runtime qualification or proof of owned closure. The bounded host joins the selected source and method to genuine saved execution and closure evidence.

The current transform admits only the same genuine VALID reference snapshot selected during development. It does not accept a TEST phase override or turn a transformed prediction into a historical author artifact. A distinct authentic TEST prediction/checkpoint binding and candidate-aware original-task grading route remain future work.

## Evaluation and limits

The existing VALID grader already has a distinct candidate role. After a real transform, its complete saved result becomes the candidate method binding, with the same packet identity and the transform program identity. The unchanged `freeze_prediction` records that candidate snapshot, and the existing bounded `score_pair` compares its freeze with the original reference freeze. No candidate is relabeled as an author reference. These future method, freeze and grading records do not yet exist.

Selection uses co-bps alone. A later paired comparison must report co-bps, forward-prediction bps, PSTH R-squared and velocity R-squared using the original evaluator and TRAIN decoder handling. Positive scaling does not establish improvement in all four metrics; decoder refitting and regularization can change the velocity result. VALID selection is development evidence, not an independent test result.

The retained task has 574 VALID trials with 137 observed neurons over 35 bins, plus 10 unobserved future bins. The raw VALID input container also holds protected fields and must not be exposed to the worker. The separate restricted-input and owned-episode components supply the projection and inference-ownership contracts. Their actual model/runtime qualification is not supplied by this component.

The selected released `reach_nlb_smoothing_proposal_36d` directory has an adjacent saved configuration declaring phase `val`, 20 ms bins, 137 held-in and 45 held-out neurons, 10 forward bins and co-smoothing. Under the pinned preprocessing code, this implies TRAIN-only optimization inputs if the actual run followed that saved configuration. The trainer nevertheless selects checkpoints using VALID co-bps, so VALID is not an untouched evaluation cohort. The actual run-to-config linkage, retained local weight-to-release identity, exact checkpoint-to-Table-2 identity and exact DANDI revision lineage remain unproved. The 32 trajectory averages are Monte Carlo inference samples, not independent training replicates. The public status of original TEST targets also prevents a new hidden-test claim.

## Resource and verification scope

The proposed selector uses one bounded child for the whole nine-gain search: 2 GiB, 600 CPU seconds soft / 605 hard, 720 seconds of work plus 60 seconds for cleanup, and one numerical thread. These are proposed limits, not measured adequacy or authorization to execute. Runtime, image, source, private mounts and owned closure still require fresh admission.

Generated controls use small arrays to check the mathematical direction of calibration, exact identity/ties, dtype agreement, target ordering, transformation guards and changed ownership/report joins. They do not run author inference, fit the real calibration, or score original predictions. Local source-test dependency versions and the admitted production dependency versions must be reported separately; refusing an incompatible production loader is not positive runtime qualification.
