# MorseEEG content identity preparation

The current source inventory records Git object IDs for 192 annex symlinks. Its
small extents describe pointer text, while `provider.Recording` needs the
size and SHA-256 of each underlying header, marker and signal file. This component
closes that conversion gap without changing the original reader, numerical
preprocessing, participant panel, 301-sample window, labels or scorer.

`content_identity.compile_metadata(pointer_bodies)` authenticates the unchanged
`registered-runtime/SOURCES.json` by SHA-256, requires exactly all 192 pointer
bodies from all 32 participants and both tasks, authenticates each body using its
Git blob object ID, validates the repeated SHA256E annex key, and extracts its
content extent and digest. Input is a mapping from the original source path to
immutable pointer bytes. The returned 64 records contain three content pins and
the unresolved event Git identity for each recording. No file is downloaded or
dereferenced, and no authentic recording is opened.

`compile_provider_selections(pointer_bodies, event_bodies)` additionally accepts
all 64 event bodies from a separately authorized operator. It authenticates their
Git object identities and computes their SHA-256 hashes without parsing or
returning event rows. Its result matches the existing provider's exact four-file
selection schema. Headers, markers and EEG must still be acquired and verified by
that provider before native use. A changed event body, missing source, duplicate
recording, swapped pointer or wrong recording path fails instead of shrinking
the panel. The small internal `_compile_metadata` function exists so generated
controls can exercise complete cohort assembly without authentic source bodies;
operators use the two public functions, which load the pinned inventory.

The source is [OpenNeuro ds007655 v1.0.2](https://openneuro.org/datasets/ds007655/versions/1.0.2),
at [Git commit d2e09f610d267b8b3679997f8bc4e52fe6ca402a](https://github.com/OpenNeuroDatasets/ds007655/tree/d2e09f610d267b8b3679997f8bc4e52fe6ca402a).
The exact existing inventory SHA-256 is
`3ec6ba3dcf60c49ee381126958a617a87eadfcbabce09a5cf8bd3eb12ab0af8e`.
Git object framing is included when verifying Git SHA-1 identities; neither a
plain SHA-1 nor the pointer body's SHA-256 is substituted for the payload digest.

The task-local tests use generated pointer and event bodies, with one metadata
check against the existing public inventory. Eight controls passed through the
shared bounded test pool. They cover the payload/pointer distinction, Git object
framing, malformed keys, role bounds, all 64 provider selections, exact event
binding, and missing/swapped/extra/duplicate source rejection. Generated controls
establish software behavior only. This component does not authorize native
preparation or change task admission. Full payload authentication, complete
usable trial counts, delivered-prefix timing/information opportunity, reference
competence, native matched controls, and paired-program qualification remain
unestablished. No neural-understanding performance is measured here.
