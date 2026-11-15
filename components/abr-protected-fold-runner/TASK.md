# ABR released-background classification

Predict `p_6n`, a probability from 0 to 1, for every held-out animal in this
fold. `/input/FOLD.json` gives the current outer-training labels, current test
IDs, and four inner folds restricted to outer-training animals. All 104 animal
objects are in `/input/animals/<animal_id>.json`. No test label is supplied.

The waveform route supplies all released numerical samples and integer sample
indices, with every record and repeated level retained. The layout-only route
supplies the same record layout, stimulus, numerical level, sample indices and
repeat indices, with all sample values removed. These are within-release index
and numerical-value representations; physical voltage/time calibration is not
claimed. Object IDs are opaque and have no biological meaning.

Your frozen Python program runs once in a fresh container for this fold. Fit all
preprocessing, category vocabularies, feature selection, tuning and probability
calibration using the supplied training animals and inner folds only. Refit the
chosen rule on the complete outer-training set and predict every outer-test
animal. Account for ragged records and unknown layout categories explicitly.
Do not read another fold's labels, trained state, outputs, logs or conversation.
The runner carries only the frozen method source between folds.

Write one JSON list to stdout, with exactly one object per current test animal:
`{"animal_id":"animal_<64 hex>","outer_fold":0,"p_6n":0.5}`.
Use the active fold index from FOLD.json. Output no explanatory text. The
evaluator imports no candidate code. Missing, duplicate, reordered-to-wrong-fold,
nonfinite or extra-field predictions do not receive a partial score. Both
complete 104-animal streams must be committed before the private final score.

The primary measure is pooled out-of-fold balanced accuracy at a fixed 0.5
cutoff (equality predicts 6N). The paired waveform versus layout-only difference
is descriptive for this public cohort. No claim of causal genotype sensitivity,
clinical performance, new-laboratory generalization or unseen-test performance
follows. Acquisition/batch information may predict these released labels.

The declared per-fold allowance is 600 seconds, one CPU and 2 GiB memory, with
no network or package installation. Writable /work and /tmp are private fresh
128 MiB tmpfs mounts. Python/NumPy/SciPy/scikit-learn versions are supplied by the
separately admitted runtime. No previous fold state or feedback is available.
