# Compact permitted inputs for original language requests

This component serializes one original request's allowed qid/time maps and ordered training responses into immutable bytes. A separate compact request descriptor binds exactly one feature matrix and the original job context. It replaces repeated row lists in the earlier selected-view representation; it does not execute a candidate, prepare authentic data, provide an operating-system boundary or qualify a complete run.

The paper task remains 14 sessions, eight people, 58,926 feature jobs, 6,776,076 held-qid requests and 224 result arrays. The existing source preprocessing, original per-job prediction interface and private scoring remain unchanged.

## Contents and identity

The versioned wire layout uses a canonical 64-byte header, followed by a full permitted float64 qid map, int64 time map and float64 training-response matrix in the original training-row order. The header declares the row count, training-row count, output width and held qid; reserved bytes must be zero. There are no held prepared responses, private response-source-row maps, host paths, private object IDs or whole-store/source-response digests in the bundle.

The builder takes the exact full qid/time maps as operands and checks their join to the reviewed selection. This preserves even signed-zero qid bytes while retaining the original equality-based membership rule. Query responses never appear among the allowed response-array operands. The decoder validates dimensions, extent, finiteness, qid domain, ordered times and the resulting train/query partition before returning read-only views over immutable bytes. Source training-target bit patterns, including signed zero and subnormals, remain unchanged.

Reconstructing the prediction callback returns the original training features, training responses, query features and context. Full X belongs to a single feature job; it is the union of that job's original train/query features. The full qid/time maps contain metadata already allowed by the source callback. Sharing an identical allowed response bundle never authorizes exposing another layer's features or retaining candidate state across requests.

The compact descriptor hashes only permitted bundle content, one selected feature identity and original context. Its feature digest is a **trusted operator input**, not proof that arbitrary caller-declared features were authenticated. Original source lineage and immutable-file authentication belong to the preceding preparation/store layer; actual descriptor/FD enforcement belongs to a later native provider. This is a new compact identity schema, not the older bridge's materialized-array request hash or the verbose selected-view hash.

The source performs smoothing, lagging and shuffling before its qid splits. These semantics are preserved. Isolation of held prepared-response shards does not establish independence from raw firing-data changes that propagate through original preprocessing.

## Bounds and remaining execution work

Callers provide finite output and working limits. The implementation checks primitive metadata and declared extents before numeric views, snapshots or copies that depend on them. Returned wire bytes are immutable; decoder array views cannot mutate them. Logical working admissions are cooperative estimates, not kernel-enforced RSS limits. A malformed or over-budget request fails without producing a usable packet.

This finite component does not implement a persistent bundle cache, LRU eviction, a store-file reader, sealed Linux descriptors, process namespaces, fresh execution, candidate freezing, output collection or lifecycle closure. It therefore makes no cache-hit, reuse, startup-time or throughput claim. The original packed collector's canonical source order remains in force.

The separately reviewed saved-census arithmetic gives 202,407 sufficient response-class/held-support units. Materializing each allowed target/maps bundle once would still produce 67,042,113,280 payload bytes cumulatively, before headers, rereads and recreation; canonical order does not guarantee once-only materialization. A later cache/provider must account for actual creation, rereads, evictions, descriptor traffic, state separation and all 6,776,076 fresh requests. No full campaign or output-storage allocation follows from this source component.

## Generated controls

```sh
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-001/implementations/original-compact-bundles-v1/test_bundle.py -v
```

The source-equivalence control traverses all 4,209 jobs of one generated session and compares every original callback's arrays, byte patterns and context. Other controls cover held-response/private-ID invariance, sensitivity to allowed inputs, signed-zero and subnormal values, immutable ownership, exact row joins, malformed wire headers/extents, resource admissions, forged selections, compact descriptors and feature/target geometry. Only NumPy is required. No original dataset, model fit, AI result or native sandbox is executed by these controls.
