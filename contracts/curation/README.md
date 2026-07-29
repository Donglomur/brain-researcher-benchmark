# Automated curation contracts

These publishable contracts define the boundary between a durable controller and
a bounded scientific worker. They describe artifacts and lifecycle decisions;
they do not provide queue, lease, tracker-write, data-download, or execution
authority. A publishable schema is not a claim that every conforming payload is
safe to publish.

## Files

- `curation-contracts-v1.schema.json` contains the shared JSON Schema definitions.
- `evolvable-rubric-v1.md` is the canonical C1–C10 and F0 rubric.

Use a definition by its JSON Pointer, for example:

```text
contracts/curation/curation-contracts-v1.schema.json#/$defs/CurationJob
contracts/curation/curation-contracts-v1.schema.json#/$defs/StageResult
```

Most draft artifact definitions allow `additionalProperties` so their scientific
contents can evolve. The server-facing `ArtifactRef`, `Actor`, and
`CurationTransition` envelopes reject unknown fields; producers must use the
exact append interface.

## Authority boundary

- The scheduler/controller selects one bounded job, leases it, pins its inputs
  and budget, validates the returned artifact, appends a transition, and updates
  any tracker projection.
- The worker processes exactly the assigned job and returns one `StageResult`.
  It does not select another topic, claim a queue item, write the tracker, append
  a transition, or declare a release.
- The immutable artifact store is scientific evidence. A tracker is a
  rebuildable projection and must not be cited as measured evidence.
- Only an adjudication transition may set `outcome=released` and
  `to_state=released`. A worker result has no `released` outcome.

`CurationTransition` is a controller-internal append payload. It can contain
artifact URIs and references with `author_private`, `oracle_private`, or
`restricted` visibility, so it must not be copied to a public board or log.
A redacted transition log or tracker projection is a separate view contract:
it may expose only public fields plus opaque identifiers/hashes selected by the
controller. This schema deliberately does not define that public view.

## Evidence states

| Status | Meaning |
|---|---|
| `reported` | A source reports the value; it has not been independently checked. |
| `verified` | Identity, availability, or another non-computational fact was checked against a stable source. |
| `measured` | The value was produced by an executed probe with input, command/log, and output artifact references. |
| `planned` | A bounded probe is specified but has not run. It cannot satisfy a pass gate. |
| `missing` | No adequate evidence or executable probe is currently available. |

Never silently promote `reported` or `planned` evidence to `measured`.

## Lifecycle

The schema's `x-stage-transition-contract` map is normative. A stage consumes
one of its declared lowercase input states. `passed` produces the declared
stage output; `killed` produces the stage-specific kill state; `blocked`
produces `blocked`; and `retry` moves from `blocked` back to one declared input
state. `ADJUDICATE` alone may produce `released` or `retired`. The controller,
not the worker, chooses and appends the transition.

The normal paths are:

```text
SCOUT -> PAPER_RESOLUTION -> DATA_PREFLIGHT -> ACQUIRE
ACQUIRE -> STEP0 -> BENCHMARK_DRAFT -> CALIBRATE_BENCHMARK -> ADJUDICATE
ACQUIRE -> FAMILY_DRAFT -> CALIBRATE_FAMILY -> ADJUDICATE
ADJUDICATE -> released | retired
```

`STEP0` means the exact paper claim or benchmark-critical lever was executed on
the declared obtainable substrate. `CALIBRATE_BENCHMARK` means oracle,
adversarial, and frontier-agent runs were actually performed and reviewed.
`CALIBRATE_FAMILY` means the required family probes, including measured C2,
C4 falsification, and F0 freshness evidence, were actually performed. A desk
assessment or fixture is not any of these.

## Integrity and visibility

`ArtifactRef.sha256` is the lowercase SHA-256 of the referenced bytes. The
complete reference always includes `artifact_id`, `uri`, `sha256`,
`media_type`, and `visibility`; none of those fields is optional. Likewise,
`Actor.executed_by` requires a 64-character lowercase SHA-256 `skill_sha` and a
complete `tool_manifest_ref` so the execution environment is bound to the
transition.

The client does not submit a transition `content_sha256`. The append server
canonicalizes the accepted transition, computes its receipt hash, and returns
that hash with the append receipt. Reusing a `transition_id` with identical
content is idempotent; reusing it with different content is rejected.

Public summaries and redacted views may expose opaque artifact IDs and hashes
for `author_private`, `oracle_private`, or `restricted` evidence, but must not
copy its URI, contents, credentials, hidden lever, or oracle material. The
controller-internal transition payload retains the complete reference for
integrity and authorization checks.

## Private benchmark authoring references

`BenchmarkQuestionSpec.private_failure_axis_ref` and
`private_hidden_lever_ref`, when present, must be `PrivateArtifactRef` values:
their visibility is `author_private`, `oracle_private`, or `restricted`, never
`public`. Worker-facing `BenchmarkQuestionSpec` and
`EvolvableQuestionFamily` release statuses are only `draft` or
`adjudication_pending`; retirement and release are expressed by an adjudication
transition, not by a worker artifact.
