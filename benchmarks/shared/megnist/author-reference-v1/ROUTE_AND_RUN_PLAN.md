# MegNIST author route and private evaluator

This is an unregistered shared source package for the MegNIST candidate. It does not register a benchmark task, demonstrate authentic model execution, or establish runtime isolation. `SOURCE_AND_INPUTS.json` records operator-side source and exact external input identities; it must not be delivered wholesale to a candidate. No neural arrays, labels, private joins, checkpoints or cached test-reference scores are bundled.

The authenticated author trainer is reused unchanged from `author-source/run_hyperparameter_search.py` (SHA-256 `f377af312dd066691e5f046b5ead51c5f77745ffbd908850cc49a5d95061ab18`). Its MIT license is retained beside it. The already prepared dataset has separate CC BY-NC4.0 terms. The original MIT notice accompanies the unchanged author source. Inclusion of code does not grant additional rights to the separately licensed dataset.

## What the package preserves

The original reference task uses all 10,000 training, 1,000 validation and 1,000 test trials, with all 306×250 neural features. It concerns one participant across four sessions with held-out runs. It does not establish cross-person generalization.

The author baseline is a one-hidden-layer ReLU MLP with ten outputs. Its full reference grid is seven widths (32, 64, 128, 256, 512, 1024, 2048) crossed with ten seeds (42–51). Training uses the source cross-entropy loss, AdamW learning rate 0.001 and version-dependent remaining defaults, batch size 32, at most 200 epochs, and validation-accuracy early stopping with patience 20. Equal validation accuracy does not replace the best state. Source seed resets and DataLoader behavior are preserved; no new generator or stochastic convention is silently introduced.

Normalization uses the source's sequential, row-ordered Welford calculation on training data only. Accumulators are float64; variance divides by the sample count; exactly zero standard deviations become one. Each flattened row is standardized before its conversion to float32. Within-run normalization, vectorized accumulation and a different estimator are not substituted. A normalization cache must bind the actual training bytes, source method and numeric arrays; an unbound pre-existing NPZ is refused. No authentic normalization was computed during construction.

The exact source imports h5py, NumPy, PyTorch and huggingface_hub. It does not import PNPL or perform raw-FIF preprocessing. Hugging Face is imported by the author module, but its data-download fallback is not used by this route. Existing installed metadata is documented for generated tests; it is not a historical runtime lock or proof of original numerical parity.

## Why adapters are necessary

The original script requires labels in all three HDF5 files, prints test accuracy after every run and retains only aggregate accuracy. The prepared candidate test file intentionally contains only `data` and `case_ids`. The adapter therefore separates fitting from private evaluation without changing the scientific model or fitting method.

`author_route.py` verifies the author source before loading it. Its `fit_reference_run` primitive constructs the source train/validation loaders, calls the original model and training functions, and returns the validation-selected model, normalization identity and a model-state digest. This fitter receives no test path or labels. Its low-level functions also support the small generated fixtures used for engineering controls; calling them is not evidence that the full original input profile or reference grid has been completed.

The separate `run_reference_panel` function composes the complete reference route under operator control. It binds the accepted input manifest and private test-join identity, computes or verifies training normalization once, iterates the original 70 width/seed cells with fixed author settings, exports predictions and privately scores each frozen model before disposal, then writes the complete summary. Its outputs are evaluator-private. The optional representative checkpoint refit is explicitly not performed. Calling this function would perform authentic fitting and test evaluation and requires separate execution authorization; construction controls exercise only mocked routing, never the authentic function path.

`prediction_interface.py` consumes feature-only test batches and exports numeric per-case logits and argmax predictions. Its `predict_h5` helper uses the author normalization and Torch inference route; pass the exact normalization returned with the fitted reference model after its provenance check. It checks the expected frozen model-state identity before inference and checks that inference did not mutate that state. The operator must freeze the state before test access. A matching digest is an integrity check, not independent proof of when freezing occurred or an isolation boundary. It identifies numeric parameters and buffers, not arbitrary model code or Python attributes; the runner must bind model code/configuration and normalization separately.

`evaluate_private.py` joins those predictions to evaluator-private labels using exact opaque case IDs. The prepared IDs are arrays of shape `(N,16)` and dtype `uint8`; they are random raw bytes, not strings or source row numbers. Private joins contain `labels`, `case_ids` and `original_row`. Labels retain signed 32-bit source storage. Row provenance must not be used to infer targets. Missing, duplicate, extra, malformed or unsupported cases must be rejected before the original `100 × correct / total` score is produced. All 1,000 test cases are mandatory for the original profile.

Private per-case labels, joins, predictions, test scores and full reference test results remain outside candidate search and candidate-visible logs. The construction directory is an operator package, not a safe candidate sandbox. Local paths, absence of a label dataset, model fingerprints and preflight assertions do **not** establish actual process, filesystem, network, provider or conversation isolation. That remains unqualified until separately demonstrated.

## Reference summaries and improvement candidates

`summarize_reference.py` requires the complete seven-width/ten-seed baseline grid and uses mean validation accuracy to select the width, retaining source ordering and tie behavior. Its representative-seed metadata is kept separate: the author code chooses the seed nearest median validation accuracy and breaks ties using proximity to median **test** accuracy. This is a test-informed, post-hoc representative choice. It must not select an improvement candidate or replace the main ten-seed mean result.

The author's default script optionally performs a 71st fit to save that representative checkpoint. This is a separate checkpoint artifact and extra compute, not a new reference-grid cell or a substitute for the 70 runs. A checkpoint also omits normalization parameters, so its separate normalization identity must be retained.

The trainer computes no SD. Recovered author values numerically explain the notebook's rounded population SD and paper's rounded sample SD, but the paper's intended convention remains unconfirmed. Cached scores are reference evidence, not a reproduction threshold, a meaningful-effect rule, or an uncertainty estimate for a new candidate. Ten seeds are not ten independent participants.

An improvement candidate may change architecture or method within the same original task. It is **not** forced to use the seven-width author grid or the author's normalization helper. The numeric `write_predictions`/`read_predictions` transport and private scorer also accept independently produced candidate logits with the same ten-class, complete-case support. Its observed cases, available neural information, label access, validation-only choices and prospective comparison must remain explicit. Paper+data and paper+data+author-code conditions need the same predeclared search/compute budget; only authorized source-code exposure differs. No checkpoint or pretrained weights are added implicitly. No candidate budget, superiority margin or significance rule is invented here.

## File scope and controls

The eight scoped files are `SOURCE_AND_INPUTS.json`, `author_route.py`, `prediction_interface.py`, `evaluate_private.py`, `summarize_reference.py`, `preflight.py`, `tests/test_generated_route.py`, and this plan. The untouched author trainer and MIT license are bundled under `author-source/`; `requirements-controls.txt` declares direct control dependencies. Review receipts remain external. Tiny generated fixtures and their accounting receipts are retained in a fresh temporary directory outside this package.

`preflight.py` defaults to metadata inspection. Full reference validation binds the exact accepted candidate manifest and original counts; the generated profile is explicit. Optional file hashing and HDF5 header checks are operations for a separately authorized context, never a reason to reread authentic payloads during these controls. Header checks do not establish case-ID uniqueness or the correctness of a private join; the complete-case evaluator and accepted input-preparation proofs have their own roles.

Generated controls exercise selected author functions only on small synthetic arrays and small models in a compatible environment. Run them in a fresh process with one thread, no more than 1GiB declared working RAM and a 180-second deadline. The existing `torch-cpu` CI group is the intended enrollment target; it needs the reviewed Hugging Face Hub dependency closure in addition to its existing PyTorch/NumPy/h5py packages. Dependency versions used for engineering controls are not a paper-producing historical lock. They cover normalization/cast parity, cache provenance, source-versus-adapter fitting and seed behavior, baseline selection, private scoring and refusal cases. They do not instantiate a full 76,500-input model or open authentic recordings, labels, reference pickles or model states. They cannot earn scientific success.

## Later execution boundary

Independent method/delta review and passing generated controls finish this construction phase. They leave all four scientific outcomes unknown. Actual runtime isolation, an exact execution environment, measured resources and a justified comparison remain separate requirements before any authentic baseline or candidate run.

A full baseline is computationally substantial. At width 2048, parameters alone number 156,694,538 and occupy about 626,778,152 bytes at float32; gradients, Adam states, the best-state copy, batches and libraries require more. The generated-control resource allowance is not permission to launch that workload. No training time, full-run memory claim or package installation is inferred from the small controls.

Any later authorized run must preserve the full original reference family and its observation-level derivation, freeze allowed information and selection before test evaluation, enforce actual evaluator isolation, and record failures rather than substitute an easier panel. Original source history, prepared inputs and the first recovered reference packet remain immutable.

## Portable use

From the repository root, the generated-only check is:

```sh
python -I -B benchmarks/shared/megnist/author-reference-v1/tests/test_generated_route.py
```

It runs the existing 18 controls with tiny generated fixtures and mocked full-panel routing. It does not need the authentic prepared inputs. Retain its printed temporary fixture path and accounting receipt when investigating failures. A missing dependency is an environment error, not a reason to skip controls or fabricate parity.

For later separately authorized reference execution, put this directory on the module search path and call `author_route.run_reference_panel` with explicit `input_manifest_path`, `candidate_root`, `private_join_path`, `expected_private_join_sha256` and a fresh evaluator-private `output_root`. Use the exact prepared content identities in `SOURCE_AND_INPUTS.json`; relocation of files does not authorize regenerated or different inputs. A later execution plan must supply an actually enforced candidate/evaluator boundary and measured resources first. This package has no automatic execution entry point.

Do not use the bundled upstream command-line entry point as an offline or isolated runner: it retains its original data-download fallback, label-bearing test expectations and test-score output behavior. It is bundled unchanged for provenance and use by the reviewed adapter.
