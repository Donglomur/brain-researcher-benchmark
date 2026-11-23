# Fixed-image ERP attachment preparation

`dispatch_manifest.py` builds one portable payload containing four demonstration PNGs and one committed query PNG. It derives filenames from anonymous IDs, authenticates file extents and SHA-256 hashes, checks the retained renderer's fixed PNG format, and embeds the validated bytes. A transport can consume these exact bytes without manually copying image paths.

This is an input preparation component. It does not call a model, dispatch an agent, open protected labels, score predictions or establish that a participant received or inspected an attachment. The current collaboration transport has no adapter for this payload. Until an adapter consumes it directly and records delivery, this component alone cannot prevent manual path errors in a separate workflow.

The manifest has exactly five top-level fields:

- `schema`: `erp-image-dispatch/v1`.
- `protocol_sha256`: the independently supplied frozen protocol SHA-256.
- `prompts`: `direct` and `programme` strings, each containing exactly one `{trial_id}` placeholder and no other braces.
- `demonstrations`: four descriptors in `demo1` through `demo4` order.
- `queries`: the frozen anonymous query roster; IDs use `case-0001` form.

Each descriptor contains exactly `image_id`, `file`, `bytes` and `sha256`. The filename must equal the ID plus `.png`; arbitrary paths and query-label fields are rejected. The selected asset directory is an operator argument and never appears in the returned payload. The builder reads only the four demonstrations and requested query; it does not open the other query images. Both arms receive identical ordered attachment bytes. The prompt differs by the frozen arm policy.

The renderer contract is 1400 by 820, eight-bit RGB, with exactly IHDR/IDAT/IEND chunks and no ancillary metadata. CRC, decoded extent, row-filter and trailing-compressed-data checks complement the file hash. This proves bounded image structure, not scientific correctness, readability, safe prompt semantics, or absence of labels encoded in pixels. The export owner must inspect the public schema and renderer semantics separately. The component is not a sandbox against a hostile host or an enforcement mechanism for participant tool restrictions.

Run generated controls from this directory with `python3 -B -m unittest test_dispatch_manifest`. The controls use distinct valid synthetic images, including wrong-file swaps, missing files, bad pins, path typos, traversal, symlinks, duplicate IDs/keys, unexpected label fields, invalid CRCs and overexpanded PNG data. They do not exercise authentic neural data or actual transport.

For future integration, invoke the builder with `--manifest`, `--manifest-sha256`, `--protocol-sha256`, `--assets`, `--trial-id` and `--arm`. Its stdout is the complete JSON attachment payload. Do not substitute hand-written paths for the embedded bytes. Freeze and record its exact output hash before dispatch, then retain the transport's first delivery outcome, complete available tool trace and first response. A delivery error is an error record, not an opportunity to silently retry or replace a query. An assertion that images were opened must come from actual transport/view evidence, never this validator's success.

This source changes no full-cohort scorer, exporter, endpoint or registration. The separate prospective study proposal is not an authorization to select cases, read labels, render images, dispatch participants or score a new comparison.
