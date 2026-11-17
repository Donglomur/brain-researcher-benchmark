# Both original SMC-RNN result rows: AI reproduction interface

This package freezes **both** source-method prediction sets before opening the
original test targets, then runs the unchanged NLB evaluator on each. It returns
the complete eight findings: co-bps, velocity R², PSTH R² and forward bps for each
of the causal-proposal and noncausal-proposal methods. Published values and signed
differences are retained individually; no arm or companion metric is averaged away.

This closes the joint reproduction-evaluation interface. It does **not** supply a
qualified episode policy, a hostile-code execution boundary, a scientific agreement
threshold, or an evaluated AI attempt. Every finding and the overall scientific
outcome remain `unknown`. A later scientific assessment must use independently
justified, prospectively frozen agreement and uncertainty criteria. A small
numerical difference, including the earlier author calibration, is not an AI
reproduction pass.

The existing `source-matched-nlb-v1` and `offline-nlb-outcomes-v1` packages remain
unchanged. The latter still accepts **one** original offline prediction set for
improvement; this two-source-method route imposes no extra recipe or two-arm
requirement on that separate outcome.

## Actual prediction and source requirements

Use the original MC_Maze 20-ms test panel: 2,295 decoder-training trials and 574
test trials, 137 held-in and 45 held-out neurons, 35 observed bins and ten future
bins. The original 108-condition universe and actual scored-condition support
remain intact. `source-matched-nlb-v1/reference_panel.json`, its scorer and original
protocol, and the task's current `reproduction.v1.json` are byte-pinned.

Each arm supplies an HDF5 `mc_maze_20` group with the retained submission ABI:
six required scored rate arrays and optionally both training-forward arrays.
Eight **findings** does not mean eight mandatory arrays. Full dimensions, input
identity, finite nonnegative values and direct HDF5 storage are checked using the
retained validator. Scalar-only answers and incomplete tensors cannot enter this
route. One prediction file may be at most 512 MiB; JSON metadata is limited to
1 MiB and the canonical target to 256 MiB.

For this specifically named source-method reproduction condition, execution
declarations retain 192 particles, 32 repetitions and `smooth: false`. The two
original source-method observation dependencies and filtered outputs must be
verified by the trusted source-method review. An independently authored faithful
implementation is allowed: its code need not match author Git and this interface
does not require supplying author checkpoints. Recipe declarations are **not**
proof that the declared computation happened. The 32 Monte Carlo repetitions are
not independent animals or recordings.

## Trusted policy and execution records

Before the participant episode, the operator reviews and freezes an exact
`smc_paired_reproduction_policy_v1` object. `validate_policy` defines its complete
field set. It binds the current canonical task, reproduction contract, complete
source panel, original author recipe, paired delivery and both condition manifests,
plus distinct materials, selection/adaptation, budget, source identity, agreement,
uncertainty and operator review receipts. This package does not provide fabricated
review receipts or a runnable policy with placeholder approvals.

The delivery is the existing additive offline pair: `paper_data` and
`paper_data_author_code`. Both receive the same admitted data, paper and task
materials; the latter also receives the official source. Its condition manifest
must bind the exact supplied public test-panel JSON, reproduction contract,
registered task and author protocol. The joint freeze selects one of these access
conditions. A separate participant episode evaluates the other condition.

After independent verification of the actual participant execution and granular
outputs, the operator freezes a `smc_ai_reproduction_execution_v1` record containing
the task, outcome, condition, policy hash, participant method ID and exactly the two
arm records. Each arm binds its actual submission hash, analysis-source hash, run
receipt, source-method review and granular-output review, seed, original declared
recipe and explicit behavioral-guidance declarations. A single verified execution
may produce both arms; the record does not manufacture two runs. The operator
supplies the execution-record hash separately to the CLI.

`validate_executions` gives the exact schema. Author-calibration or single-candidate
improvement records cannot be passed directly as AI reproduction evidence. Hashes
and role fields authenticate bytes and declared joins; they cannot establish the
truth of a forged review. Trusted review, participant attribution, isolation and
the before/after chronology remain operator responsibilities. The interface does
not infer chronology from a self-reported wall-clock timestamp.

## Freeze, then evaluate

With provisioned inputs and real operator-reviewed policies, the two commands are:

```sh
python reproduce.py freeze \
  --causal /candidate/causal.h5 --noncausal /candidate/noncausal.h5 \
  --panel /delivered/inputs/mc_maze/test/panel.json \
  --episode-policy /operator/reproduction-policy.json \
  --episode-policy-sha256 "$SMC_REPRODUCTION_POLICY_SHA256" \
  --pair-manifest /delivered-pair/pair_manifest.json \
  --delivery-manifest /delivered/delivery_manifest.json \
  --executions /operator/verified-ai-executions.json \
  --executions-sha256 "$SMC_REPRODUCTION_EXECUTIONS_SHA256" \
  --condition paper_data --output /operator/joint-freeze.json

python reproduce.py score \
  --causal /candidate/causal.h5 --noncausal /candidate/noncausal.h5 \
  --panel /delivered/inputs/mc_maze/test/panel.json \
  --episode-policy /operator/reproduction-policy.json \
  --episode-policy-sha256 "$SMC_REPRODUCTION_POLICY_SHA256" \
  --pair-manifest /delivered-pair/pair_manifest.json \
  --delivery-manifest /delivered/delivery_manifest.json \
  --executions /operator/verified-ai-executions.json \
  --executions-sha256 "$SMC_REPRODUCTION_EXECUTIONS_SHA256" \
  --freeze /operator/joint-freeze.json \
  --target /private-targets/mc_maze_target.h5 \
  --target-sha256 f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865 \
  --scorer-source /verified-nlb-tools/nlb_tools/evaluation.py \
  --scratch-root /operator/scratch --scratch-budget-bytes "$SMC_REPRODUCTION_SCRATCH_BYTES" \
  --output /operator/eight-findings.json
```

Use the existing source qualification environment for authentic evaluation. The
source package's `requirements-cpu.txt` records it; generated CI compatibility
does not requalify a different environment. No acquisition, installation or
scientific execution is implied by these examples. A new authentic operation
requires the operator's resource allocation and execution protocol.

Freezing has no target argument. Scoring revalidates the policy, execution record,
condition, full panel and **both** prediction files; copies both into isolated
temporary snapshot files; checks the copies against the joint freeze; and only
then hashes and opens the target. Scratch allowance is explicit, at most 1 GiB,
and enforced cumulatively before each copy write. Reserve both snapshot sizes and
the evaluator's memory/CPU separately before running. Temporary snapshots are
removed on failure as well as success. The complete result is installed atomically
without overwriting an existing result; failure of either arm emits no partial
eight-finding report.

The evaluator is the unchanged, hash-verified original `nlb_tools` implementation.
The report preserves all eight measured values and published anchors, source and
prediction identities, declared execution provenance, behavioral guidance,
environment versions and public-target exposure. Both original test targets and
published anchors are already public; local exclusion does not create an untouched
holdout. The report establishes neither improvement nor current SOTA.

## Generated verification

`test_reproduce.py` exercises actual tiny generated HDF5 submissions, both-arm
admission, the unchanged official evaluator, numerical likelihood identities,
target-read ordering, wrong-role and wrong-output refusals, metadata/input bounds,
scratch accounting and atomic output behavior. These fixtures are software
controls, not neural observations, author baseline runs or model attempts.
