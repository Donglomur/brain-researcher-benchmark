# Decision-times complete contrast panel

This additive scorer addresses the original Table 1 endpoint: held-contrast latency errors for all six intervals, encoding (event 1→3), decision (event 3→5), and behavioral RT, separately under accuracy and speed instructions. It keeps the three source laws as 54 distinct reference RMSE cells and reports full-data latency R² plus the 18 Fechner accuracy R² companions. Reproduction and improvement are separate outputs. No scalar aggregate, numerical tolerance, superiority threshold or paper-win decision is invented.

The concrete repair concerns uneven contrast support. The pinned author helper predicts every participant on the condition's global contrast grid. The initial evaluator instead restricts predictions to participant/contrast cells containing observed trials. At a contrast observed only for participant A, predictions from B must still enter the equally weighted predicted mean. This scorer requires those predictions and the corresponding fit declaration. Its generated control has observed A=0 ms and predictions A=0/B=100 ms: the held-contrast error is 50 ms, not zero.

The implementation imports the predecessor's strict five-event parser, interval identities and R² function; it does not duplicate those kernels or change predecessor files. New code implements global fold coverage, complete panels, separate behavioral/HMP populations, fixed-target binding, unrestricted supplied predictions and source-model reproduction comparisons.

## Source semantics

At each omitted contrast, the observed duration is the mean over all retained trial rows at that contrast. The predicted duration is the mean over **all participants'** predictions at that contrast, including participants with no observation there. RMSE is the square root of the mean of these squared differences over contrasts. Folds are within-participant contrast exclusions, not participant holdouts. Fit declarations use each participant's actual support minus the globally omitted contrast; the omitted contrast need not have been present for that participant.

Full-data curves use separate supplied refit predictions. Observed latency and accuracy curves first average within participant/contrast, then across the participants observed at that contrast. Predicted curves average every participant on the global grid. Accuracy retains incorrect responses. Constant observed curves yield undefined R² (`null`), not a fabricated perfect fit. Predictions remain in milliseconds, contrasts in percentage points; negative linear latency predictions are not clipped.

The author helper matches the prediction grid after one-decimal rounding. This component accepts grids separated by more than 0.1000000001 percentage points, where exact keyed matching is equivalent, and rejects denser ambiguous grids for native review. The recovered integer stimulus-trigger route satisfies this condition; no trigger values are converted, rounded or replaced with nominal display contrasts here.

Notebook source cells 7, 19, 21, 27 and 28 define the RT, six-interval and combined-stage panels and companion accuracy summaries. Source cell 5 forms behavioral population B before HMP; cell 16 forms interval population H later. Existing external metadata audits found 26 participants, 28,126 H trials and all six intervals, and matched source cached counts and integer trigger labels. They did **not** authenticate B's original keys and producing state or establish historical 512 Hz target identity. This scorer therefore requires independent B and H blocks; it never derives the RT population by dropping the interval column from H. H must join to consistent B metadata, but B may contain additional trials. Successful joins are software consistency checks, not source authentication.

## Input and output

`targets.json` has schema `decision-times-panel-targets-v2` and two blocks:

- `hmp`: an existing `decision-times-export-v1` payload, including the full trial inventory, five event times, distinct model endpoint and behavioral RT. Sample rate must be 512 Hz. An empirical export retains all 26 source participants; smaller fixtures must explicitly say `engineering_control`.
- `behavior`: `time_unit: ms`, `contrast_unit: percent`, its own retained/excluded `trial_inventory`, and all responded `trials`. Each trial has participant, epoch, condition, contrast_percent, side, response and rt_ms. Every participant must occur in both conditions for every panel target.

`predictions.json` has schema `decision-times-panel-predictions-v2`, `access_condition` (`paper_data` or `paper_data_author_code`), and `references`: exactly three methods named `fechner`, `pieron`, `linear`. It also supplies either or both of:

- `reproduction`: exactly those three named methods, scored against their corresponding reference across all 54 cells and companion metrics. Output includes numerical differences and `reproduction_pass: null` until independent source qualification and tolerances exist.
- `candidate`: an arbitrary named method, with all 18 target/condition cells. Its error difference against each of the three source laws is reported separately. Candidate equations or architectures are unrestricted.

Each method has `targets_sha256`, `latency_selection: all_responded`, `time_unit: ms`, `contrast_unit: percent`, and complete `held_out` and `full_data` prediction lists. Each row has `target`, `condition`, `participant`, `contrast_percent`, `fit_contrasts_percent` and `latency_ms`. The two lists cover every participant × global contrast × target × condition. The full-data list has no held contrast excluded. Full-data Fechner rows require `probability_correct` across the entire panel; candidate accuracy is optional but cannot be partial. These values must come from the same latency fit for source reproduction, a provenance obligation not independently certified by the supplied JSON.

`target_digest(targets)` computes SHA-256 of sorted-key compact UTF-8 JSON (`allow_nan=False`), binding both populations, units, identities, exclusions and values. Both references and tested methods must name that digest. This prevents changing HMP event estimates between methods within an evaluation; the operator must independently establish the target file and protect it from the participant. It is not an access-control mechanism. The CLI additionally records exact input-file SHA-256 values.

The generated examples in `tests/test_panel.py` demonstrate every field and both outcomes. To score already prepared operator exports:

```sh
python3 -B benchmarks/paper/PAPER-paper-signal-add-019/implementations/contrast-panel-v2/panel.py \
  /external/operator/targets.json /external/operator/predictions.json \
  --output /external/operator/result.json
```

Authentic inputs and outputs belong outside Git; result files include target means and participant metadata. Paired paper+data and paper+data+author-code evaluations must use the same authenticated targets, references and declared budgets; the access-condition label alone does not attest actual delivery. Author-code delivery must omit cached notebook outputs, estimates, parameter/result CSVs, plots and pickles. No paired participant trial was run here.

## Verification and limits

The bounded generated suite covers global participant predictions on ragged support, 9:1 observed-trial asymmetry, full panel coverage, independent full-data R², all-response accuracy, separate B/H populations, interval identities, target substitution, explicit reproduction outcomes, fold leakage, incomplete panels, nonfinite values, units, rate, keyed order invariance and CLI file pins. It uses only Python's standard library, through the shared two-slot test pool.

No source was downloaded, no authentic CSV values or private solver answers were read, and no scientific preparation, HMP inference, law fitting, model trial or dependency installation occurred. Source files and metadata audits were reused. Reproduction is now a first-class outcome under current steering; the older task contract's calibration-only wording is preserved pending central revision. Neither outcome is scientifically qualified by this component. Authentic target/cohort lineage, source runtime and parameter-fit provenance, reference numerical qualification, reproduction tolerances, protected delivery, resource/access budgets and the full-panel improvement/uncertainty policy remain unresolved.
