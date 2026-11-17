# Restricted count viewer for NEURAL-095

This component makes the complete existing DMFC task available through a restricted observation interface. It delivers the cue-only and neural views as separate `restricted_count_viewer/v1` sessions, replays every observation and answer, collects both complete prediction files, and scores them against the original targets and five fixed references. It adds a viewer condition; it does not rename either of the existing programme conditions or modify their controller.

The neural observation is an exact table of processed spike counts. It is not a raw EEG waveform, a reconstructed spike raster, or a claim that a model has understood neural activity. No authentic packet, target, model or provider was run in constructing this component.

## Original task and information

The fixed public development task uses Haydn session 20161211 from the [Sohn–Jazayeri interval reproduction study](https://doi.org/10.1016/j.neuron.2019.06.012), released in [DANDI 000130](https://dandiarchive.org/dandiset/000130). All **748 training cases and 258 query cases** remain available in each view, in the source packet's original chronological order. All **40 held-in units** remain available in the neural view. There is no new trial, unit, outlier or target filter.

Each neural case contains four original 50 ms count bins, `[−200,−150)`, `[−150,−100)`, `[−100,−50)`, `[−50,0)` ms relative to observed Set. Set itself is excluded. The input is the original `uint32[4,40]` count matrix. The fixed 1400 × 820 RGB image prints all 160 integers and all 40 original unit IDs exactly, including the full uint32 range. Unit IDs and their order come from the original admitted `units.json`. No count normalization, clipping, interpolation, inferred spike timing, filtering or resampling occurs.

Both views retain case ID, condition, context, nominal sample interval and elapsed observation clock. Training observations additionally retain released `tp_ms` and the original five chronological fold labels. Query observations contain neither `tp_ms` nor a fold label. `context = condition // 5`; the nominal interval 800 ms occurs in both long and short prior conditions and does not substitute for the condition or context. Floating cue values use their exact emitted binary float values in JSON and their round-trippable decimal `repr` in the image.

The prediction is released behavioral **tp in milliseconds**, not Go minus Set. The cue-only view never loads a count member. Full query browsing and revisits are allowed, and session state persists across all queries. All training cases are available; the participant need not view every one. The broker requires each query to have been viewed before its answer and requires all 258 answers in the original query order. Each answer is immutable. Finite negative predictions are accepted without clipping, just as in the original validator.

A view starts with a fresh broker session. The instructions also require a fresh external participant context, no opposite-view observations or answers, no assessment feedback, and no fitting preprocessing or selection parameters on query rows. **The broker does not prove an external model complied with those instructions.** Source review or recorded JSON cannot establish external no-tools behavior, context reset, training-only fitting, absence of remembered public answers, or a matched scientific procedure. Participant transport and study budgets require separate qualification.

## Delivery, replay and grading

`viewer.py` authenticates the five original public files for a view against the accepted `provision_support/expected.json` pins before decoding any arrays. It reuses the unchanged `project.members` header, CRC, expanded-size and exact-member checks. It checks the complete counts/cues geometry and original condition/clock semantics. Pairing requires identical common NPY member hashes, identical original ordered query IDs and identical unit order across both views.

The typed actions are:

```json
{"op":"show_train","index":0}
{"op":"show_query","index":0}
{"op":"answer","case_id":"dmfc-000000","prediction_ms":850.0}
{"op":"finish"}
```

Indices refer to the complete source order, not condition rank. The example ID is illustrative; the actual ID must match the viewed next query. Show responses contain exact cue metadata plus a PNG, its byte hash and the decoded pixel-buffer hash. Counts appear in the image, not in a numerical-analysis response. No analysis, code execution, target lookup or filtering action exists. Invalid action errors in the CLI do not print source values, paths or parser payloads.

The operator journal records the source/runtime identities, file pins, complete ordered roster, actions and observation hashes. An answer event is flushed and `fsync`ed before acknowledgement or release of a later observation. A write failure ends that process without continuing. A failed session remains incomplete; it is not automatically retried or resumable. A complete receipt records all 258 answers and cumulative rendered PNG/RGB bytes, including revisits. These are render-byte counters, not model/provider/wire accounting. Base64, JSON framing, failed transport, model context/token cost and collection replay CPU are outside those counters.

Collection replays both complete histories against the same source packets and runtime metadata, including deterministic images. It emits one original two-member `case_id` / `prediction_ms` NPZ per view and validates each with the unchanged original prediction validator. The collection directory is fresh and mode 0700, and collected files are mode 0400: these are operator-custodied artifacts, not proof of a participant-readable isolated mount. File and ancestor symlinks, incomplete histories, changed images, wrong views/IDs, duplicate/reordered/missing answers and nonfinite predictions are refused.

Grading independently replays both complete histories, checks their canonical prediction bytes, validates both public NPZs and verifies the exact collection receipt **before calling any reference or private-target loader**. The CLI takes only an evaluator path locator before this boundary; it does not stat/hash/open the target operand until after public admission. It then authenticates the existing public identity, three frozen reference artifacts and private target packet, joins the exact IDs/conditions/contexts, and calls unchanged `metrics.score_candidate` for each view. Five fixed reference comparisons and all 40 condition / 8 context groups remain present. No new reference is fitted.

The primary arm metric remains trial-mean MAE in ms. RMSE, eight-context macro MAE and group MAEs are retained. The paired endpoint remains `mean(abs(cue − tp) − abs(neural − tp))`; positive means lower neural-view error on this finite panel, and zero or negative is valid. This route **explicitly binds the accepted `paired-arithmetic-v2`** exact-rational calculation of submitted binary64 values and its existing consistency checks. The old `paired.py` can erase small representable differences through intermediate rounding. The canonical four-cell runtime still has its previous binding; this component neither changes it nor retroactively changes old scores. The consistency envelope is not a scientific success threshold or uncertainty interval.

Scores identify the viewer pair, not `frozen_program` or `case_adaptive`. They do not establish causal tool-use effects, a matched method, native understanding, new SOTA, participant isolation or research readiness. This is one exposed public-development animal/session, with no population CI or p-value. In particular, one condition has a single original query; evaluator reference/group reports must remain outside participant context because they can reveal individual errors. All evaluator files and previous outputs require separate custody in a future study.

## Future operator commands

These commands describe an authorized future run. They were not run on authentic data during construction. Execute from the repository root with the approved existing Python/NumPy environment. There are no installed dependencies beyond NumPy and the standard library.

Create two separate operator input locators, each containing only its selected view and exactly five path keys. Use the already provisioned file paths or a separately approved exact-byte copy; the component does not download, convert or copy the original dataset.

```json
{
  "cue_only": {
    "train.npz": "/approved/cue/train.npz",
    "query.npz": "/approved/cue/query.npz",
    "schema.json": "/approved/cue/schema.json",
    "units.json": "/approved/common/units.json",
    "contract.json": "/approved/common/contract.json"
  }
}
```

Use a separate locator with the single `neural` key for that view. The paired operator locator contains both mappings. These paths belong to the operator; do not expose raw packet files to a purported restricted-viewer participant.

```sh
python -I -B benchmarks/neural/NEURAL-095/implementations/count-viewer-v1/viewer.py serve \
  --inputs cue-inputs.json --view cue_only --history cue-history.jsonl
python -I -B benchmarks/neural/NEURAL-095/implementations/count-viewer-v1/viewer.py serve \
  --inputs neural-inputs.json --view neural --history neural-history.jsonl
python -I -B benchmarks/neural/NEURAL-095/implementations/count-viewer-v1/viewer.py collect \
  --inputs paired-inputs.json --cue-history cue-history.jsonl --neural-history neural-history.jsonl \
  --out fresh-collection
python -I -B benchmarks/neural/NEURAL-095/implementations/count-viewer-v1/viewer.py grade \
  --inputs paired-inputs.json --cue-history cue-history.jsonl --neural-history neural-history.jsonl \
  --collection fresh-collection --evaluator-inputs evaluator-paths.json --out fresh-grade.json
```

`serve` accepts newline-delimited actions on stdin and writes JSON responses on stdout, including base64 PNGs. The evaluator locator must have exactly `public_identity.json`, `query_targets.npz`, `reference_grade.json`, `reference_commit.json`, `reference_audit.json` path keys. Grading is a separately authorized operator activity, never a participant action.

The broker bounds actions at 20,000 per view, input/journal lines at 16 KiB and the journal at 64 MiB. These bounds comfortably admit full 1,006-case browsing and all 258 answers; they are software refusal limits, not approved CPU/RAM/wall/wire/model budgets. This source does not enforce provider spend or an external process resource allocation. The complete future session, replay, repeated rendering, collection and grading costs must be planned prospectively. Full-panel authentic preparation and provider qualification remain unrun.

PNG compression uses the unchanged accepted NEURAL-077 Canvas/font pixels and local standard-library zlib level 6. Pixel hashes bind exact displayed content; PNG byte hashes can depend on the zlib build/runtime. Replay checks observed Python, NumPy and zlib version strings and exact source pins. Version strings do not pin binaries or a hermetic environment. Actual byte equality remains required; a differing build must be qualified rather than bypassing replay checks.

## Generated verification

Run through the authorized bounded test pool when available:

```sh
python -I -B benchmarks/neural/NEURAL-095/implementations/count-viewer-v1/test_viewer.py
```

`TEST_RESULTS.json` records the exact executed selectors and immutable receipt/log identities. Nineteen unique generated methods passed across 24 executions: 16 initial controls, then eight focused checks after the display/counter review, including three new methods. No failure occurred and no broad second suite was run.

Full-panel controls exercise every training/query projection, unrestricted browsing with ordered immutable answers, negative values, forbidden query-target/cue-count members, wrong condition/context/nominal relationships, input pins before decode, source/view/ID/image/history changes, original prediction validation, complete paired scoring with all five references, malformed final output before private access, exact v2 arithmetic, and durable journal failure behavior. Large history controls use a declared deterministic display substitute to avoid thousands of rasterizations. Separate actual-render controls validate all literal row/bin cells including uint32 max, PNG CRC/mode/dimensions, lossless decoded pixel equality to the unchanged Canvas, and actual PNG observations inside complete replayed histories.

All executed controls observed Python 3.12.8 / NumPy 2.2.6 and zlib build 1.2.11 / runtime 1.2.12. No other interpreter/NumPy combination is claimed passing. Three final generated images were 9,387–19,886 bytes versus 3,444,000 decoded RGB bytes; these are only observed generated examples, not authentic-data compression or full-study bandwidth measurements. Fixture accounting preserves the initial counter's omitted collection-write boundary with a conservative allowance and counts later writes explicitly. No authentic payload/label read, model inference, candidate fitting, Docker/provider run or scientific performance result is claimed.
