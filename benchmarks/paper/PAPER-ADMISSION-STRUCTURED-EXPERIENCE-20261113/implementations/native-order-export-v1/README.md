# Supplied native index order export

The original fold bridge records which rows belong to each fit, but deliberately does not guess the ordering produced by pandas `Index.difference` and `reindex`. This component fills that metadata gap by **observing the actual supplied native indexes**, preserving their sequence, and joining them to the already validated original row memberships. It implements no splitter, sorter, pandas replacement, neural preprocessing or fitted model.

The scope remains thirteen original sessions, ten source-order trial folds and three source-context decoders: 390 fit units and the unchanged 117-cell error vector. The existing original-fold bridge and original-row scorer are exact hash-checked dependencies. Their source files, memberships, endpoints and qualification flags are unchanged.

Both dependency bodies are captured and hash checked before execution. The exporter compiles those exact bytes; a private import facade for the bridge binds its scorer loader to the captured scorer bytes. Existing Python bytecode caches cannot replace either body, and no process-global import hook changes. The unchanged bridge's source recheck can still refuse a concurrent scorer replacement. This loader binding establishes which reviewed component code executes; it does not authenticate scientific data, the native producer or runtime declarations.

## Capture at the native callsite

```python
recorder = NativeOrderRecorder(owner_index, membership_plan, owner_secret,
                               source_runtime_declaration)
# At each separately qualified source train_slice callsite, before fitting:
recorder.record(unit_id,
    source_context=source_context,
    training_index=y_train.xs(source_context, level="type").index,
    query_index=y_test.index)
# Only after every one of the original 390 units has been captured:
capture = recorder.finish()
ordered = join_native_order(owner_index, membership_plan, owner_secret, capture)
```

This illustrates an operator callback, not an admitted source runner. The accepted training index names are exactly `trial, result, time_bin`: the source context slice has dropped `type`. Only that field is restored, using the bound unit's source context. The query index must have exactly `trial, type, result, time_bin`. Unknown shapes, reordered names, changed row identities, duplicated or missing rows and cross-fold/source membership refuse. A unit can be recorded only once; incomplete 390-unit collections cannot finish.

Each supplied index is consumed once with `tolist()`. Values use the same scalar `item()` export convention as the existing scorer; the exporter then compares finite JSON row keys without equating integer and floating labels or converting strings to numbers. It preserves the supplied sequence without sorting. The recorded index class and level dtype strings are descriptive metadata, not a serialization of all pandas index internals or proof of a matching native library version.

The capture stores complete row-position permutations and hashes of their exported index values. The owner index supplies the reversible original row keys. `join_native_order` checks exact coverage, those order/value hashes and the original feature/index/plan bindings, then produces calibration row order and the matching existing opaque query IDs in native query order. This allows a later source runner's prediction sequence to join to the unchanged bridge and scorer. It does not choose a new calibration ordering, silently coerce labels or replace the original membership plan.

`source_runtime_declaration` requires the recorded source commit, producer SHA256, runtime-manifest SHA256 and source-run-receipt SHA256. These are declarations and content bindings. A caller can supply a fabricated index or declaration, so structural validation is not proof of native provenance. Restoring the omitted context also relies on the genuine context-bound source callsite. No model, scientific library or data loader is imported by this component.

## Evidence and remaining qualification

The exact source operations were previously observed on the [pinned producer's rendered GitHub page](https://github.com/heyslab/StructuredExperience_NatNeuro_2026/blob/8c62c1cfe91644e3030a35d3ebb45e3bee94c3c8/ms_figures/ephys_time_decoding/time_decoding_ephys.py) and recorded with the preceding bridge. That observation is not newly authenticated raw source. This construction makes no fresh HTTP request and does not infer pandas sorting defaults or version parity. Before authentic use, the operator must qualify source custody, the actual native frames and dependency versions, original input/behavior/unit support and the frozen feature-index universe.

The metadata objects contain private trial/context/target lineage. Keep the owner index, plan, capture, ordered selection recipe and secret inaccessible to actors. No process, storage, chronology, fitting, budget or leakage boundary is enforced here. Original all-unit-zero-event trial handling, paper-only interpretation, rights, native preprocessing/LDA parity, competent baseline, biological uncertainty and meaningful same-task improvement decision remain unresolved. `source_native_parity_established` and `execution_admitted` remain false and `paper_win` remains null.

The new tests use explicit generated index-protocol objects, not pandas, authentic neural data or source runtime. They exercise all 390 units, the 117-cell scorer join, preserved unsorted sequence, exact native shapes and type-sensitive identity, missing/duplicate/rebound memberships, declaration binding and rejected qualification promotion. No previously passing component suite is replayed.

Five separate loader controls exercise valid unchecked stale caches for both dependencies, replacement after capture/recheck, fail-closed replacement before recheck, and both initial hash guards. Saved private evidence distinguishes the initial eight order controls from these five affected controls. Prospective public CI should discover all thirteen with `python3 -I -S -B -m unittest discover -s benchmarks/paper/PAPER-ADMISSION-STRUCTURED-EXPERIENCE-20261113/implementations/native-order-export-v1/tests -p 'test_*.py'`; central CI enrollment remains the integrator's responsibility.
