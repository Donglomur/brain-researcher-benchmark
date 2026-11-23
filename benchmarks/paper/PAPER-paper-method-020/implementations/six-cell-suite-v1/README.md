# Six-cell NEURONA trace diagnostics

This operator component joins the existing [source scorer](../source-scoring-v2/README.md) across the six declared conditions: `paper_data` and `paper_data_author_code`, each with `neural`, `no_neural`, and `shuffled_neural` inputs. It closes the missing suite-aggregation step identified in that scorer's README. It recomputes every score from complete declared traces and keeps every source exclusion and failure ledger. It does not execute a participant, load neural data, authenticate a checkpoint or establish benchmark completion.

The original CSI1 semantic-QA task and source scoring paths are unchanged. The source training monitor and final posthoc calculation have different eligibility and failure semantics; both remain visible. No six-cell average or replacement task score is defined.

## Inputs and execution

Python3.10+ standard library only. From this directory:

```sh
python3 -B suite.py manifest.json suite.json vocabulary.json > operator-report.json
python3 -B suite.py manifest.json candidate-suite.json vocabulary.json \
  --reference-suite reference-suite.json > operator-comparison.json
```

The source manifest, ordered vocabulary and individual run traces use the unchanged [v2 interface](../source-scoring-v2/README.md). Both source modules are checked against fixed raw SHA256 identities before import, including the source scorer with empty-branch aggregate handling. This is a dependency identity check, not runtime isolation. All inputs and reports are operator-only: manifests contain answers, and reports contain identifying per-query ledgers. Keep them outside participant environments and Git. The CLI inherits duplicate-key and nonfinite-JSON rejection from the source scorer.

`suite.json` has exactly four fields:

- `schema`: `neurona-six-cell-trace-suite/v1`.
- `comparison_plan_sha256`: an operator-supplied binding to the intended comparison plan. This component checks identity only; it does not validate the plan's scientific content or freeze time.
- `control_design`: `same_frozen_model_inference_ablations`.
- `cells`: exactly six objects, each containing `run` and `declarations`. The run's `access_condition` and `neural_condition` identify its cell; duplicate, missing or unknown cells fail.

Each `declarations` object has exactly these five fields:

| Field | Consistency requirement |
| --- | --- |
| `common_inputs_sha256` | The declared common paper/data and permitted non-neural input bundle must be identical in all six cells. Author code is represented separately. |
| `resource_budget_sha256` | The declared cumulative resource/access-budget document must be identical in all six cells. This does not measure actual consumption. |
| `author_code_sha256` | Null for `paper_data`; a SHA256 for `paper_data_author_code`, identical within its three input conditions. |
| `candidate_code_sha256` | The same submitted method within each access arm's three inference conditions. It may differ between access arms or candidate and reference methods. |
| `training_run_sha256` | The same declared frozen training run within each access arm's three inference conditions. It may differ between access arms or candidate and reference methods. |

The run's checkpoint, selection-policy declaration and all-hop setting must also match within each access arm. Thus zero-input or shuffled inference cannot silently become retraining. An all-zero inference ablation is explicitly **not** a separately trained text-only baseline. Tensor/control construction and these declarations' authenticity require independent operator verification.

The wrapper requires a common source manifest and ordered answer vocabulary for all cells. The source scorer still checks the original84-path roster for non-fixture manifests. Neither the roster, a hash, nor a question count authenticates original native query contents, source-parser outputs, stimulus aliases or Table1 parity.

## Report interpretation

`cells` contains all six complete source reports, including training-monitor completion, posthoc category numerators/denominators and complete declared-query ledgers. `within_access_contrasts` reports neural minus each inference control separately within each access arm. `author_code_arm_minus_paper_data_arm` reports the corresponding arm difference for each neural condition. These are arithmetic diagnostics, not causal or statistical decisions.

Every difference requires identical, nonempty included query IDs. A caught exception that removes an erroneous answer can raise a cell's source accuracy; the wrapper retains that score and the omission ledger but withholds its paired difference. It does not score the common intersection or treat missing executions as evidence of a gain. An aborted source training monitor never becomes a completed comparison; posthoc diagnostics remain separately available. Overall comparisons also require both source branch metrics to exist: if all T/F or all vocabulary calls are excluded or fail, the scorer retains surviving-query arithmetic as a diagnostic and withholds its source Overall accuracy. `both_scores_available` reports this separately from query identity and training-monitor completion.

`--reference-suite` compares candidate and reference in the same six cells. The comparison plan, common input bundle, budget declaration and supplied author-code bundle must match. Candidate models/checkpoints may differ from the reference, while each method retains its own same-model inference controls. The output includes both full reports and each candidate-minus-reference diagnostic. It does not compare one access arm against the other as a paper-improvement result.

No report establishes source-paper reproduction, improvement or current SOTA. `execution_verified`, `resource_equality_verified`, `information_boundary_verified`, `native_query_population_authenticated`, `separately_trained_text_only_present` and `full_benchmark_panel_complete` remain false. Required original Linear/UMBRAE/SDRecon/BrainCap pipelines, a separately trained text-only companion, authenticated original query/checkpoint/selection evidence, paired biological uncertainty and a justified decision rule remain unresolved. This is a six-cell declared-trace join, not the complete original paper panel or an executed control suite.

## Construction verification

Fourteen generated controls exercise six-cell completeness, access/resource mismatch, hidden retraining, dropped-error denominator inflation, direction of paired differences, source aborts, every-cell bindings, candidate/reference alignment and refusal of caller-supplied qualification claims. They use five invented questions solely as software counterexamples; no authentic neural data, model fit or scientific score was run.

The public test command is:

```sh
python3 -I -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-020/implementations/six-cell-suite-v1/tests -v
```

The existing `stdlib-b` commands now discover 14 suite methods and 12 source-scorer methods.
