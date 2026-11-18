# Full-grid candidate submission and evaluator bridge

This component collects candidate operands for the existing rat population-geometry
task and derives their scores in the operator evaluator. It requires the complete
**13,824 GLM coordinates and 64,000 geometry coordinates**, preserving eight rats,
eight sessions and two regions. Coordinates are outputs within one registered
task, not additional benchmarks or independent animals.

The original primary geometry findings remain separate from supporting GLM D²
and readout errors. There is **no overall improvement predicate** here. A larger
geometric quantity, smaller p-value, or better supporting classifier alone does
not establish that the paper's findings have been surpassed.

The existing authentic-input join has already validated all 128 regional packets
and 64 paired sessions. This addition performs no new authentic-data run, fit,
AI trial or reference qualification. It adds executable submission, numerical
evaluation and reduction interfaces. The parent task's current outcome contracts
remain authoritative and unchanged.

## Candidate operands

`glm_bridge.evaluate_glm(reference, candidate)` accepts one exact original grid
coordinate. Candidate inputs contain the submitted method SHA256, native row,
unit and contiguous-fold identities, all ten alpha slots of held predictions,
selected full-row expected counts and declared selected alpha indices. The
operator supplies the counts and original coordinate. The evaluator derives
all per-unit/alpha/fold deviances, source nanmean/ordinary-argmax selection,
undefined fold statuses and the original session summary. It rejects submitted
targets, scores, missing units, changed folds and extra summary fields.

The all-alpha tensor is **a newly required raw artifact**. The existing producer
saves per-alpha CV scores but does not retain these raw predictions. The selected
OOF column reconstructed from that tensor is not represented as a replay of the
producer's ten additional selected-alpha refits. Correct raw outputs cannot by
themselves attest out-of-fold training or execution of the declared method. The
deviance calculation uses the retained numerically stable mathematical replay;
bitwise agreement with an original native runtime has not been established.

`geometry_bridge.make_reference` joins the exact 500-row, 19-neuron source draw,
500 Gaussian teacher tasks and 300/200 training/test partition. It reconstructs
the draws from the saved RNG state without fitting a classifier. Its required
`ReferenceChain` checks both region seeds and every continuing draw in the original
global 64,000-coordinate order; `finish()` refuses a partial chain. Native row,
unit, teacher, training and test identities remain explicit. The current serial
seed recipe is not an authenticated historical parallel realization.

The operator must also supply raw source SVC test predictions, authenticated by
its own source/artifact loader. These are **not present in old checkpoints merely
because those checkpoints contain error summaries**. Source SVC predictions and
their content pin are newly required reference operands. `make_reference` checks
logical joins; it does not independently attest the caller's file custody or
execution history.

`geometry_bridge.evaluate_geometry` requires the candidate's complete 23×23
joint covariance estimate and signed predictions for every retained teacher and
test row. The evaluator:

- Recomputes the source covariance from the fixed observations and compares all
  529 submitted covariance coordinates.
- Requires a finite, exactly symmetric full matrix before splitting its blocks;
  it never silently discards or repairs a changed lower-left block.
- Reuses the retained source covariance kernels to derive all eight geometry
  quantities and theoretical error, retaining their existing numerical
  admissibility rules. Those rules are not scientific agreement tolerances.
- Reports finite discrepancies and explicit positive-infinity agreement or
  disagreement. It does not replace undefined/infinite quantities with a win.
- Derives source Hebbian error and source SVC error from their respective raw
  operands. Arbitrary candidate error is separately labelled and uses ordinary
  signed-label inequality. Zero predictions cannot exploit the original
  Hebbian-specific zero-margin convention.

`reduce_geometry_case` calls the existing `session_result` on all 500 draws. It
requires **separate operator source-GLM and evaluator-derived candidate-GLM PR
results**: candidate PR/D² never overwrites the author reference. `reduce_panel`
joins all 128 ordered cases through the existing `panel_result`, preserving eight
independent animals and repeated sessions. The ordinary complete-grid GLM
finalizer remains `producer.validate_complete_grid`; evaluator-derived GLM
results have its required raw fields and can be stored through `producer.save_result`
in an operator-owned tree under an explicit evaluator binding. No original
producer, finalizer or stochastic policy is replaced.

## Freeze and collect the complete submission

`collection.full_plan()` enumerates the unchanged two original plans.
`make_binding` binds the method identity, operator input identity, information
condition and full plan fingerprint. `freeze_submission` consumes that exact
ordered stream and creates exclusive numeric artifacts, a JSONL manifest and a
final `COMPLETE.json`. It rejects missing, duplicate, reordered or extra
coordinates and preserves failed/partial output. Byte ceilings count cumulative
writes, including a failed completion write; a failure does not refund costs.

The caller must retain the returned COMPLETE SHA256 outside the candidate tree.
`verify_submission` requires that pin and verifies every numeric artifact before
any target callback. `evaluate_submission` performs that complete verification
and then yields records through the explicit GLM/geometry evaluators and trusted
operator reference loader. It does not label a partially consumed iterator as a
completed evaluation. Callers must finish the iterator and the global reference
chain, retain failures and separately save the evaluator's outputs.

The API is an operator library, not a sandbox. It does not execute participant
code, authenticate the execution of a submitted method digest, provide atomic
whole-directory snapshots, or prevent a concurrent trusted caller from mutating
inputs. Source and target custody, immutable private evaluation storage and
runtime isolation remain separate obligations.

## Information conditions and remaining work

Paper+data and paper+data+author-code remain distinct declared conditions.
Candidate covariance reconstruction requires latent targets, while readout
prediction must not receive its test labels. **All readout predictions must be
frozen before full latent targets are released for covariance analysis.** The
current final artifact contains both outputs. Its final freeze does not implement
or attest that earlier two-phase delivery. It is therefore not evidence of a
protected or pristine held-out readout evaluation. A subsequent runner must
implement that information boundary; the declared condition alone is insufficient.

Other preserved limits include source full-session preprocessing and alpha
selection exposure, paper CA1=24 versus active code=19 neurons, unresolved
historical file/RNG/runtime identity, source null-unit regional aggregation,
original NWB table-reference/anatomical qualification, public-source exposure,
rights and authentic comparator execution. No source scalar, complete file
census or generated test resolves these scientific questions.

The complete source-shaped artifact size and authentic runtime remain unmeasured.
All-alpha held predictions can be large. An admitted full preparation must budget
that actual representation rather than substitute a smaller grid or another
score. No downloads, installs, authentic preparation or model runs are part of
this component's construction.

## Generated validation and runtime

The component reuses exact pinned sibling algorithms recorded in `SOURCE.json`.
The original numerical producer requires NumPy 2.2.6, SciPy 1.15.3 and
scikit-learn 1.6.1; its current trend backend has separate requirements. In
particular the inherited numeric loader uses a NumPy 2.2.6 interface absent in
NumPy 2.4.6. Storage controls must run in the existing compatible environment.
The GLM/covariance arithmetic controls can also exercise their mathematical seams
under another explicitly recorded NumPy version; that does not qualify the
production runtime.

Generated controls cover independent deviance/covariance oracles, zero-null and
infinite cases, all native identities, all 529 covariance coordinates, source
RNG continuation, separate source/candidate labels, complete-case reduction,
the actual full metadata census, and small explicitly mocked-plan filesystem
round trips and failures. A metadata census plus tiny storage fixtures is not a
full 77,824-artifact or authentic scientific run. The construction receipt records
initial failures, focused reruns and final independent reviews without merging
them into an invented successful campaign.

Run the generated tests in the compatible existing environment from this
directory with `python -B -m unittest discover -s tests -v`. No test opens
authentic neural inputs or fits a model.
