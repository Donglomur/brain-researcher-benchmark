# Complete full32 adaptive-gain observation

This separately named condition, `erp-full32-first-unclipped-gain-observation-v1`, captures observations only. It does not classify, fit, predict, score, invoke a provider, or claim participant isolation. The original fixed-gain20 condition and its incomplete reference calibration remain unchanged.

The source admits the exact original full32 public manifest and the existing consumer's complete 6,400-query roster: the predefined 32-person complement to six training and two development people, 200 queries per person. This is neither the original 400-case/two-development-person condition nor the entire 40-person collection. The four fixed demonstration labels are known; query labels are inaccessible to this implementation. There is no private-material operand.

For each of the four demonstrations and each of all 6,400 queries, start at 20 native units per division and try only `20, 50, 100, 200, 500, 1000`, in order. Always retain Cz and Pz, all 1,024 samples in `[-256,768)` at 1,024 Hz, and no display filter. Stop at the first image whose **two rendered clipping warnings are absent**. If either warning remains at 1000, retain that terminal image with `cap_clipped`; never drop that case. There is no accuracy, target, amplitude-array, feature, or class-dependent selection. Known demo labels are used only for the existing displayed title and original label/order admission.

The unchanged renderer flags a channel when any sample is strictly outside `[-3g,3g]` for gain `g`; equality is in range. The policy reads only exact red warning glyphs or blank white pixels in the two fixed warning rectangles. Source-bound font, coordinates, PNG dimensions, CRCs, scanlines and metadata are checked. Partial or unexpected warning pixels fail; a trace near the plot border is not a clipping test. Every successful capture records its action and prior/new state, pins, lossless PNG, original raster and scanline pins, warning evidence, display scale, and resolution/loss metadata. An action file precedes rendering, so a failed rendering attempt remains identifiable. Completed cases and incomplete attempts survive failures; there is no resume, retry, or subset switch.

Production already persists the maintained lossless compressed PNG, preserving every original pixel and filter byte. The raw renderer PNG exists only in memory; it is not written as a second artifact. Its original stored-DEFLATE bytes are reconstructible from retained scanlines and its pin. No compression implementation change is needed. Unclipped does **not** mean lossless waveform observation: vertical sample placement rounds at 30 pixels/division, with an in-range sample rounding bound of `g/60` native units; horizontal placement rounds by at most half a pixel. Rasterized segment geometry, shared pixels, and interpolation do not recover exact signal samples. Increasing native units/division reduces vertical resolution. Out-of-range segments may remain omitted at the cap. Native stored amplitude is not independently calibrated microvolts, and physical display delay remains unresolved.

Adaptive attempts, gain metadata, and all retained intermediate images provide a different information budget from a single fixed image. The current gain20 image classifier is not valid unchanged across these scales. No scale-aware prediction method or competence claim is supplied. This source does not establish authentic full32 visibility, authentic runtime/disk sufficiency, learning performance, independent generalization, or successful participant delivery.

## Operator interfaces

Use Python 3.10+ on a POSIX host providing `SIGALRM`, `O_NOFOLLOW`, and ordinary single-link files. The implementation is standard-library-only. `SOURCE_BINDINGS.json` pins its own executable plus five exact external files. Only `viewer.initial_state`, `viewer.transition`, and `viewer.display_metadata` are used; the viewer's dynamic dependency loaders, sessions, collector and scorer are not called. `consumer.PacketSession`, the renderer and codec have no nonstandard or dynamically loaded dependencies on this path. The action schema is frozen as a compatibility dependency. The final publication freeze must authenticate this entire package and binding file externally.

The commands below are prospective examples, **not authorization to execute**. `REPOSITORY` is the verified repository root, `IMPLEMENTATION` the installed directory, `PUBLIC` the exact original full32 public packet, and `OUTPUT` a fresh disjoint protected directory. Resource values require a separately selected operation. Actual artifact, read, time and memory budgets are **unselected and unqualified**. `PROSPECTIVE_OPERATION.json` distinguishes this unresolved resource requirement from a loose mathematical ceiling; it does not recommend a local allocation.

```sh
python3 -B "$IMPLEMENTATION/observation.py" capture \
  --repository-root "$REPOSITORY" --public-root "$PUBLIC" --output "$OUTPUT" \
  --read-bytes "$CAPTURE_READ_BYTES" --write-bytes "$CAPTURE_WRITE_BYTES" --work-seconds "$CAPTURE_WORK_SECONDS"

python3 -B "$IMPLEMENTATION/observation.py" audit \
  --repository-root "$REPOSITORY" --output "$OUTPUT" \
  --receipt-bytes COMPLETE_BYTES --receipt-sha256 COMPLETE_SHA256 \
  --read-bytes "$AUDIT_READ_BYTES" --write-bytes "$AUDIT_WRITE_BYTES" --work-seconds "$AUDIT_WORK_SECONDS"
```

The theoretical 151.368 GiB ceiling is obtained by assigning every one of the maximum 38,424 attempted images the generic 4 MiB PNG admission cap, then adding conservative JSON caps. It is not a measured or estimated compressed total and does not justify recommending a 152 GiB local allocation. Production compression is already in place. A later root-selected complete label-free byte/visibility census could measure actual compressed bytes and visibility across all four demos and 6,400 queries with the unchanged policy, preserving same-pixel compression, cap-clipped outcomes, quantization and resolution limits. No such census is selected or authorized here. The resource variables above remain unset until a separately selected, evidence-based operation admits them.

Capture emits an externally preservable pin for `COMPLETE.json` only after all 6,404 records finish. That receipt pins the complete ordered record inventory and source/policy intent. The artifact-only audit requires this external receipt pin, replays every action/state, decodes all images, checks lossless representation and all metadata, rejects any premature clipped termination or continuation after unclipped, and admits all 6,400 queries and four demos together. It never reopens waveforms. Its origin claim relies on trusted capture execution and external receipt/source custody; it does not independently reauthenticate original-packet identity or prove that an arbitrary image was rendered from a particular waveform. A hash alone is not an execution attestation.

`participant_projection(directory, record_pin, trial_id, demonstration, modules, budget)` audits one record and returns only image references, actions, display metadata, loss/resolution evidence and selected outcome. Its query projection has no numeric waveform arrays, query labels, source paths or cohort roster. Image paths are relative to that one record directory. A future separately selected transport must give each query the four corresponding audited demo projections plus its own query projection, enforce isolation, authenticate receipt/source custody, and prevent access to the operator packet. This module is the complete observation capture/audit source, not that participant transport or a classifier.

## Generated validation

```sh
python3 -B "$IMPLEMENTATION/test_observation.py" \
  --repository-root "$REPOSITORY" --scratch-root "$FRESH_OWNED_SCRATCH"
```

No installs or authentic inputs are needed. Controls exercise the actual renderer/codec, metadata custody, warning tampering, all-six-gain cap, inclusive boundaries, same demo/query rule, full-population admission, original-manifest rejection, and the real `PacketSession` query path. The full-roster generated packet deliberately has one valid generated query and malformed placeholders thereafter; it proves first-failure retention and refusal, not complete scientific rendering. No generated test claims successful authentic 6,400-record capture. The packet pin substitutions occur only inside the generated test fixture; production has no alternative-manifest interface.

All 16 correctness controls passed in 4.013 seconds, with a 269.8 MiB macOS peak RSS above the planned 256 MiB expected envelope. That excursion remains unqualified under the original resource plan. An isolated six-gain check used 195.0 MiB; it does not qualify full-suite memory. Root prospectively allowed 384 MiB for genuinely needed review follow-ups; no full-suite rerun was made to relabel the first result. Ordinary review added three independent focused controls. Future CI should reserve at least 384 MiB and 60 seconds for this suite; other-platform memory has not been measured. `VALIDATION.json` preserves counts, platform, costs and review. These are correctness controls, not scientific benchmark results.
