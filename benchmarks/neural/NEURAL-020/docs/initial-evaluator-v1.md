# NEURAL-020 initial evaluator v1

This construction component prepares an identity-bound public query, training packet and private scorer packet from complete, already binned Area2 training-asset tensors. It evaluates held-out-unit expected spike counts separately for active and perturbed trials and provides executable training-mean and NLB smoothing/Poisson controls. It does not parse NWB, acquire data, execute candidate code or establish scientific qualification. Canonical `task.json` is unchanged.

The implementation is in `../implementations/initial-evaluator-v1/evaluator.py`; its provenance file maps each behavior to the frozen contract or exact primary source. Every result retains `research_qualified: false`, `submission_ready: false` and explicit qualification gates. Generated control outcomes are engineering evidence only.

## Scientific meaning and frozen prospective policies

The source is DANDI 000127 version 0.220113.0359: one Han session on 2017-12-07. This component's preparation boundary covers all 826 trial rows and all 65 units in the named training NWB, including explicitly excluded rows. It does not claim to ingest the separate test NWB or combine files into a newly verified population. Source identifiers, timestamps, held-out flags and conversion facts supplied in metadata are **operator attestations**, not verified NWB reads. In particular, the actual official unit-mask values and acquisition time/rate conversion remain unqualified.

Pinned `nlb_tools` commit `42f8410b88e12db136910fa2f888b025ea0aa2ae` aligns Area2 trials to `move_onset_time` over [-100, 500) ms. Supported bins are 5 or 20 ms. Counts and predictions are **expected spikes per bin**, never Hz. Source unit ordering and the `NWB units.heldout` mask must be carried through unchanged. The private `ctr_hold_bump` field maps exact integer 0 to active and 1 to perturbed.

The canonical wording “active/passive conditions held out as specified” does not freeze a concrete leave-condition-out assignment. This version therefore requires an explicit native-split-to-role map, keeps the full source roster, rejects train/evaluation blocks or continuous-time windows that overlap, and reports both conditions. It does **not** establish leave-condition-out generalization. A later qualified protocol must resolve that scope before outcomes, including exclusions, reference access, fitting and compute. Native reference examples use train→val for validation and train+val→test for test; those are source facts, not an automatically accepted split for this contract. The implementation's stricter continuous-time separation may reject a native prepared split; it never repairs one by silently dropping trials.

For each condition, the scorer computes the official Poisson likelihood improvement over that condition's **evaluation-target per-unit mean**, divided by the observed spike total and ln(2). It recomputes the null within each subgroup. Official NLB `evaluate()` itself reports pooled co-bps; subgroup application is an explicit prospective policy required for this task's condition reports. The pooled official-equation result is a separate diagnostic and is not an average of subgroup scores. The training-mean reference is a candidate control, distinct from the evaluation-derived scoring null.

Exact-zero predictions and exact-zero null means become 1e-9, matching the pinned scorer; positive rates below 1e-9 remain untouched. Fixed target NaNs define ignored cells. This interface additionally requires finite, nonnegative predictions even at ignored cells, integer nonnegative observed counts, and observed coverage for every fixed held-out unit in each condition. These stricter submission and coverage policies are prospective fail-closed choices. All-zero spike totals yield an explicit undefined score, never zero performance. Constant predictions remain legal because a mean-rate baseline is meaningful; they are flagged diagnostically. Counts larger than 2^53, object arrays, unsafe archive allocations, duplicate IDs, mismatched ID order, wrong bin units and extra private fields are rejected.

No trial/block bootstrap is interpreted as biological replication. Reports are descriptive for one session; observed-spike predictive performance does not reveal true latent rates or causal circuit dynamics. Both files and former test targets are public development material, so this package cannot provide a contamination-resistant final leaderboard.

## Operator input and privacy boundary

`prepare` accepts an NPZ with only `full_counts`, a real numeric array of shape `(826, 600/bin_width_ms, 65)`, and JSON metadata. Counts are converted to contiguous float64 before hashing. NaNs encode fixed source missingness; infinities, negative and fractional observed counts are invalid. All metadata keys are required; unexpected keys reject.

| Metadata field | Required meaning |
| --- | --- |
| `schema_version`, `task_id`, `contract_sha256` | `1`, `NEURAL-020`, exact SHA256 in `provenance.json` |
| `source` | Exact `dandiset`, `version`, `subject`, `session_start_time`, `asset_id`, `asset_sha256` constants enforced in `_metadata` |
| `bin_width_ms` | Integer 5 or 20 |
| `unit_ids`, `heldout_mask` | 65 unique bounded text IDs and 65 Boolean flags, with both held-in and held-out units |
| `trial_roster` | All 826 rows in tensor order; each contains unique `trial_id`, `block_id`, `native_split`, `role`, `ctr_hold_bump`, absolute aligned `window_start_seconds`, `window_stop_seconds`, and `exclusion_reason` |
| `protocol` | Nonempty `protocol_id`, `selection_rationale`, `access_policy`, `resource_budget`; `native_split_roles` mapping source split names to `train`, `eval` or `excluded`; exact `condition_policy: report_active_and_perturbed_within_condition_null` |
| `conversion_receipt` | Exact `nlb_commit`, `alignment_event: move_onset_time`, `window_ms: [-100,500]`, `rate_units: spikes_per_bin`, `mask_source: NWB units.heldout`, SHA256 of contiguous float64 `full_counts` bytes in `counts_sha256`, and nonempty `operator_evidence` reference |

Included rows have `exclusion_reason: null`; every excluded row retains its explicit reason. Windows must last exactly 600 ms within floating-point tolerance. Every trial in a continuous block has one role; train/evaluation windows cannot overlap even across different block names. Both active and perturbed evaluation rows and a nonempty training population are mandatory. The fixture constructor in `tests/test_evaluator.py` is a complete **generated example** of this format, not an authentic packet.

`prepare` creates a new operator directory with mode 0700 and refuses to reuse it. Only `public_query.npz` and `public_training.npz` may be exposed to a candidate after operator qualification. Query fields are opaque evaluation IDs, held-in and held-out unit IDs, relative bin left edges, `prediction_units`, `packet_sha256`, and held-in `visible_counts`. Training contains opaque training IDs and corresponding visible/target counts. No source trial IDs, absolute times, condition labels or movement labels are included in either public projection.

`private_gold.npz`, `private_protocol.json` and `private_receipt.json` remain scorer-only. The receipt records SHA256s of both public files and both private inputs. The packet identity commits to all metadata and full source count bytes, including excluded rows. Hashes detect mixups after construction; they are not proof of native acquisition, truthful attestations or a secure candidate sandbox. The scorer trusts its operator-owned gold; never let a candidate replace that file. This library neither launches candidates nor claims filesystem/process isolation.

Submission NPZ fields are exactly `trial_ids`, `heldout_unit_ids`, `bin_left_edges_ms`, `packet_sha256`, scalar `prediction_units: spikes_per_bin`, and `expected_counts` of shape `(evaluation_trials, bins, heldout_units)`. IDs and bins must match in order. Archives are data-only, with pickle disabled, validated NPY headers, at most 20 fields and a 128 MiB total expanded limit.

## Commands and references

Run from the implementation directory using an existing Python environment with NumPy. The smoothing command additionally needs existing SciPy and scikit-learn. No command installs dependencies or reads the network.

```sh
python3 evaluator.py prepare --metadata operator_metadata.json --source-counts operator_counts.npz --output-directory prepared
python3 evaluator.py mean-reference --training prepared/public_training.npz --query prepared/public_query.npz --output mean.npz
python3 evaluator.py smoothing-reference --training prepared/public_training.npz --query prepared/public_query.npz --output smooth.npz --audit smooth-audit.json
python3 evaluator.py score --gold prepared/private_gold.npz --submission mean.npz --output mean-score.json
python3 -m unittest discover -s tests -v
```

The smoothing recipe follows pinned `examples/baselines/smoothing/run_smoothing.py`: a normalized Gaussian with SD=30 ms, length `int(6*30/bin_ms)`, standard deviation `int(30/bin_ms)`; convolution separately within each trial; log(smoothed held-in counts + 1e-4); and one `PoissonRegressor(alpha=.01)` per held-out unit, fitted only on training rows. No scaler, movement labels, evaluation targets or between-trial convolution enter fitting. The native integer truncation is preserved: 20 ms bins use length 9 and SD 1 bin. Default 500 iterations retry at 2500 then 12500 when needed; predictions clip to [1e-9, 1e20]. This interface additionally fails on final nonconvergence, nonfinite output, all-zero training units or missing reference inputs rather than inventing an imputation or treating an unsupported fit as qualified. The modern `scipy.signal.windows.gaussian` location implements the source's `scipy.signal.gaussian` function. MIT attribution is preserved in `NLB_LICENSE`.

The bounded controls used an existing Python 3.11 environment with NumPy 2.4.6, SciPy 1.17.1 and scikit-learn 1.9.1. The complete 22-test suite requires these libraries and contains no skip path for missing dependencies or external evidence. Exact official metric parity defaults to the package-relative `vendor/nlb_evaluation.py`, an unmodified 18,292-byte copy of the pinned upstream source under the included MIT `NLB_LICENSE`. An optional `NLB_OFFICIAL_SOURCE` override is accepted only if it matches SHA256 `05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476`. The test verifies that hash before extracting only `neg_log_likelihood` and `bits_per_spike`; it does not import the full vendored module. This control executes generated arrays, not an authentic native campaign. No test downloads source, reads dataset payloads or requires the external evidence directory.

## Remaining admission work

Native payload verification and numerical acquisition conversion, official mask validation, condition-label verification, authentic full-packet equality, exact prospective condition-transfer/split scope, frozen access and budgets, authentic reference/comparator runs, independent reproduction, rights/release review, and scientifically justified admission criteria remain open. Neither this code nor its tests clears those holds. No authentic data, model evaluation, paid API call or scientific performance result was produced during this construction.
