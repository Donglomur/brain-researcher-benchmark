# Hybrid artifact provisioning

This component creates an authenticated location map for all 80 frozen reference artifacts and prepares a fresh, unselected source proposal for the existing no-refit Hybrid replay. It helps authorized operators who already hold the exact accepted private source and data inputs. **It does not include the complete replay runtime or the private reference/model/data bundle.** The public synthetic-controls package is not substituted for that missing source bundle: its authentic loader is deliberately disabled.

The benchmark scope remains 20 people, 80 held-session folds, 4,884 complete trials and 163,135 eligible decisions. The accepted historical reference construction is distinct from the full protected replay, which remains unrun. This is processed human behavior with within-person cross-session interpolation, not unseen-person or neural-signal decoding. Folds, conditions and relocation commands add no benchmarks.

## Required operator inputs

Use CPython 3.11 and ordinary private paths outside the repository. The component itself uses only the standard library. It needs the following inputs for its respective commands:

- `locations`: the immutable accepted reference-result JSON, exactly 351,850 bytes with SHA256 `f9bb15d421d9182b594225c501214269af86ea9b89c83480bd4320efd1d702d5`, and the intended directory holding all 80 selected model files with their original opaque basenames. The command reads reference metadata; it does not read model bodies or prove their presence.
- `bind`: the accepted predecessor operation directory and all its 43 source dependencies, the three accepted V2 adapter sources, the selected map descriptor, and operator-local case/reference paths. The predecessor lock and adapter identities are fixed in `SOURCE_BINDING.json`. Other source dependencies must still exist at the paths bound by that private predecessor lock. Only operation-local files may reside at the supplied predecessor directory. This is not a general source-tree relocation tool.
- Actual replay, if separately selected: the exact case map, reference result and every original selected model. `bind` changes their locations only; the old immutable byte/hash identities remain in the output PLAN. Nothing in these commands grants access to or redistribution rights for those assets.

This repository currently does not distribute the accepted private 43-member no-refit source bundle. There is no public download command for it here. The two public commands remain useful provisioning operations for holders of that exact bundle; they are not a complete public benchmark runner. The independent [synthetic causal controls](../hybrid-causal-controls-v1/README.md) exercise a different, explicitly invented interface and cannot replace the required source or scientific inputs.

## Create the location map

Use the trusted `SOURCE_MANIFEST.json` hash recorded by the release/CI as `COMPONENT_SHA256`; do not treat a newly calculated hash of an untrusted manifest as provenance. Run from the repository root. The output file must not exist.

```sh
COMPONENT=benchmarks/neuroscience/hybrid-artifact-provisioning
python3.11 -I -S -B "$COMPONENT/provision.py" \
  --source-manifest-sha256 "$COMPONENT_SHA256" locations \
  --reference "$AUTHORIZED_REFERENCE_RESULT" \
  --artifact-directory "$PRIVATE_ARTIFACT_DIRECTORY" \
  --output "$FRESH_PRIVATE_LOCATION_MAP"
```

The command authenticates the exact reference before parsing it. It hashes all 80 original records with the same canonical encoding as the accepted producer and preserves each artifact's original bytes/SHA256. The selected directory must retain the original opaque filenames. Duplicate basenames or records and incomplete coverage are refused. The map is created exclusively with mode 0600 and is limited to 128 KiB. Its printed path/bytes/SHA256 descriptor is the input to the next command.

No artifact is selected by performance, labels or numerical uniqueness. Different folds may legitimately have identical model bytes. The later replay adapter checks every map record against the original reference, authenticates every model, and rejects missing/extra/foreign records or late file mutation. Neither the map nor private record identities enter the participant mounts.

## Bind a fresh operation proposal

```sh
python3.11 -I -S -B "$COMPONENT/provision.py" \
  --source-manifest-sha256 "$COMPONENT_SHA256" bind \
  --predecessor-directory "$AUTHORIZED_PREDECESSOR_DIRECTORY" \
  --adapters-directory "$AUTHORIZED_V2_ADAPTER_DIRECTORY" \
  --locations "$FRESH_PRIVATE_LOCATION_MAP" \
  --locations-bytes "$LOCATION_MAP_BYTES" \
  --locations-sha256 "$LOCATION_MAP_SHA256" \
  --cases "$AUTHORIZED_CASE_MAP" \
  --reference "$AUTHORIZED_REFERENCE_RESULT" \
  --destination "$FRESH_OPERATION_SOURCE" \
  --output "$FRESH_REPLAY_OUTPUT" \
  --caller "$FRESH_CALLER_OUTPUT" \
  --capacity-binding "$FRESH_CAPACITY_JSON" \
  --operation-token nb-hybrid-relocated-001
```

`bind` authenticates the entire predecessor source closure and all three adapters without importing or executing them. It copies operation-local source, preserves other pinned dependencies, binds the map and operator-local case/reference paths, and emits a new 43-member source lock plus `NEXT_OPERATION_PROPOSAL.json`. The case/reference byte/hash pins, model hashes, holdout policy, scorer, TRAIN selection and numerical outputs remain unchanged. No fit, data read, Docker command, capacity probe, installation or runtime dispatch occurs. The map is not opened by `bind`; its descriptor is bound for later exact validation.

The destination, output, caller, capacity and map paths must be distinct and must not nest inside one another. Output/caller/capacity leaves must remain absent. A failed source construction can leave an incomplete new directory; it cannot produce a successful scientific result. The proposal is explicitly unselected and must be independently checked before any execution.

## Run the generated interface controls

```sh
python3.11 -I -S -B "$COMPONENT/test_provision.py" \
  --source-manifest-sha256 "$COMPONENT_SHA256" -v
```

These controls authenticate the component before importing it and use invented metadata. They test all 80 map slots, canonical hashes, original pin preservation, missing/duplicate/invalid metadata, refusal of an unaccepted external source bundle, source composition with all 43 invented slots, fresh paths and bootstrap admission. The invented composition fixture intentionally cannot pass the public CLI's immutable predecessor admission. No human data, scientific fit, model inference, biological metric or protected replay is exercised. Passing it is not evidence of scientific or runtime readiness.

## Remaining execution and rights requirements

The generated operation retains its historical runtime/image and exact physical endpoint requirements. Their current validity is not asserted or probed. A current reviewed runtime/endpoint binding, fresh source-lock-bound capacity receipt, the complete 24 GiB output reservation and a separately selected full replay are still required. The existing 86,400-second work ceiling plus 600-second recovery cannot be replaced with a successful subset if the campaign times out. The separately built clean runtime used by the PFC work is not silently substituted or qualified for Hybrid here.

The location map adds one 131,072-byte read to the complete replay's conservative bound, yielding 15,084,075,045 bytes under the unchanged 16 GiB ceiling. Source/ledger/output caps remain enforced. These are source-derived bounds; no measured replay resource claim is made. Provisioning needs its own selected budget when used on actual inputs.

The repository MIT license applies to this authored component. The article, original data, reference artifacts and other third-party assets have separate rights. Public data redistribution remains unresolved; private access and source-specific permissions are operator prerequisites. The public component includes no reference artifacts, model parameters, observations, participant identities, raw captures or original upstream source copies. See [attribution](ATTRIBUTION.md). Original raw-event reconstruction, Julia/Float32 parity, ANN/symbolic/lesion/transfer reproduction and stronger scientific-reasoning claims remain outside this component.
