# Raw source recording and staged delivery

This component supplies two missing pieces of `PAPER-paper-method-add-006`: original-grid raw predictions that earlier source checkpoints did not retain, and an operator interface that seals geometry readout predictions before releasing behavioral latents or GLM inputs. It reuses the original numerical methods and phase15 evaluators. It is source construction, not an authentic baseline run, a validated participant isolation system, or evidence of paper improvement.

## Original support and source recording

The full plan remains **13,824 GLM coordinates and 64,000 geometry coordinates**: 108 GLM configurations over 128 regional session packets, and 500 geometry draws per packet. There are eight independent animals and 64 paired sessions. Coordinates, teachers and repetitions are outputs within this paper task, not separate benchmarks.

`recorded_glm.py` derives its two fitting functions from the pinned `glm_search.py`. It preserves the actual `GridSearchCV`, ten alphas, ten unshuffled folds, source scoring, callable NaN-aware refit, full-row refit and ten additional selected-alpha fits. Integer source-row identities survive sklearn indexing; repeated feature rows never serve as identities. The additional tensor records every held prediction as `[source row, source unit, original alpha]`. Capturing it requires an additional prediction call for each alpha/fold/unit, but no additional model fitting. The original Poisson route produces float64 predictions; the recorder refuses unsupported prediction dtypes instead of silently converting them. Capture-only warnings remain separate from the original warning census. Original selection already sees all folds, and original preprocessing sees the whole session. These remain inherited exposures, not a protected or nested estimate.

`recorded_geometry.py` derives its readout and geometry-repetition functions from the pinned `geometry_results.py`. It retains the raw SVC predictions already computed in the original classifier loop. Columns follow the existing valid-teacher identities, and rows follow the existing 200 held-out row identities. It adds no classifier fitting, prediction or random draws. It requires the original classifier's float64 prediction dtype, preserving finite fractional values rather than coercing or rounding a different dtype. Capturing raw numeric values does not make them automatically admissible to a downstream evaluator: the unchanged phase15 reference bridge explicitly requires source-encoded binary predictions.

The geometry recorder's `max_prediction_bytes` ceiling covers the retained float64 matrix only: `200 × valid teachers × 8` bytes, at most 800,000 bytes. Positive but insufficient limits are rejected after source teacher selection, before the training split and classifier dispatch. That failed call has consumed teacher-generation randomness: discard or restore its RNG before retrying. The resumable producer reconstructs the stream from its persisted prefix on a fresh invocation.

`raw_producer.py` supplies explicit `run_glm` and `run_geometry` entrypoints. Importing it starts no work. Their bindings include the original source/runtime/input identity and the new recorder source hashes, so old summary-only checkpoints cannot silently resume this route. Geometry resumes by verifying every prior original coordinate and restoring its recorded RNG continuation; a prefix is not a smaller completed benchmark. The wrapper also projects recorded source operands into the existing GLM candidate and geometry reference schemas. Those projections are author-reference operands, not an improved participant model.

The GLM capture allowance bounds explicitly recorded and source-owned numeric arrays. It is not a total working-memory guarantee: original preprocessing, caller-owned input storage, sklearn train/test copies, Python objects and estimator work require separate admission.

Byte ceilings are explicit. A complete per-result allowance is reserved before each new producer dispatch. The returned `charged_successful_output_bytes` records successful writes in that invocation only. An external execution controller must charge failed saves by the reserved allowance and maintain accounting across prior invocations. These source functions do not enforce a machine-wide storage quota.

## What a participant may see

For **each geometry coordinate**, Stage A retains the original supervised readout problem:

- All 500 selected neural feature rows, their native row identities and the 19 selected unit identities.
- The exact 300 original training row identities and signed labels for every retained teacher, in original order. These are legitimate training labels; the candidate can fit or otherwise construct a readout from them.
- The exact 200 complementary test row identities and features. Their labels remain operator-only.
- The original balanced-teacher identities. The source selected balanced teachers using all 500 labels before the train/test split. This inherited selection exposure is preserved and disclosed.

Stage A excludes full behavioral latent vectors, teacher weight vectors, test labels, source SVC predictions, evaluator scores and real GLM inputs or outputs. GLM covariates derive from the same behavioral latents; releasing them early would defeat the readout boundary.

Stage A seals all **64,000 readout outputs** before Stage B releases the declared GLM inputs and full latents needed for covariance reconstruction. Stage A includes operator-generated, data-free placeholders at GLM roster positions only to reuse the unchanged full-grid collector. A placeholder is explicitly not a GLM prediction or a completed scientific result.

Stage B receives the real 13,824 GLM predictions and 64,000 geometry covariance reconstructions. Final joining takes readout values exclusively from the externally pinned Stage A artifact. A Stage B payload cannot replace earlier predictions.

This is a prospective participant-delivery protocol preserving the original readout model's fitting information, not a claim that the authors used staged access. Giving an agent all original behavioral data at once is a distinct information condition; it cannot be scored as a protected readout trial under this interface.

## Independent coordinate execution is required

A training label in one draw can disclose another draw's held-out target. Therefore all Stage A inputs cannot be delivered into one persistent participant conversation, process, workspace or cache. Distinct context identifiers alone do not solve this.

The runtime seam requires a separately qualified adapter that provisions an independent context or a fixed-program invocation for each coordinate. Such an adapter must actually enforce the declared data view, frozen method identity, lack of cross-coordinate state and target isolation, and must return that coordinate's predictions without exposing further targets. The operator copies those predictions before context teardown; durable collector storage follows teardown. The global Stage A artifact must be durably sealed before any Stage B release. A fixed program needs appropriately isolated invocations and storage; simply naming a program or starting a process is not proof. A model provider needs an actual fresh-context and resource-isolation policy, not a different metadata string.

The source interface can validate artifact bindings and protocol order. It **cannot establish OS, container, provider, filesystem, network or memory isolation**. Engineering controls do not qualify a real execution. No supplied boolean, unique context ID or self-asserted receipt can turn this construction into a scientifically qualified run. Public source-data availability and contamination also require a separate evaluation policy.

## Evaluation and remaining scientific limits

The final operands enter the unchanged phase15 GLM/geometry bridges and existing session/panel finalizers. Evaluator-owned targets determine the scores. Native row, unit, session and teacher identities remain exact. Geometry reconstruction remains the primary endpoint; supporting GLM D² or classifier error differences do not substitute for it or define an overall paper improvement.

The active author code uses 19 neurons in both regions, while the paper's CA1 count of 24 remains unresolved. Historical runtime, RNG realization and source ordering are not recovered by this component. A complete authentic comparator, real-library numerical parity, independently qualified delivery runtime, reproduction criteria and a defensible improvement predicate remain outstanding.

Construction controls use generated numeric inputs and non-learning estimator doubles. Real frozen GridSearchCV/KFold indexing is exercised without estimating any model parameters. They can establish recording alignment, source control-flow equivalence and refusal boundaries; they cannot establish genuine Poisson/SVC numerical parity or authenticate scientific results. `CONSTRUCTION_EVIDENCE.json` records exact tested scope and limitations.
