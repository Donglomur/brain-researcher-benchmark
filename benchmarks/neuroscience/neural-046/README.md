# Released-fluorescence prediction artifacts — NEURAL-046

The isolated scorer, ordinary-file interface and actual common benchmark command have passed. This component grades prediction files; a candidate-program/training interface and the full canonical benchmark remain incomplete.

Submit one prediction for each of the 2,795 fixed cue identities, or abstain from the whole task. Evaluation reports source-animal-equal MSE, MAE, signed bias, per-animal and per-condition diagnostics, training-scale-normalized error where defined, and signed comparisons with five frozen regularized baselines. Larger effects or statistical significance are not rewarded.

All 13 source animals and their outcomes are exposed development data. Across leave-one-animal-out folds, the union of training labels contains every evaluation target. The private grader mount is an execution boundary, not a claim that targets are secret. An answer file cannot establish its training procedure, prevent memorization, or certify generalization. Separate future per-fold program isolation would need its own qualification and would still use the same exposed source animals.

The task uses released processed fluorescence and explicit methods. It is not native/no-tools raw-neural-signal comprehension. Anatomical, missing-lick and lifetime-history identities remain unresolved. Whole-session upstream preprocessing prevents a future-data-free forecasting claim. Differences between the five penalized baselines do not isolate conditional E/N information: added correlated features can redistribute nuisance shrinkage. The broader canonical licking-controlled/condition-holdout NEURAL-046 question remains open.

Keep the full score, including coverage, numerical status and all animal/condition diagnostics. A primary scalar alone does not establish scientific success.

Run through `python3 tools/neurobench.py score NEURAL-046 --submission FILE --output NEW_DIRECTORY --review REVIEW.json --other-reserve-bytes BYTES`. Each local execution uses an explicit reviewed resource allowance. No LLM is started by this command.
