# Original Allen likelihood components

`components.py` independently recomputes the Poisson likelihood terms on each declared native test batch for all ten Allen sessions and all five Table S1 variants. It fills a missing computation on the original empirical panel; the existing two-arm interaction-gain evaluator remains a separate prospective endpoint.

The [paper, Table S1 and Appendix G](https://proceedings.neurips.cc/paper_files/paper/2025/file/ac643478c07baa8432690555e4702b65-Paper-Conference.pdf) specifies the five variants, posterior-mean inference and ten-session cohort. Its observation model uses Poisson expected counts in 2-ms bins. The [pinned model loss](https://github.com/Qi-Xin/GLM-Transformer/blob/421b5eef321cac3d1c1279759e0f6b638068b021/GLMTransformer.py#L438) averages `exp(eta) - y * eta` and adds scaled KL. This does not identify the historical total-NLL calculation. The [source recovery](../../docs/ablation-source-recovery-v1.md) describes the unresolved split, stage, cache and loss lineage.

For counts `y` and log expected counts per bin `eta`, this collector reports three separate **sums**: `exp(eta) - y*eta`, `log(y!)`, and their sum. Unequal native batch sizes retain their observation weight. No mean of batch means, session mean, run mean, standard error, KL term or training penalty is substituted for the paper score. All arrays use `(time, neuron, trial)` order after the declared history padding. Counts must be nonnegative exact integers; arithmetic overflow is rejected without clipping.

Run with an existing Python 3.10+ and NumPy environment:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 components.py --manifest /operator/native-run.json --output /output/new-components.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The output path must be new. One manifest describes one run. Its exact keys are:

```json
{
  "schema_version": 1,
  "task_id": "PAPER-paper-method-018",
  "source_commit": "421b5eef321cac3d1c1279759e0f6b638068b021",
  "run_id": "operator-assigned-run-id",
  "inference_policy": "posterior_mean_where_present_target_conditioned_reconstruction",
  "bin_width_seconds": 0.002,
  "sessions": []
}
```

Populate `sessions` with exactly one record for each registered session. Each record has `session_id`, ordered unique `neuron_ids`, contiguous integer `time_bin_indices`, disjoint ordered `train_trial_ids`, `validation_trial_ids`, `test_trial_ids`, `model_runs`, and `batches`. No split fraction or trial membership is inferred; the supplied partitions still require independent source reconciliation.

`model_runs` has exactly these five keys: `full_model`, `bidirectional_rnn_encoder`, `no_trial_wise_latent`, `no_coupling`, `no_post_spike_history`. Each value has `checkpoint_sha256`, `recipe_sha256` and a nonempty `model_stage`. These are declarations bound by the manifest, not verified fitting provenance or a mapping from the incompatible notebook stages. In particular, `no_trial_wise_latent` is the paper variant name and does not silently map to the notebook's `without_encoder` label.

Each ordered batch has `trial_ids`, `counts`, and `predictions`. Concatenating batch trial IDs must exactly equal the declared test list. `counts` is an artifact record `{"path": "batch-counts.npz", "sha256": "<lowercase SHA-256>"}` for an NPZ containing only `counts`. `predictions` has the same five variant keys; each value is an artifact record for an NPZ containing only `log_rate`. Each array must have the shared batch shape. Paths must remain within the manifest directory, including after symlink resolution. Artifacts and manifests are hashed and decoded from the same captured bytes. The collector processes one batch at a time; it does not rerun inference or change batch composition.

The report retains ordered neuron/bin/batch identities, per-batch artifact commitments, separate likelihood sums and per-session diagnostic totals. It deliberately emits `paper_score: null`, `paper_standard_error: null`, `scientifically_qualified: false` and `full_contract_complete: false`. The historical constant/KL/penalty/total convention and independent repetition units remain unresolved. Supplied array labels cannot establish authentic completeness, correct model execution, protected test use or original neuron eligibility. Native coupling/dynamics outputs are not checked. These components cannot establish full-family reproduction, improvement or causal connectivity.

The controls use small generated arrays only. No author module is imported, no checkpoint or recording is loaded, and no scientific result is claimed.
