# NEDS binned-trial evaluator

This package implements a complete binned-trial evaluation component for `PAPER-paper-method-replacement-005`: closed task input packets, a runnable train-only reference, source-derived scores, complete source-session coverage, paired method comparisons and explicit trade-offs. It does not run or replace the native NEDS transformer, acquire ONE data, or establish scientific reproduction. Scientific qualification remains **unknown**.

See the [task implementation note](../../docs/initial-evaluator-v1.md).

Requires Python 3.10+ and NumPy. No installation, network call or authentic/model run is performed by tests.

```sh
python3 -m unittest discover -s tests -v
python3 neds_evaluator.py /absolute/bundle.json /absolute/reference-results.json
python3 neds_evaluator.py /absolute/bundle.json /absolute/comparison.json \
  --submissions /absolute/predictions.json --methods multitask task_specific
```

The default rejects missing members of the pinned 74 training / 10 heldout session lists. `--engineering-subset` is permitted only with `evidence_kind=generated_engineering` and labels the report accordingly. It cannot admit a reduced authentic cohort. A valid 84-session generated control demonstrates membership enforcement, not authentic population coverage.

## Input arrays and identity

A bundle has exactly `schema="neds-binned-panel-v1"`, `source_commit` equal to the pinned NEDS commit, `evidence_kind` (`generated_engineering` or `operator_supplied_unqualified`), and `sessions`.

Each session has exactly these fields:

| Field | Meaning |
|---|---|
| `eid` | An exact UUID from `cohort.json`. |
| `animal_id` | Declared biological animal identity; an authenticated full EID/PID/animal join remains required. |
| `bin_width_seconds` | Exactly 0.02, with 100 bins per trial. |
| `unit_ids` | Nonempty ordered unique strings shared by training and evaluation. |
| `source_identity` | Nonempty provenance declaration identifying objects, revisions, camera, original trials, unit eligibility and preprocessing. The declaration is retained by the input digest; this component cannot authenticate it. |
| `train`, `validation`, `test` | Split objects with `trial_ids`, `spike`, `choice`, `block`, `wheel`, `whisker`. |

`spike` is nonnegative integer counts `[trial,100,unit]`; model predictions are expected counts per bin, not Hz. `wheel` and `whisker` are finite continuous `[trial,100]` arrays. `choice` is raw `-1/+1`; `block` is raw `0.2/0.5/0.8`, each `[trial]`. The native loader maps these labels to `0/1` and `0/1/2`; export adapters must invert those mappings before submitting here. Trial IDs are unique across all three splits within a session. A unit cannot be reordered or silently omitted by one method. Unknown array fields (including reward, target aliases and arbitrary derived inputs) are rejected.

The canonical 70/10/20 source split and acquisition provenance must be frozen externally. This component consumes and checks explicitly frozen trial partitions; it does not redraw source splits or assume list indices prove original-trial identity. It does not resolve the source validity-mask bug, eligibility conflict or presplit scaling by reusing processed caches. Supply independently audited original-aligned arrays. No LFP, reward, contrast or alternative IBL derivative is silently added.

## Input masks and prediction panel

`input_packet(session, split, task)` deep-copies only permitted predictor inputs. The six tasks are:

| Task | Visible modalities | Predicted targets |
|---|---|---|
| `encode_all` | choice, block, wheel, whisker | all spike units |
| `encode_choice`, `encode_block`, `encode_wheel`, `encode_whisker` | only the named behavior | all spike units |
| `decode_all` | spike counts | all four behaviors |

No evaluation target, null rate, reward, alias or source provenance text is forwarded inside the packet. Native mask-token semantics are represented by omission, not by executing the transformer. Packet hashes bind the declared evaluation observation arrays. They do not prove that an arbitrary external program was sandboxed or that its training claims are true; protected execution remains a gate.

A prediction collection is one list entry per method/session. `make_receipt(session, method, predictions, budget_contract, pretrained_eids)` constructs the required receipt. `predictions` maps every task above to its exact target fields. Continuous/spike predictions match target shapes; class predictions use raw source labels. Receipts carry ordered test/unit identities, exact fit and validation trial IDs, pretraining EIDs, a nonempty budget contract, and one hash per input task packet. Missing, duplicated, reordered, unknown or mismatched pairs fail. Pretraining may name only pinned training EIDs, and both paired methods must declare identical pretraining exposure and budget for a session. Such declarations do not establish measured compute parity or full native training; they are preserved in the output.

All 84 session identities are required for a full panel. Training sessions report heldout trials from source training sessions; heldout sessions report within-session heldout trials after declared within-session fitting/finetuning. This does not make a zero-shot transfer claim. Performance is summarized separately for the 74 source training sessions and ten source heldout sessions.

## Metrics and reference

Neural encoding uses the pinned source definition: compute Poisson log-likelihood gain separately for each neuron against that neuron's mean **evaluated** counts; divide by that neuron's total spikes and `ln(2)`; then take an unweighted mean across defined neurons. Factorial terms cancel. Exactly zero predicted/null rates become `1e-9`; positive values below that are retained. Source-null rates stay scorer-only. Zero-spike neurons are listed explicitly with null scores. A separately named training-mean-null diagnostic uses only training counts and is not the historical source metric.

Continuous wheel/whisker R² flattens all evaluated trials and time bins, as the actual source call path does, without clipping negative scores. Constant-target behavior follows the finite sklearn convention (1 for exact prediction, otherwise 0) and is flagged. Choice/block ordinary accuracy is primary; balanced accuracy, class recalls and absent classes are retained as diagnostics. No score is an arbitrary average of neural and behavioral endpoints.

The prospective reference is runnable from the same arrays. For each task, it standardizes visible features from training only and fits ridge regressions. Encoding fits `log1p(count)` from behavior, then applies `expm1` with a disclosed numerical clip `[-20,20]` and nonnegative truncation. Continuous decoding fits behavior from binwise spikes; class decoding fits one-hot scores from per-trial mean spikes. Lambda is selected on validation among `0.1,1,10` using Poisson loss, MSE or misclassification as appropriate; ties choose the smaller lambda. Training remains the only coefficient/scaling fit set. The test set never fits coefficients, normalization or lambda. This is an engineering reference chosen here, **not** the paper's unresolved classical linear/RRR baseline or a NEDS multitask model.

Comparisons report each session and a session-macro mean for every endpoint. An undefined session blocks that aggregate rather than silently removing it. Paired differences are also summarized by equal-weight declared animals after averaging each animal's sessions. Percentile intervals resample these animal means and are explicitly conditional on the unverified identity join; they are not qualified scientific confidence claims. Fewer than two animals yields no interval. The Pareto relation keeps all nine endpoints separate; one mixed neural/behavior score is never manufactured. Comparisons sharing IBL cohorts are not independent datasets.

## Source departures and holds

The evaluator deliberately scores every input trial; the inspected native evaluation loop appears to invoke the model after its dataloader loop and can retain only the final batch. This component therefore does not claim byte parity for that execution bug. It also requires complete session support instead of applying a silent session-level `nanmean`.

The paper and pinned preprocessing code disagree on unit eligibility (paper excludes below 2 Hz; code's `fr_thresh=.2` yields `mean_fr>5 Hz`). The code also rescales dynamic behavior globally before splitting to `[0,1]`, whereas the paper describes `[-1,1]`, and combines list-valued validity masks using Python truthiness. Camera selection tries left whisker then right on a skip condition. These are recorded source discrepancies, not silently repaired historical facts. Resolving their scientific impact requires exact source/data provenance and native comparison outside this construction package.

Exact ONE object/revision/checksum selection, all animal/probe joins, source preprocessing/eligibility, native training recipes and environment, original split provenance, protected references/tolerances, authentic full-cohort execution, rights/exposure and measured resource parity remain held. Generated controls establish implementation behavior only. No empirical baseline performance, binary reward or scientific readiness promotion is produced.

`provenance.json` records primary source hashes, formulas, source discrepancies and prospective choices. The canonical task and its historical source records remain unchanged.
