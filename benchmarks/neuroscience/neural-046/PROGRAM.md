# One program across 13 isolated NEURAL-046 folds

This local program interface has passed fixed-control qualification and an actual common-command integration run, with separate automated reviews. The existing prediction-artifact scorer remains available. This guide describes the runnable local interface; each new attempt still needs its own bounded operator allocation. The versioned TASK and PROGRAM_CONTRACT texts are retained exactly as tested, including their historical construction notes. README.md is also preserved as the exact historical artifact-scorer snapshot included in that source freeze. Current program status is recorded here, in STATUS.md and in manifest.json.

One UTF-8 Python source, at most 131,072 bytes, runs unchanged in 13 fresh sequential environments, one for each exposed source animal. Each process sees only its source, PROGRAM_CONTRACT.md and one fold's fold.json, INPUT_IDENTITY.json and TASK.md. The held source, label and original input variant are committed before trusted preparation reads training tables. No previous-fold state, outputs, feedback, all-fold directory, saved predictions, operator roster or private target file is mounted to a candidate. Ordinary common-CLI invocation uses original training labels and the fixed label submitted_program. The rotated-label variant is an explicitly reviewed operator diagnostic, not an implicit ordinary option.

The candidate command is:

```
python -I -B /candidate/program.py --input /input/fold.json --identity /input/INPUT_IDENTITY.json --predictor-id submitted_program --output /output/predictions.json
```

The actual fixed label supplied by the command must be echoed exactly. Read the current identity and public contract; do not use an operator all-panel fingerprint. Write only predictions.json, at most 131,072 bytes. A complete result contains each current assessment (asset_id, cue_event_row0) exactly once, in any order, with finite binary64 predictions. A whole-fold abstention has the same schema/public identity/label and an explicit bounded reason. PROGRAM_CONTRACT.md gives the exact wire fields, strict number rules and whole-panel precedence. TASK.md defines target windows, units, features and training-only model transformations. No known-program accuracy or training-label-dependence requirement is imposed on an arbitrary submission.

With a separate reviewed operator allocation, the common command is:

```
python3 tools/neurobench.py run NEURAL-046 --program PATH.py --output artifacts-build/FRESH --review REVIEW.json --other-reserve-bytes 102000000
```

The common command dispatches the qualified generic runner in its default original mode. Each candidate has a full 10-second execution allowance, 1.75 CPU, 3 GiB, 32 pids and two numerical threads. Its holder adds 0.25 CPU and 128 MiB; the aggregate remains within 2 CPU/4 GiB. The complete operator attempt allows 210 seconds: 180 work and 30 cleanup, with 24 MB full durable reserve. Setup and capture consume the shared deadline. The runner does not shorten a started allowance or retry; it records unattempted folds when safe time is exhausted.

Every producer is removed and its output committed before any private grading. The runner retains valid answers written before timeout, bounded prefixes of invalid/extra output, full inventories and explicit omissions/truncation. Any failed, invalid or unattempted fold makes the entire panel incomplete, with no scoreable aggregate and no private callback. A fully admitted panel containing an abstention becomes whole-panel abstention with zero private callback. Only 13 complete folds with the exact 2,795-key union yield one committed aggregate and a call to the unchanged artifact scorer.

Operational exit 0 can mean handled incomplete, abstained or complete. Inspect panel_status, score_status, cleanup and full reports, not exit code alone. Complete grading reports equal-source-animal MSE in squared stored dF/F, MAE and bias in stored units, per-animal/condition diagnostics, normalized error where defined and descriptive comparisons with five fixed regularized baselines. Keep the full score; there is no scientific pass floor. Finite extreme predictions can produce an explicit unsupported-numerics outcome. Candidate source cannot attest its prior training history or fit count. Final files, when present, are final/output/score.json and aggregate.json; terminal_outcomes.json preserves the fixed outcome roster.

This is retrospective event-feature prediction of released processed fluorescence, not native raw-neural-signal understanding, causal identification or future-data-free forecasting. All 13 animals and the development outcomes are already exposed. The union of all training folds contains all evaluation targets; fresh processes enforce available runtime files, not erased author knowledge, an unseen biological cohort or a guarantee against memorization. Upstream whole-session preprocessing remains. Unresolved anatomical, missing-lick and lifetime provenance, the canonical licking-controlled analysis and condition holdout remain open. Differences among penalized baselines do not identify distinct conditional E/N information because added correlated columns may redistribute shrinkage.

The original/rotated developer programs and privileged stale copier are implementation diagnostics. The stale copier remains structurally valid and receives its complete ordinary score; only its known-procedure recomputation comparison may fail or be inconclusive. No favorable threshold, alternate rotation or hidden performance rejection is introduced. This adds no dataset/task ID, reference/scorer count, new model-service result or full research-contract claim. Existing source-data access and reuse rights are unchanged.

Model normalizations are fitted on the active training fold. This does not undo upstream whole-session fluorescence processing; declared feature vocabularies may use all event metadata. Reported SD and SE are descriptive summaries, with overlapping training folds, rather than inferential confidence intervals or p-values. Source freezing constrains this attempt and does not erase prior exposure to development outcomes.
