# NEURAL-047 history observation transport

This additive component delivers the existing whole-worm SAAV task through two distinct conditions: a complete numeric direct-observation prompt and a typed history viewer. It uses the exact permitted training/query packets from `full-conditional-programme-v3`; it does not change the landmark, target, animal folds, N/B/NB arms, or scorer. V3 source and historical manifests are unchanged.

Authentic input qualification remains unresolved. This component has no raw-data downloader, native converter, model caller, fitter, or target loader. Its generated controls establish software behavior only. A deployed direct or viewer study still requires qualified native clock/animal/SAAV preparation, independently trusted packet pins, participant isolation and an admitted complete-panel execution protocol. There is no direct-model or viewer-model result.

The existing source audit pins the author decoder at `c7e7e18a84cde5dc02df9d63492293b38402eb2c` and the WT aggregate at SHA-256 `4fcf5906d95d144ed1d6741cc86f4ef4fd332dec0f52e00ee5f34e8b75fe6d45` (236,931,813 bytes). Its WB builder supplies the named SAAV trace and dorsal-positive curvature but no physical clock/native-frame map. This revision reuses that audit and makes no new acquisition claim. The inherited scientific references are the [primary paper](https://doi.org/10.1038/s41593-026-02257-5), [Dryad release](https://doi.org/10.5061/dryad.8sf7m0cz2), and [pinned decoder](https://github.com/flavell-lab/SAAV_Decoding/tree/c7e7e18a84cde5dc02df9d63492293b38402eb2c).

## Delivered observations

Each session is one held-worm fold and one N, B, or NB arm. Every training event from every other worm is required, with its existing opaque group and binary direction label. Every held-worm query is required without a label. The participant receives no panel-wide file, source recording name, reversal end/duration, future samples, odor, private target, score, or another context's output.

The direct prompt contains every supplied time offset and channel value as shortest round-trip JSON numbers in a text table. It has no participant observation actions. The typed viewer supports:

- `catalog`: current-context case keys, roles, sample counts, allowed channels, and training-only labels/groups.
- `history`: one current-context case, unique allowed channels, and inclusive physical time bounds within `[-4.8, 0]` seconds. It returns the exact selected native sample indices, times and values plus an SVG waveform.
- `submit`: exactly one finite dorsal probability per query case.
- `abstain`: an explicit reason for leaving the entire context unscored.

The SVG uses a fixed physical time axis. Each channel has a displayed source-value range, a polyline and a marker for each selected sample. Exact numerical values accompany the graphic; pixels alone are not the equality claim. The component makes no amplitude-unit or online-causality claim for the original processed source signals. It does not interpolate samples, normalize amplitudes, infer physical units, summarize away events, or select demonstrations. The condition is full outer-training demonstrations, not zero-shot interpretation. A viewer host must display the returned SVG and sample values faithfully; this source does not qualify a particular front end.

Source packet validation reuses V3's past-only history validator and adds complete training membership and group checks against the public panel. Matching pins establish that direct and viewer conditions received byte-equivalent permitted observations. Equal input availability does not imply equal visual perception or equal actions taken.

## Operator interface

`delivery.py` uses the Python standard library and imports the existing sibling V3 validators and scorer admission. `SOURCE_BINDINGS.json` identifies the directly reused source closure. Run the controller in a trusted operator process. Give the participant only the opening stdout payload and the allowed JSON-line request/reply channel. Never give the participant the controller's filesystem, Python object, arguments, panel, prepared-packet paths, another context, or stderr. Host isolation, timeout and prevention of outside tools remain operator responsibilities; receipts alone do not prove those properties.

For one independently qualified, canonical V3 packet, substitute operator-owned paths and the exact pin from the trusted preparation manifest:

```sh
python3 -I -S -B delivery.py session \
  --panel /operator/prepared/panel.json \
  --packet /operator/prepared/fold_000_N.json \
  --expected-packet-bytes PACKET_BYTES \
  --expected-packet-sha256 PACKET_SHA256 \
  --mode typed_viewer \
  --context-output /operator/session/context.json \
  --transcript-output /operator/session/transcript.json \
  --output /operator/session/response.json
```

`direct_observation` selects the complete text prompt. The context receipt is retained before participant interaction. The transport accepts one request per input line and returns one JSON object per output line. For example, after using the opening catalog's query key:

```json
{"action":"history","case_key":"case_<32 hex>","channels":["saav_history"],"start_seconds":-4.8,"end_seconds":0}
```

Only the typed-viewer condition permits that request. Direct observation accepts only `submit` or `abstain`; a trusted no-tools response collector sends that terminal message on the participant's behalf. The session closes permanently after a valid complete response. Missing/duplicate/foreign queries, nonfinite values, booleans, out-of-range probabilities, unknown actions, extra fields and future times fail admission. CLI errors are terminal and retain a failure audit; EOF never becomes an abstention or a completed response. Reuse of an existing output path is refused.

The transcript retains ordered request/response hashes and a hash chain, including the opening payload and the terminal reply. It contains no hidden targets. The response binds the preceding observation transcript hash. These are transport records, not signed proof of participant behavior. Retain original stdout/stdin in the isolated operator audit if independent byte-level replay is required.

The protocol caps each packet/payload and total accepted response payload at 64,000,000 bytes, and the session at fewer than 10,000 participant requests. These are explicit transport ceilings, not inferred authentic feasibility. A complete context exceeding a ceiling fails; it is never silently cropped or treated as a smaller valid panel. Host wall-time and process resources must be bounded separately.

## Complete paired collection

Retain the trusted pre-interaction context receipts separately from responses. Create a JSON object with keys `direct_observation` and `typed_viewer`, each containing **all** `3 × number_of_worms` context receipts, and another identically keyed object containing all corresponding closed responses. Do not derive expected receipts from participant response fields. Then:

```sh
python3 -I -S -B delivery.py collect-paired \
  --panel /operator/prepared/panel.json \
  --contexts /operator/closed/expected-contexts.json \
  --responses /operator/closed/responses.json \
  --output /operator/closed/paired-collections.json
```

Collection rejects incomplete animal/arm support, duplicates, response-context substitutions, cross-mode outputs, and any direct/viewer pair with unequal observation pins. It returns separate mode collections. Each `collections.<mode>.submission` has the existing `neural047-predictions-v1` format and is admitted by the unchanged V3 scorer. No target file is accessed by collection. The existing scorer retains animal-macro balanced accuracy, equal-animal log loss, all arms, and its abstention-before-target policy. Direct/viewer scores must retain their mode labels; they are not F or I programme outcomes and must not be pooled with those modes.

`collect --mode ...` is also available for inspecting one mode's complete set. Paired-study admission requires `collect-paired`. No new metric or scientific readiness flag is introduced.

## Controls and remaining scope

`test_delivery.py` uses three invented worms, two reversal events each, and all N/B/NB contexts through the existing preparation function. Controls independently recover every text-table value, compare every viewer sample and SVG marker, reject withheld-field/time/identity violations, exercise probability closure and matched-mode collection, verify target-free abstention, and run the actual JSON-line CLI including EOF failure. No authentic recordings, private historical labels, model calls, fitting, or scientific scores are used.

Run only through the wave's reviewed shared test pool. The external handoff records the exact invocation, measured costs and results. Passing these controls does not qualify native inputs, real visual rendering, participant isolation, context capacity, deployment, reference competence, direct interpretation, viewer interpretation, or scientific performance.

Integration proposal: register this task-local component as source for direct-observation and typed-viewer delivery, retain the unqualified deployment and native-source limits, and enroll its controls centrally. Canonical task/contracts/catalog files were deliberately left to their owners.
