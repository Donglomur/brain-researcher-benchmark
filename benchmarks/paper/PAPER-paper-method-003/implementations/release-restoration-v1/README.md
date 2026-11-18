# Preserve REVE release provenance through private restoration

This trusted operator continuation connects the existing
[`Episode.complete_predictions()`](../development-boundary-v1/boundary.py)
release to the unchanged private inverse-ID restorer and native-score metadata.
It preserves the episode, access arm, scientific profile, declaration, frozen
artifact, design, campaign roster and material identities throughout that join.
It creates no runner, scientific outcome, or benchmark registration.

The original full panel stays fixed: 109 people, 654 recordings, 9,837 epochs,
with every one of the 1,803 opaque test predictions restored to its exact original
event ID and source order. Prediction values are not normalized, rounded, clipped,
filled or rescored. Only bounded JSON metadata is read; no signal arrays, original
target labels, model weights, providers or scientific libraries are opened.

## Trusted continuation

`binding.restore(released, ...)` accepts the mandatory `release` plus `predictions`
wrapper returned by the existing completed campaign. Supply independently retained
context with exactly these existing release fields:

`episode_id`, `role`, `profile`, `declaration`, `artifact_identity`,
`design_identity`, `roster_identity`, `materials_identity`, `release_identity`.

Also supply the original panel, private map and material-manifest paths, their
selected panel/map identities, and the selected shared A/B `data_identity`.
The existing `packet_info` authenticates complete material semantics and checks
the role against the literal paper/data or paper/data/code packet. The release
must match the retained context, its complete own digest, and its prediction-file
pin before the original `materials.restore_predictions` is called.

Use a fresh `output` under an operator-owned mode0700 parent, outside every input
directory. The output remains private (directory0700, files0600) and contains:

- `opaque.json`: the exact canonical released predictions, including its newline;
- `original.json`: the unchanged native restorer’s complete original-ID output;
- `BINDING.json`: the unchanged full release, retained context, input pins and exact
  opaque/original byte pins, published only after the complete join is verified.

Retain the returned `binding_pin` separately from these writable files. The
manifest is not a resume token and is not an execution attestation. A forged
wrapper with forged caller expectations cannot establish genuine provider
execution or campaign completion. Those remain responsibilities of the existing
live owner and independently admitted runtime. The input and output locations
must stay under a trusted single writer; filesystem modes do not defend against
that operator deliberately rewriting or racing its own files.

Ordinary failures retain private partial outputs without a valid complete binding.
`BindingFailure.detail` records the stage, bounded error/errno, and conservative
I/O charges. The unchanged restorer is charged its actual per-call limits before
entry: four reads of at most16MiB+1 requested bytes and one16MiB write, including
failed paths. These are conservative charges, not measured output sizes.
`created_file_bytes` reports the successful actual output-file lengths separately.
Direct reads are capped at4MiB per metadata document,1MiB+1 for the released
prediction envelope,1MiB for the selected restored envelope and64KiB for the
binding. Imports, runtime I/O and directory metadata are excluded. External
supervision and campaign-wide accounting still cover interruption and blocked
syscalls; this component supplies no new wall, CPU or scientific budget authority.

## Verify before downstream use

`binding.verify(output, expected_binding_pin=..., expected_context=...,
expected_data_identity=..., expected_panel_identity=...,
expected_mapping_identity=..., original_like_only=True)` rechecks the externally
retained binding and both exact private output files. `None` or an absent pin
cannot disable authentication.

The original-like route rejects `frozen-program-full-test-context-v1` releases.
The prospective profile retains `requires_separate_outcome_binding=true`; it
cannot enter the unchanged current Table12 outcome route. Original-like declarations
also do not prove semantic non-adaptation or historical paper equivalence. All
runtime, scientific and paper-win qualification flags remain false.

`binding.join_score(output, score_path, expected_score_pin=..., **verification)`
adds a private provenance wrapper around an already captured native score. It
reads and preserves the exact native score-file byte pin, including its original
serialization, and joins the existing `prediction_file_sha256`, `panel_identity`
and preprocessing `profile` fields to the bound restored artifact. The entire
parsed native score remains unchanged, including any paired author-file identity.
The native preprocessing profile is distinct from the release’s scientific access
profile. This helper invokes no scorer, independently authenticates no target or
author predictions, and establishes no new numerical result or paper victory.
The caller must retain the bound wrapper with the score; using a bare score loses
the release provenance this component supplies.

## Focused construction controls

```sh
python3 -I -B tests/test_binding.py
```

Controls use the real release emitter with an explicitly inert campaign barrier,
full generated metadata, and the unchanged private restorer on all1,803 distinct
prediction vectors. They check exact original event order and values, both access
conditions, cross-arm/roster/context refusals, profile separation, mandatory pins,
actual private-file tampering, raw native-score serialization, output permissions,
and publication failure accounting. No previous materializer suite is replayed.
No authentic packet, target, array, candidate, scorer or Docker process is run.

Actual phase-view preparation, protected runtime deployment, matched campaign
budgets and author calibration remain separate. Historical Table12 preprocessing,
classifier/checkpoint and seed/run/SD lineage remain unresolved. This is a source
continuation for later reviewed integration, not a selector or admission change.
