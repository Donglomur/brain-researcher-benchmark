# NEURAL-062 phase API

This is the legacy full-release population-summary condition with a versioned
two-phase orchestration extension. All 136 held mouse/image-set/context cases
and CONTEXT/PRE/POST/PRE_POST panels remain. Image classes are shared across mice.

Both F and I scripts are committed before any programme input is exposed. F uses
a fixed precommitted analysis recipe. I may adapt its analysis using only the 73
training mice. No human/model feedback channel or live agent provider is supplied
by this source. The precommitted I script implements its adaptation inside FIT.

Each FIT invocation gets VIEW.json, train.npy and TRAIN_GROUPS.json. train.npy
contains features, original class labels and original hierarchical sample weights.
TRAIN_GROUPS is a compressed run list of opaque training mouse IDs; counts sum to
the train rows. It grants no access to the protected validation/test mouse IDs.
If an I script chooses internal validation, all such groups must be training mice.
No new canonical inner split is selected. F and both fixed references do no tuning.

FIT writes /output/result, capped at 32,000,000 bytes and 1,024 tree nodes.
The host captures exact files, verifies them, retires the process, and mounts
only that cell's sealed state read-only at /state in a fresh INFER invocation.

INFER gets VIEW.json and query.npy only, with public opaque row IDs. It receives
no training matrix, class labels, target map, other case state, network or feedback.
It writes exactly result/prediction.json in the legacy probability grammar.
All expected IDs and eight finite probabilities are required; simplex tolerance
is 1e-6 and log-loss flooring 1e-12 is preserved by the protected grader.

The 15 validation mice are protected diagnostic evaluation; the 19 test mice are
protected primary evaluation. Neither may tune or select a recipe. All 3,264
owner/mode/case/panel predictions must be captured and all 6,528 phases retired
before target evaluation. A failure invalidates the complete comparison, preserves
its error and unattempted coordinates, and never removes a hard case.

The fixed references are the unchanged C=1 logistic recipe and a prospective
scikit-learn 1.3.2 HistGradientBoostingClassifier with the parameters in
reference_phase.py, early_stopping=False and random_state=0. Both use exactly
train-only original median imputation and weighted scaling. Both references are
identical across F/I modes; neither is a learned result or proven competent model.
Reference pickle state is used only inside the isolated reference inference process;
the host and candidate evaluator never deserialize it.
