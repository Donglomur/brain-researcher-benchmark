# Selected immutable views for the original language task

This component authenticates a trusted operator's prepared store once and constructs a view for one original feature job and one held qid. It preserves the original train/query row order while excluding that invocation's held prepared responses. It does not launch a candidate, mount files, create a sandbox, prepare authentic source arrays or qualify a complete benchmark run.

The original task remains 14 sessions from eight people, 58,926 feature jobs, 6,776,076 held-qid requests and 224 result arrays. Those counts describe the existing source schedule; the tests here use generated inputs. No model, fit or authentic prediction is executed.

## What a view contains

`FeatureJob` identifies one source session, field, feature family, layer and lag, together with its complete qid/time maps and response-shard partition. `select_rows` reproduces the unchanged source predictor's `qid != held` training selection and `qid == held` query selection. Each selected shard joins exactly its qid's row positions. `assemble_request` restores the original training row order and returns the original training features, training responses, query features and context. It rejects missing, extra or held response arrays.

`build_view` produces a public JSON descriptor and a separate private mount plan. The public descriptor includes one complete feature matrix (the union of the original train and query features), qid/time metadata, selected training response shards, ordered row joins and the original context. It exposes no other layer's matrix. The held response file is neither authenticated nor included in the mount plan. Full qid/time metadata is already recoverable from the original callback's training qids, held qid and ordered train/test time indices; it is not a new response-label channel.

Private object UUIDs, host paths, whole-store identities, support-class/source-response hashes and cache accounting remain operator-private. Public aliases are fixed names. The public view ID is SHA-256 of the public descriptor and therefore changes only with selected visible content or its declared context. Changing a held **prepared response shard** or another layer's feature leaves it unchanged. Changing selected features or training responses changes it. This is a new `language-selected-immutable-view/v1` identity; it is not the old submission bridge's hash of materialized callback arrays.

The unchanged source smooths responses before its qid split and uses its original lag and shuffle operations. This adapter preserves those semantics. Its held-shard property does not claim that changing raw firing data cannot affect other prepared rows through source preprocessing, or that the original design has independent unsmoothed train/test observations.

## Custody and limits

`ImmutableStore` accepts a finite typed operator manifest. Every used ordinary, single-link, read-only NPY file is fully authenticated against its expected size, SHA-256, primitive dtype, shape, order, finite values and exact extent. Qid/time arrays are retained; feature and response bodies are discarded after authentication. Reuse checks the device, inode, mode, link count, extent, mtime and ctime without rereading or rehashing the same base array. A failed authentication or stability check poisons that cache. Symlinks and writable or hard-linked files are refused.

This reuse assumes a trusted host, prepared manifest and cache lifetime. It does not resist a privileged host replacing content and restoring identity, validate that arbitrary caller-declared files came from the original source, or enforce read-only mounts against a participant. A later provider must authenticate the original preparation lineage, enforce its namespace and descriptor boundary, hide private paths (including mount metadata), freeze one candidate globally and prove fresh participant state and closure for every invocation.

Finite read admissions include an EOF probe for each first authentication. Working admissions include retained manifests/maps, live selection and descriptor reservations, and temporary file authentication space. These are conservative cooperative bounds, not operating-system RSS enforcement. The caller owns the lifetimes and aggregate budget of returned plans and assembled requests. A descriptor over its declared bound produces no view. `public_descriptor()` returns a copy; the immutable serialized bytes remain authoritative.

## Controls and integration

Run:

```sh
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-001/implementations/original-immutable-views-v1/test_views.py -v
```

The generated source-equivalence control traverses all 4,209 original jobs for one generated session, comparing every original callback's arrays and context. Other controls cover privacy under held/other-layer mutations, sensitivity to permitted inputs, cache reuse and mutation refusal, exact training-shard membership, read/work/descriptor bounds and ordinary-file custody. NumPy is the only external control dependency.

The prior packed collector can retain original row predictions and authenticate closure records, but it does not create the closure evidence. A provider, global candidate freeze, participant-side reconstruction, bounded stdout collection, authenticated lifecycle journal and final private scorer join are still required. Current public descriptors and per-shard checks are a correctness interface, not a measured scalable deployment.

Arithmetic over the saved authentic support census gives 1,312,357,554 training-shard references and 2,665,371,564 warm-cache stability checks across all requests. Repeating this descriptor's row lists would encode 58,072,993,062 numeric row entries: at least 116,145,986,124 bytes in numeric fragments alone. A largest request selects 348 data objects. These are prospective cumulative operation/serialization counts, not measured runtime, peak RAM or an allocation. A production transport must avoid repeating these descriptors and opening every shard at once while preserving exactly the same allowed view; no such native transport is qualified here.

Grouping cannot broaden feature or response exposure; a grouped scheduler also needs an explicitly bounded collector that restores the canonical source job order. No complete store, full-run output allocation, protected execution, AI reproduction or paper improvement is claimed here.
