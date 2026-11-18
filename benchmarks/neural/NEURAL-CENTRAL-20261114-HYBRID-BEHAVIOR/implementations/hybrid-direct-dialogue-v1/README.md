# Direct numeric dialogue for Hybrid behavior

This component fills the task's missing **prompt/response protocol core**. It
adapts the existing causal `OnlineSession` into provider-neutral messages: one
current 12-field behavioral state, the exact current opaque token, and all
previous observations and committed responses within that same trial. A valid
four-probability response must be committed before another state is revealed.
The next trial starts a fresh message history. No labels, private identifiers,
future length, model artifact, score feedback or tool request enters a message.

The original consumer remains the authority for observation validity, ordering,
reply schema and probability normalization. The loader authenticates its exact
13,637-byte source before executing those captured bytes. This component adds
no data reader, fit, metric, model invocation, API client, or source download.

## Operator interface

```python
consumer = direct_dialogue.load_consumer()
# accepted_private_decisions and secret remain in the trusted operator process.
session = consumer.OnlineSession(accepted_private_decisions, secret)
dialogue = direct_dialogue.DirectDialogue(consumer, session)
request = dialogue.next_request()
# Send only request["messages"] to a separately qualified no-tools provider.
# Start a fresh provider conversation whenever request["new_trial"] is true.
# Return a single raw JSON response as bytes; no retries or JSON repair.
dialogue.submit(response_bytes)
# Continue until next_request() returns None after the final commitment.
private_predictions = dialogue.finished_predictions()
```

The example is an interface sketch, not an executable model evaluation.
`DirectDialogue`, `OnlineSession`, private decisions and the token key must never
be passed to untrusted code. The transport must independently reject tool-call
and multiple-candidate provider envelopes, forbid network/filesystem tools, and
qualify conversation/state reset. Copying messages is not OS isolation and does
not establish that a provider has no hidden persistent state. Context overflow
must fail the entire evaluation; it must not truncate history or drop trials.

## Scientific scope

The condition is explicitly `unassisted_numeric_dialogue`. The frozen candidate
condition can receive a TRAIN-selected model artifact; this new component does
not. A contrast between those conditions would therefore confound artifact
access and must not be described as matched-information reasoning superiority.
The original source contains processed behavioral states, **no neural signals**.
A successful use of this interface would not demonstrate neural interpretation.

Full evaluation still requires the authenticated complete accepted cohort:
4,884 trials and 163,135 commitments across 20 people and 80 held sessions. Use
the unchanged complete-cohort scorer, participant/session weighting and paired
participant uncertainty. Finishing an `OnlineSession` alone proves neither
those counts nor the original source admission, protected transport or model
performance. No new scientific result or readiness promotion is claimed.

## Generated controls and integration

`test_direct_dialogue.py` exercises this adapter against the exact existing
consumer using five invented decisions in two trials. It checks stop-and-wait,
history preservation/reset, future-data invariance, private-field exclusion,
strict malformed/tool-envelope rejection, mutation resistance, roundoff-only
normalization, and refusal of altered consumer source. These are interface
controls, not a reduced scientific benchmark or authentic replay.

Thirteen generated controls passed in one shared-pool invocation. No authentic
cases, model artifacts, provider calls or biological metrics were evaluated.

Run through the existing project test pool using isolated Python and the
explicit `--consumer-source` path when testing outside the repository. After
integration as `implementations/hybrid-direct-dialogue-v1`, the default source
path locates the adjacent frozen-candidate consumer. The new component and its
test command require source/CI enrollment by the integrator; no current runner
or task access-mode status is changed by these private postimages. Provider
admission, complete transport lifecycle and actual full-cohort execution remain
unfinished.
