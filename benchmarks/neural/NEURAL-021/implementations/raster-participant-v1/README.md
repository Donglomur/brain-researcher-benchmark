# NEURAL-021 raster participant presentation candidate

This component presents the existing count observations as PNG images while retaining the original task, Session, answer contract and replay. It is a separately versioned construction candidate. It does not establish native neural understanding, participant filesystem isolation, no-tools enforcement, image readability, task difficulty or submission readiness.

The scientific endpoint remains velocity x/y in m/s for all 92 queries, each with 30 ordered pairs. All 65 units and 35 count bins remain available. Counts are exact integers in their original 20 ms intervals; response timing, six-bin histories, source column order and retrospective-task caveats stay visible. The original trained-programme condition and numerical scorer are unchanged.

## Presentation and exposure

`raster.py` accepts only the pinned original SVG vocabulary and geometry. SVG text, count arrays and operator-side replay never become observation-message fields. It draws every literal header, axis, count and calibration label using the bundled, authenticated DejaVu Sans Mono font at 13 px. The complete font license is included. No font substitution, case folding, resizing, implicit cropping, tiling or dropped units/bins is performed.

The fixed control requests all 272 calibration images followed by all 92 query images and immutable 30-by-2 zero answers in original query order. Its typed-viewer variant also requests one explicit crop. This checks transport support; zeros are not an inference method. The inherited operator API continues to expose bounded calibration, full query, answer and finish operations. Explicit query crops are exclusive to typed-viewer mode and require the full query first. Direct observation receives full images. A future participant study must freeze calibration exposure and its complete schedule; control success alone does not freeze a study protocol.

Typical full queries are 1710 by 1710 pixels and full calibrations 1710 by 2420. The original count-dependent width can reach 6365, so the maximum calibration is 6365 by 2420. Typed crops retain original unit/bin labels, interval start coordinates and repeated explanatory axes. They are separate participant actions, not a hidden way to reduce direct-observation support.

A 6365-by-2420 PNG is not proof that a downstream model can read it at native resolution. Provider APIs and display clients may resize images. The adapter does not solve that qualification gap. Any later fixed tiling/paging scheme must preserve complete support, coordinates/order, repeated axes and a fixed direct-observation schedule; it requires separate review.

## Message boundary and provenance

`raster_transport.py` loads a private module instance of the exactly pinned predecessor transport and the explicitly pinned renderer. It keeps the predecessor Session, cleanup and source replay. Observation responses contain only sequence, image type/media type, PNG base64, width and height. There is no SVG source, raw numerical array, file path or textual metadata chunk in the PNG payload. Base64 is framing only: a model connector must decode or attach it through an actual image input channel. `fixed_response_client.image_content_block` constructs a validated MCP-style image part without calling a provider.

The private receipt records each original SVG event hash, rendered PNG hash, pixel hash, dimensions and renderer/font/runtime profile. Actual PNG response bodies replace SVG response hashes before the next wire-chain link; transmitted-byte counts cover PNG frames. A failure after Session advancement irreversibly seals the exchange. First final answers and all-query completion remain inherited and unchanged. Participant closure precedes original source replay in the predecessor lifecycle. No new numerical scoring is introduced.

This is an operator API boundary, not an OS sandbox. A local child can still access files unless an independently qualified launcher prevents it. Rendering raw data on the operator side does not establish native/no-tools performance by a future model. The prior authentic SVG fixed-control result does not transfer to raster execution, provider display or isolation.

## Bounds and runtime

PNG is grayscale8 with exactly IHDR, IDAT and IEND; metadata, animation, trailing data, extra zlib streams and unsupported filters are refused. Maximum raw scanlines are `2420 * (6365 + 1) = 15405720` bytes. An explicit stored-deflate fallback gives a constructive PNG maximum of 15406963 bytes, including filter bytes, zlib and chunk overhead. Canonical base64 requires at most 20542620 bytes, inside the 22 MiB response-frame limit. Each image is handled independently.

The generic response-wire ceiling is 49413103992 bytes: 2142 frames including hello, each at most 22 MiB plus its four-byte frame header. It is a conservative streamed-byte ceiling, not retained output storage, an expected study cost, or an admitted authentic-run budget. Receipts remain bounded at 2 MiB with no omitted rows. Future execution needs separate whole-operation wall/RAM/output bounds; inherited child cleanup does not itself enforce a rendering deadline outside an outer controller.

The installed local runtime tested here is Python 3.11.6, Pillow 12.3.0 and FreeType 2.14.3. The selected source/runtime pins are not a complete transitive environment identity or OS RAM guarantee. Other runtimes may produce different antialiasing/compression; actual profile and pixel/PNG hashes must accompany every run. No dependency was installed. Pillow imports only for drawing; the participant PNG validator is standard-library code.

## Generated checks

From a complete repository checkout with its existing Pillow runtime, the focused commands are:

```sh
python3 -I -B benchmarks/neural/NEURAL-021/implementations/raster-participant-v1/test_raster.py RasterTests
python3 -I -B benchmarks/neural/NEURAL-021/implementations/raster-participant-v1/test_transport.py RasterTransportTests
```

These select 14 image/layout/codec controls and 12 transport controls. Local construction used the same classes with explicit source paths and an isolated installed site path. The full support transport check uses labelled generated blank PNG fixtures; the real-render checks test image content separately, including all count cells, extreme integers and all calibration rows. The single-query real-render transport control checks their composition. The optional `FullRasterScheduleTests` class is excluded from normal enrollment: its attempted 729-render run was interrupted on coordinator direction and has no completed result. Avoid broad default discovery that selects it.

`VALIDATION.json` preserves exact method attribution, the repaired fixture NameError, the interrupted attempt, saved image identities and limits. The existing scientific CI lane pins Pillow 11.1.0; a proposed enrollment is a compatibility check, not evidence it has run or is pixel-identical to this local runtime. Neither an authentic raster run nor an AI evaluation has been performed. No readiness/count/scoring promotion accompanies this candidate.
