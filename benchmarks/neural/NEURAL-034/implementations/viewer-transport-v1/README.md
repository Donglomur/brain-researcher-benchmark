# Restricted active-fold calcium viewer transport

This component connects the existing seven-mouse viewer to a separately confined
participant process for each held-mouse fold. It closes the local transport,
fresh-state and complete-response collection gap; it does not add a benchmark,
change observations or scores, run a model, or establish scientific qualification.

Every fold retains all 120 labeled training windows from six mice and all 20 query
windows from the held mouse. Every window retains the existing 300 samples of
12 source-processed calcium traces and the aligned binary behavior proxy.
The unchanged renderer uses sample centers `0.05 + arange(300)*0.1` seconds.
The task remains context-A/B prediction, with exactly 140 original probabilities
across seven folds. The unchanged registered scorer reports every mouse,
equal-mouse balanced accuracy and log loss, and all six fixed comparisons.

Other folds' training labels reveal the current query answers. Each participant
therefore receives only typed observations from its active fold and starts in a
new process and empty temporary working directory. Filesystem writes are denied;
the empty directory is destroyed at shutdown. The restricted collector admits only seven distinct,
successfully closed macOS-sandbox sessions under the same frozen source,
client, runtime and resource condition. A missing or failed fold is not replaced
by a favorable surviving subset.

## Operator invocation

Use an existing Python3.11+ environment with NumPy for the operator and an
installed framework Python for the standard-library participant client. No
installation or network acquisition occurs. The macOS client executable must
be a framework interpreter; Apple's `/usr/bin/python3` developer launcher is
not an admissible substitute. For example:

```sh
OPERATOR_PYTHON -I -B transport.py fold \
  --fold 0 --packet /operator/fold-00/public.npz \
  --client /operator/frozen-client.py \
  --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
  --sandbox macos --max-actions 161 --max-images 140 \
  --max-output-bytes 67108864 --wall-seconds 900 \
  --output /operator/results/fold-00
```

Those limits illustrate the complete scripted-control interface, not a scientific
study allocation or empirical performance estimate. The operator freezes one
common budget before any study. All 120 training windows remain available even
when a participant chooses to inspect fewer. The supplied `scripted_client.py`
inspects every training window, then every query, submits fixed probability 0.5
for each query, and finishes: 161 actions and 140 images per fold. It consumes PNG
bytes without analyzing them. It is a construction control, not an AI attempt.

After seven separately completed folds, collect in fold order 00 through 06:

```sh
OPERATOR_PYTHON -I -B transport.py collect \
  --packets /operator/fold-00/public.npz /operator/fold-01/public.npz \
    /operator/fold-02/public.npz /operator/fold-03/public.npz \
    /operator/fold-04/public.npz /operator/fold-05/public.npz /operator/fold-06/public.npz \
  --sessions /operator/results/fold-00 /operator/results/fold-01 \
    /operator/results/fold-02 /operator/results/fold-03 \
    /operator/results/fold-04 /operator/results/fold-05 /operator/results/fold-06 \
  --output /operator/results/complete
```

The transport uses the unchanged viewer replay validator, then produces
`probabilities.json` in the original grader format. It adds
`TRANSPORT_COMPLETE.json`, an unscored local
delivery receipt. Private targets and reference results are never read by the
transport. Grading is a later operator operation under the original contract;
transport completion is not model performance or authentic reference competence.

## Participant protocol and local boundary

Each binary frame begins with two unsigned network-order 32-bit lengths, followed
by JSON and optional raw PNG bytes. Client requests contain JSON only, at most
4,096 bytes. Operator JSON is at most 32,768 bytes, each PNG at most 4 MiB.
Oversized prefixes are rejected before their claimed payload is read. The first
frame contains instructions, counts, allowed actions, an opaque episode identity
and frozen limits, without a preselected image, fold identity or source path.

Actions are exactly the existing `training`, `query`, `inspect`, `gain`,
`respond` and `finish` actions. A query must be rendered before its first and
only valid response. Training images carry the allowed context label; query
images carry only their original opaque query ID. There is no action for source
files, numerical arrays, private labels, the scorer or another fold. Invalid
requests fail the session and preserve its history. Final responses cannot be
revised after feedback.

The macOS deny-default sandbox allows the captured client, required system
runtime reads and reads within the fresh empty workspace. It denies other operator-data
reads, all filesystem writes, network access, child creation and
other-process inspection. The process receives anonymous pipes and a sanitized
environment. Broad admitted system runtime roots are trusted and must not hold
operator secrets. New local process state and workspace isolation do not prove
that an external provider conversation or remote model cache was reset. A real
provider bridge must independently establish fresh provider context, image
delivery and prohibited-tool enforcement before any viewer-interpretation claim.

The optional `protocol_only` mode is a trusted diagnostic with host privileges;
its histories are refused by the restricted collector. A backend renderer or
well-formed transcript alone is not participant isolation. The operating system,
operator source tree and trusted client/bridge remain part of the boundary.

## Histories and complete collection

Operator-only records bind captured client bytes, declared interpreter, sandbox,
fresh episode and limits. Every handled inbound frame and delivered outbound
frame is captured with exact bytes, direction, offset, hash and sequence chain.
Incomplete reads/writes remain marked incomplete. The viewer's existing action
chain remains independently replayable. Failures are not erased, resumed or
automatically retried.

The client must exit successfully after terminal closure, and its owned process
group must be absent. Timeout or leftover descendants fail the attempt; cleanup
targets only the newly owned group. No other project process is signaled.
Source, inputs, runtime, response images and action/answer histories are replayed
at collection. Duplicate episodes, reordered/missing folds, changed clients,
mixed limits, forged support and modified histories are refused.

Replay has a real cost: the original viewer replay and independent wire replay
each render the recorded observations again. Full authentic proposals must count initial and
replayed images, all seven folds, captured bytes and process resources. Small
generated PNG controls do not estimate authentic rendering cost. There is no
automatic model/API launch or authentic run in this package.

## Scientific scope and verification

This is viewer-mediated interpretation of a historically exposed, selected
seven-mouse development panel. It is not no-tools direct interpretation, the
paper's full eleven-mouse archive, or raw microscopy. Calcium and behavior are
jointly visible. Behavior-only matched candidate comparisons or a separately
adopted observation condition are needed to attribute performance to calcium.
ROI selection, whole-session processing, context/day order and behavior polarity
remain scientific limits. Viewer/program comparisons differ in representation
and computational access and do not identify a causal effect of tools.

Focused generated controls use the actual restricted participant process and
existing viewer state machine with explicitly generated lightweight PNGs. They
check the new boundary and complete transport, not the unchanged renderer again.
No scientific arrays, model fits or AI results are substituted by these fixtures.
Run `python3 -B test_transport.py` with the existing NumPy environment on macOS
and the framework client interpreter available. Exact dependencies and the
reviewed source cutoff are recorded in the adjacent descriptors.

The separate `python3 -B test_protocol.py` command runs five portable protocol
controls for CI, including seven protocol-only histories refused by the
restricted collector. It does not simulate a sandbox or skip isolation tests.
The thirteen macOS boundary methods were verified as twelve initial methods plus
one added targeted post-finish control, without repeating the unchanged suite.
Those host-specific results remain distinct from portable protocol validation.
