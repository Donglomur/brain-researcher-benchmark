# Initial evaluator for PAPER-paper-method-018

This package evaluates complete ten-session prediction artifacts for a **prospective** history-versus-interaction comparison. It computes the pinned model's neural loss and variational-loss components, checks matched identities and construction metadata, and reports session-level predictive gains. It does not fit the GLM-Transformer, recreate the original figure, validate Allen recordings, or establish a qualified benchmark. All canonical task and historical records remain unchanged.

The implementation is independently written from mathematical definitions and source inspection. No author implementation is redistributed or imported. The author's code reuse license remains unresolved; an eventual native execution/package must resolve that separately from Allen data terms.

## Scientific boundary and source mapping

The canonical contract is `task.json`, SHA-256 `7032a947b6b9a0a860301d587d81e83ef5b44adc1764654e0074b4cd8e55718f` (38,573 bytes). The official source revision is `421b5eef321cac3d1c1279759e0f6b638068b021` in [Qi-Xin/GLM-Transformer](https://github.com/Qi-Xin/GLM-Transformer/tree/421b5eef321cac3d1c1279759e0f6b638068b021). Source URLs bind the inspected revision; this package does not claim locally recomputed upstream file digests.

| Requirement | Evidence | Implemented behavior |
| --- | --- | --- |
| Ten Allen sessions, history/interactions comparison | Canonical `/primary_outputs` and `/input_assets/lineage_and_loader_evidence` | Exact cohort required in both arms and reference; no subset mode |
| Neural Poisson and latent KL terms | [GLMTransformer.py, loss_function](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/GLMTransformer.py#L437-L445) | Independent float64 formula, separate components and full Poisson diagnostic |
| Posterior-mean inference | [model_trainer.py, predict](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/model_trainer.py#L297-L311) | Explicit target-conditioned reconstruction policy; no blind/causal forecasting label |
| Trial-weighted source reduction | [Fig5.ipynb, test loop](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/Reproduce_figures/Fig5.ipynb) | Trial-weighted variational diagnostic distinguished from prospective equal-session neural endpoint |
| Condition-specific source split sizes | [DataLoader.py](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/DataLoader.py) | Condition grouping and integer allocation checked; frozen trial identities required |
| No frozen numeric acceptance target | Canonical `/evaluation/observable_endpoints/missing_common_contract` | No pass threshold, reward, reproduction claim or readiness promotion |
| Native and scientific discrepancies | [Primary paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/ac643478c07baa8432690555e4702b65-Paper-Conference.pdf), source and canonical holds | All remain in every output report |

The exact cohort is 757216464, 798911424, 715093703, 719161530, 721123822, 737581020, 739448407, 742951821, 743475441 and 744228101. Provider object IDs in the canonical contract are preserved; their HTTP validators are not content checksums.

## Prospective ablation and estimand

Both fitted arms must declare identical preprocessing, model-capacity recipe, training hyperparameter recipe, stimulus treatment, individual-neuron self-history, latent dimension, beta, bin size and frozen trial splits. Cross-population coupling is disabled for `history_only` and enabled for `interaction_enabled`; within-population coupling is disabled in both. These are separately fitted ablations with matched construction recipes; actual fitting/capacity equality requires independent execution evidence. Digests bind declarations, not the truth of a training claim.

These two model ablations belong within one candidate attempt. They are distinct from the canonical paper-and-data versus official-code access conditions; matched budgets, source exposure and a causal code-benefit comparison remain unestablished.

This proposed comparison preserves individual-neuron history as the task requests. It differs from the visible Fig5 test call, which turns individual self-history off. The package never treats that change as reproduction of the published figure. No alternative arm may fit a constant baseline using evaluation counts.

For post-padding count tensor `y` and natural-log expected counts `eta`, both shaped `(time, neuron, trial)`, the neural term is

`L_neural = mean(exp(eta) - y * eta)`.

Predictions are expected **counts per bin**, not rates per second. The missing factorial constant does not affect a paired gain on identical counts, but the result alone is not a full Poisson negative log-likelihood. The diagnostic full value adds `mean(lgamma(y + 1))`.

For posterior arrays `mu, logvar` shaped `(trial, latent_dimension=D)`, the pinned source component is

`L_KL = mean(-0.5 * (1 + logvar - mu**2 - exp(logvar))) * D / (time * neuron)`.

In the pinned area-specific encoder, each area supplies a contiguous block of posterior columns and the blocks are concatenated to `(trial, D)`. Export `sti_mu` and `sti_logvar` directly in area-major column order and the same trial order as predictions. `D` is the total latent dimension, not its per-area share; the evaluator accepts no implicit reshape.

The diagnostic variational value is `L_neural + beta * L_KL`. It is not the pure neural likelihood. The native code may evaluate floating arithmetic in a different precision; this independent implementation uses float64 and rejects overflow without clipping.

The prospective primary value is the equally weighted mean across all ten sessions of `history_only L_neural - interaction_enabled L_neural`; positive values favor interactions. Per-neuron gains, full Poisson diagnostics, bits per spike, the pooled-observation neural mean, and the trial-weighted source-style variational mean remain separately named. Bits per spike is null for a session with zero spikes. Weighting a per-session loss by trial count reconstructs the notebook's reduction if batches remain within a session and all trials are covered; it does not reconstruct unavailable checkpoint outputs.

An exact two-sided sign-flip diagnostic enumerates all 1,024 session sign assignments. It assumes independent exchangeable session-level paired signs under its null. It is exploratory, has no acceptance threshold, and supplies no cross-session training-generalization or causal inference claim. Neurons and time bins are not treated as independent replicates.

## Artifact interface

Run with an existing Python runtime containing NumPy; no installation is performed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/paper/PAPER-paper-method-018/implementations/initial-evaluator-v1/evaluator.py \
  --reference /operator/reference/reference.json \
  --submission /candidate/predictions/submission.json \
  --output /output/new-report.json
```

The output path must not exist. The evaluator reads only JSON and numeric NPZ files with `allow_pickle=False`. File references must be relative to their manifest directory, resolve within that directory, and match a SHA-256 digest. It rejects object/complex/boolean arrays, nonfinite values, fractional/negative counts, duplicates, changed axes, missing sessions, unpaired trials and incorrect ablation declarations. It does not load author pickles, joblib files, checkpoints, or execute submitted code.

The operator reference must be frozen independently of the candidate. The CLI accepts a supplied reference path; it does not establish a secure sealed-grader boundary, authenticate the operator, or prove raw-data completeness. The candidate must not choose or rewrite that reference.

Reference JSON has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "task_id": "PAPER-paper-method-018",
  "contract_sha256": "7032a947b6b9a0a860301d587d81e83ef5b44adc1764654e0074b4cd8e55718f",
  "source_commit": "421b5eef321cac3d1c1279759e0f6b638068b021",
  "inventory_status": "operator_frozen_not_independently_native_validated",
  "recipe": {},
  "sessions": []
}
```

The empty objects above are placeholders for the following required records, not valid runnable input. A complete generated engineering fixture is in `implementations/initial-evaluator-v1/tests/test_evaluator.py::control_artifacts`; it contains no Allen data.

`recipe` must contain:

| Field | Meaning |
| --- | --- |
| `inference_policy` | Exactly `posterior_mean_target_conditioned_reconstruction` |
| `include_stimulus`, `include_self_history`, `use_self_coupling` | Exactly true, true, false |
| `beta`, `latent_dimension` | Nonnegative finite KL weight; positive integer latent dimension |
| `bin_width_seconds`, `history_padding_bins` | Positive duration and positive integer initial padding; actual native choice remains to be validated |
| `model_capacity_sha256` | Digest of the independently frozen common architecture/capacity recipe |
| `training_recipe_sha256` | Digest of the common optimizer, stopping, budget, seed and hyperparameter recipe; coupling flag is the sole ablation difference |
| `preprocessing_sha256` | Digest binding neuron/trial eligibility, invalid-time treatment, stimulus windows, binning and preprocessing |
| `split_policy` | Exactly `operator_frozen_condition_stratified_code_route` |
| `split_frozen_after_final_batch_size` | Exactly true; source batching changes can regenerate random splits |

Each reference session has exactly:

- `session_id`; ordered unique string `neuron_ids` and `eligible_trial_ids`.
- Ordered unique string `train_trial_ids`, `validation_trial_ids`, `test_trial_ids`; all three are nonempty across the session, mutually disjoint and exhaust eligible trials.
- `trial_conditions`: every eligible trial ID mapped to `{"stimulus_name": "...", "stimulus_condition_id": "..."}`. The condition ID may be null except for drifting gratings. Drifting gratings group by name plus condition ID; other stimuli group by name only. Within each group the source allocation is `floor(0.7*n)` training, `floor(0.1*n)` validation, remainder test, except `n=15` gives 9/2/4. Small groups can have no validation/training observations. Assignments themselves must be frozen, not inferred from counts by this evaluator.
- `test_batches`: ordered nonempty lists of ordered test-trial IDs; flattening must equal `test_trial_ids` exactly. Freeze native batch composition, not merely the union of trial IDs. The pinned encoder combines `batch_first=True` with an apparent time-first input, so native predictions may depend on which trials share a batch. This layout needs independent native reconciliation.
- `time_bin_indices`: every contiguous retained bin beginning at `history_padding_bins`; no internal masking or selective time-bin omission.
- `counts`: `{"path": "counts-session.npz", "sha256": "64 lowercase hex digits"}`, containing exactly numeric array `counts` with shape determined by time-bin, neuron and test-trial IDs.
- `eligibility_receipt_sha256`: digest of the operator's complete raw-data eligibility/exclusion receipt. The receipt and native eligibility are still independently unvalidated.

Source trial splits are within sessions. The paper's training/test/validation prose disagrees with the code's validation/test naming; using this code route does not resolve that scientific discrepancy.

Submission JSON contains exactly `schema_version: 1`, `task_id`, `reference_sha256` (hash of exact reference bytes), and `arms`, with exactly `history_only` and `interaction_enabled`. Each arm contains:

- An exact copy of reference `recipe`, the appropriate boolean `include_coupling`, and `checkpoint_sha256` for the fitted artifact. Checkpoint digests must differ across the separately fitted arms; masked predictions from one shared checkpoint represent a different ablation.
- `fit_training_partition_sha256`, computed by `evaluator.partition_digest(reference)`: SHA-256 of sorted-key, compact JSON containing session ID and ordered train/validation/test identities in the fixed ten-session order. This checks identity binding, not actual fitting.
- `sessions`: all ten records, each with exactly `session_id`, `neuron_ids`, `test_trial_ids`, `test_batches`, `time_bin_indices`, and `predictions`. Axes must exactly equal the reference, including order. `predictions` is a relative path/digest record for an NPZ with exactly `log_rate`, `posterior_mu`, `posterior_logvar` arrays. Posterior latent dimension must match the common recipe.

Unknown fields are rejected to prevent ambiguous policies. Canonical content, data rights and source-native evidence cannot be replaced by metadata declarations.

## Verification and retained holds

Run generated engineering controls:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-018/implementations/initial-evaluator-v1/tests -v
```

The tests use independently derived Poisson/factorial/KL values and exact sign-flip probabilities. They exercise matched-cohort rejection, condition split corner cases, axis order, leakage through trial overlap, count validity, tampering, overflow, file confinement, untrusted object arrays, unequal aggregation weights, zero-spike normalization and the CLI. They provide engineering evidence only.

The preserved scientific and native holds are material:

- No Allen recording was downloaded, hashed, schema-validated or analyzed. Full neuron/trial eligibility, invalid-time exclusions, preprocessing and cached-loader/checkpoint lineage require native validation.
- Source notebook calls include `fix_latents`, absent from the pinned model/trainer signatures. The notebook also estimates its displayed baseline from evaluation counts. The package does not silently repair or adopt those behaviors.
- Paper/code split naming, total NLL versus mean variational reduction, and stale loss storage in the supplementary ablation workflow need native-version and reference reconciliation. Stored notebook numbers are not protected answers or tolerances.
- Anatomy/condition pickle dependencies remain missing; their group-specific figure subpanels are not covered.
- The apparent source encoder sequence/batch-axis discrepancy can mix trials. Exact native inference batch membership must remain fixed; no batch-invariance claim is made.
- Target-conditioned latent inference is reconstruction on held-out trials, not blind forecasting or held-out-session prediction.
- Code rights, Allen terms, immutable data content identity, model exposure, protected final evaluation, independently executed reference, grouped improvement panel and empirical resource envelope remain open.

The executable always reports `scientifically_qualified: false` and `full_contract_complete: false`. No new scientific run, performance gain or historical reproduction is claimed.
