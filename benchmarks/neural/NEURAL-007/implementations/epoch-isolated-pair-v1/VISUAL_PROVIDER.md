# Epoch-isolated visual provider

This is the separately named `epoch_isolated_raw_viewer_zero_shot_v1` condition,
paired with `epoch_isolated_raw_programme_zero_shot_v1` under
`epoch_isolated_same_epoch_v1`. It retains all 5,450 registered target epochs:
2,780 from development-001 and 2,670 from development-002. These are epochs
nested within two already exposed development people, not 5,450 independent
subjects. The five-class target and downstream metric are unchanged.

Every target uses a fresh local session identifier and stateless provider
requests that contain only this target. The shared byte-backed epoch packet
contains all original 3 x 3,000 calibrated-volt samples, at 100 Hz for 30 seconds,
plus only that target's original three clock features. The visual and numerical
arms bind the same projection and prior-policy pin. This matches underlying
epoch access, not numerical precision or visual and numerical representations.

Every visual request also carries a fixed public-task descriptor derived from
the pinned shared contract: both person identifiers and epoch counts, each
zero-based half-open epoch-index range, the exact
`{case_id}/{epoch_index:05d}` ID rule, person-list order followed by ascending
epoch index, the total 5,450 targets, class order and complete epoch geometry.
The compact rule matches the contract's target and required-target constructors;
there are no nonuniform per-epoch roster fields or 5,450 duplicated rows. These
are the same public cohort constants available to the programme through its
mounted contract. The descriptor adds no signal samples, labels or other-target
context.

## Information and interaction

The unchanged original renderer supplies an immutable complete three-channel
overview in every request. A different current same-target detail view is added
as a second image; identical encoded images are deduplicated. The original
1,400 x 820 canvas, source samples, gain choices and plotting behavior remain.
No tiny viewport replaces the overview. The detail may use an original gain,
ordered channel subset, or window of 100 through 3,000 samples, but every window
is constrained to the target epoch. Original absolute sample-clock positions
and the exact shared target clock row are retained.

The provider gets fixed instructions, target metadata, the immutable overview,
and current detail/state. It gets no earlier image or action transcript, prior
target answer, true label, demonstration, code, retrieval or other-target
signal. This removes both whole-night temporal context and within-target visual
transcript history. The overview remains available at the final decision.
The first accepted five-probability answer closes the target permanently.

This is not the existing whole-person/full-history condition. It cannot be
pooled as that condition or presented as an improvement on the original
full-night task. A richer temporal comparator must be identified as receiving
additional information. No scientific pass threshold, SOTA claim or completed
benchmark count is introduced.

Both arms must bind the same declared base-agent provider/model/revision and
`shared_declared_base_agent_prior_only` policy, with no extra assets.
The visual sender's declared provider must be `openai`, matching the reused
HTTPS endpoint. A policy declaration does not prove the absence of hidden
pretraining, task weights or richer assets in a future programme image;
authentic runtime/image provenance remains a separate gate. YASA, training or
reference assets unavailable to the visual condition are not matched inputs.

## Portable interfaces

Publish `epoch_visual.py`, `epoch_provider.py` and this document beside the
shared `contract.py` in `epoch-isolated-pair-v1/`. The source has no private
workspace paths. The existing nine-file whole-history integration remains
unchanged and is a separate dependency.

`epoch_visual.load_runtime(root, whole_history_integration_root=None,
whole_history_admission_root=None, contract_path=None)` authenticates the
existing client, source closure, HTTP admission helper and shared epoch contract.
Published defaults use installed sibling implementations; private preparation
supplies explicit authenticated source roots. Co-located imports use one shared
`contract` module identity. The original renderer, raster, probability validator,
bounded HTTPS Sender and Custody are reused.

`Session(packet, runtime, max_actions, session_id=None)` accepts only the
immutable shared EpochPacket. `initial()` renders the full original target.
`handle(action)` admits inspect, gain, channels, target-relative window and
respond. There is no navigation to a different epoch. `request_bytes(...)`
constructs the exact overview/detail request and checks its complete byte size.

`epoch_provider.run_epoch(runtime, packet, knowledge, budget, custody_root,
credential, input_token_bound, ...)` is a trusted operator call, not an
authorization to execute. It starts fresh target custody, connects the exact
request adapter to the unchanged HTTPS sender, records durable event evidence
before applying any action, and preserves failure evidence without retry.
A failing durable sink withholds the action. Credentials are never configuration
or command-line fields. Literal and decoded credential-echo guards are retained;
arbitrary escaped echoes in private failed raw responses are not claimed absent.

`audit_session(session_root, packet, runtime, knowledge)` sends no HTTP and
never invokes token-bound code. It reconstructs each overview/detail request
from the exact same epoch, validates the existing HTTPS receipt and response
contract, replays every accepted action, and verifies the first final answer.
The complete-arm collector additionally requires all original targets, unique
target sessions/response identities, person boundaries and the paired numerical
projection. A per-target helper success is not complete-arm admission.

## Custody and finite resources

A session directory contains CONFIG.json, END.json, events/ and turns/.
Each turn uses the unchanged REQUEST.bin, RESPONSE.bin, HTTP.json and BRIDGE.json.
Exact original PNG bytes are present in the retained request data URLs; there
are no duplicate image or wire files. Event records bind the current image
pins, target, state, action and hash chain. Configuration pins transitively bind
the shared prior policy, source closure and renderer runtime in every receipt.

The original provider Budget supplies explicit turn, history, request, response,
cumulative-byte, token and wall allocations. Requests contain at most two
same-target images and retain the unchanged 8 MiB sender limit. Complete
overview/detail requests that exceed the selected byte or token bound fail;
there is no resizing, omission, summary, fallback condition or automatic retry.
The sender reserves complete response custody, including an overflow byte on
failure. Request/response transfer accounting is separate from retained
metadata and image evidence.

The complete-input token-bound callback remains an external trusted requirement.
No guessed tokenizer or fabricated capacity evidence is supplied. Actual
per-frame/context acceptance, remote context isolation and scientific
performance remain unqualified. Generated controls may use finite fake HTTPS
only at the existing trusted sender seam; all qualification fields remain false.
No original packet, original waveform render, provider/model call, fit or
network access was performed during this source preparation.
