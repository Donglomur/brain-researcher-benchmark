# Complete original Figure 3b: reproduction and improvement

This additive mode evaluates the complete original Figure 3b population assay:
all 14 sessions/eight people, contextual layer 5, lag indices 17–19, and all
42 cells. Each frozen candidate/condition execution has 5,685 held-sentence
software callbacks. These are not required counts of processes or API calls.

Both reports use the **same recovered predictions** within an access arm:

- Reproduction reports signed and absolute per-cell differences from the
  authenticated provided-author values, with existing session and equal-session
  signed differences. No binary tolerance is chosen.
- Improvement reuses the unchanged original comparison, including equal-session
  paired delta and eight-person sensitivity diagnostics. A positive point
  estimate is not statistical superiority or current SOTA.

The paired entry supports paper_data and paper_data_author_code. It freezes
both existing per-arm protocols before dispatch, checks matched source, store,
schedule, support, reference, runtime and resource limits, and requires disjoint
candidate/output/provider contexts. Every writing path is disjoint from both
arms' protected source, reference, candidate, runtime, assistance and dependency
paths. Path separation does not qualify their content or the native host. It then runs each original runner once,
sequentially. A second-arm failure preserves the first arm's files and publishes
no paired success. There is no automatic retry.

The old selected-store/runner scope remains original_figure3b_improvement inside
the unchanged embedded protocol and existing receipts. The new envelope names
the additional reporting mode; it does not rename earlier evidence. The broader
224-array reproduction contract is unchanged and remains a separate option.

## Operator protocol and execution

Start from two complete, canonical, separately admitted protocols for
original-figure3b-execution-v1/run.py. Preserve each JSON object and its SHA256.
The per-arm envelope schema is
language-original-figure3b-dual-outcome-protocol/v1; its exact keys are in
run.py:KEYS and the published contract.json. Required policy values are:

~~~json
{
  "scope": "original_figure3b_population_dual_outcome",
  "outcomes": ["reproduction", "improvement"],
  "output_policy": "shared_frozen_candidate_predictions",
  "execution_policy": "existing_native_admission_required"
}
~~~

Each envelope also supplies its exact condition, absolute dependency_root
(the task's maintained implementations directory), entry_sources size/SHA256
pins for this directory's run.py, outcomes.py and contract.json, the unchanged
selected_protocol, its selected_protocol_sha256, and an
outcome_output_bytes limit no larger than 1 MiB.

Use the paired schema for a complete two-condition attempt:

~~~json
{
  "schema": "language-original-figure3b-dual-outcome-pair/v1",
  "scope": "original_figure3b_population_dual_outcome",
  "execution_policy": "sequential_two_existing_runs",
  "arms": {
    "paper_data": "<complete per-arm envelope object>",
    "paper_data_author_code": "<complete per-arm envelope object>"
  },
  "pair_output": "<fresh absolute private operator JSON path>",
  "pair_output_bytes": 131072
}
~~~

The angle-bracket strings above describe required objects/paths; they are not an
executable protocol. Serialize the completed protocol with sorted compact JSON,
allow_nan=False, and a final newline, and provide its exact SHA256:

~~~sh
python3 -I -B run.py \
  --protocol /absolute/operator/paired-protocol.json \
  --protocol-sha256 EXACT_PROTOCOL_SHA256 \
  --execute-admitted-native execute-admitted-original-figure3b-dual-outcome
~~~

The single-arm envelope is also accepted for an individual attempt; its receipt
is not a completed two-condition study. The two-arm shared-output design runs
two schedules (11,370 callbacks total). Using distinct reproduction and
improvement programmes in both arms instead requires four complete schedules.

This CLI has no caller-score grading route. It delegates the original protocol
to the exact maintained runner, authenticates its saved RECOVERY.json using
the returned size/hash, then composes reports. The helper reconstructs and
hash-checks the reference packet from that recovery and requires agreement with
the actual unchanged comparison. It does not reread original reference arrays
or open a new scoring endpoint.

## Admission, outputs and limits

The maintained native provider still requires its real Linux/bubblewrap 0.11.0,
cgroup and fresh-state qualification plus live admission. This component does
not create that admission, install a runtime, supply a provider override or
turn generated controls into original execution. The original runner constructs
the provider before opening original store arrays. Both per-arm protocols pass
the maintained static preflight before either runner dispatch; actual host
admission may still fail at either arm.

Each successful arm writes an additive, exclusive
output_root/FIGURE3B_OUTCOMES.json, preserving COLLECTION.json, RECOVERY.json
and all other original receipts. Only two completed arms produce the private
paired result. Qualification flags remain unpromoted.

Resource limits are additive: each arm retains the original collection/recovery
store traversals, component counters and provider caps. Reporting additionally
reads at most 4 MiB of the authenticated recovery per arm; composition admits
only a bounded 256 KiB recovery tree. The per-arm additive result is capped at
1 MiB and the pair result at 128 KiB. These are stop limits. A separately
admitted finite whole-pair deadline must cover both existing runs, source
imports, reporting and cleanup. No single shared RAM/I/O meter is claimed.

Undefined cells remain present and propagate. Original global PCA, centered
smoothing, support exclusions, public exposure and equal-session weighting are
unchanged. The 567-column population assay does not resolve the separate
579-unit/selectivity crosswalk. Neither report claims all-paper reproduction.

## Generated entry controls

The eight entry controls exercise the actual parser, paired preflight, CLI,
dispatch, recovery-byte authentication and exclusive publication. The positive paired CLI control doubles only the maintained native runner,
which emits complete synthetic recovery receipts; it then calls the real outcome
composition and the actual pinned unchanged comparator for both arms. Negative
boundary controls additionally use a labelled outcome double. No original store,
provider child or model is opened. The separate outcome controls exercise the
numerical edge cases.

Standalone repository invocation:

~~~sh
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-001/implementations/original-figure3b-outcomes-v1/test_entry.py -v
~~~

For a postimage outside the repository or an owned campaign:

~~~sh
python3 -I -B test_entry.py \
  --legacy-root /absolute/task/implementations \
  --artifact-root /absolute/existing/generated-artifacts -v
~~~

A parent unittest harness may import the test module and call
configure(legacy_root, artifact_root) once before discovery, then inspect
control_accounting(). All tests share a 1 MiB cumulative generated-write
reservation (including failed attempts/postimages) and an 8 MiB managed
source/fixture-read reservation. The standalone temporary-directory route runs
only on explicit test execution; import performs no generated writes.
