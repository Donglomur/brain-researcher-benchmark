# APCx typed spike-count viewer

This additive operator component supplies the typed count display and answer protocol missing from the deposited-label task. It consumes one already authenticated `apcx-one-public-session-v1` episode and produces an unchanged `apcx-candidate-session-result-v1` response for the existing complete-response assembler. It never opens a source dataset or owner target packet, fits a decoder, or computes a score.

This is **constructed, unadmitted source**. There is no participant process, provider connection, operating-system isolation or model result here. A host must enforce one session and one condition per fresh participant context. Giving a participant this Python object or its source episode would expose raw data; the intended participant interface is only `dispatch` replies with PNG images displayed as images. A rendering component alone does not establish native neural understanding.

## Scientific scope

The target remains the deposited `Total_pulse` integer, not authenticated physical odor delivery. The existing 43-session/three-mouse scope, 2,199 protected queries per condition, hash split, historical selection, 900 physically unresolved trials, and seven source limitations remain unchanged. The paper's 42-session count is not silently reconciled. There is no new task or readiness promotion.

Every retained unit and all 90 half-open 50-ms bins in `[0.5,5)` seconds remain accessible. The first 500 ms is unavailable, not a row of zeros. Images show **counts**, not inferred spike times or a fabricated within-bin raster. The column labels are bin start times in milliseconds; the reply supplies the exact half-open crop interval. Unit indices preserve the same complete order across calibration, development and queries.

The PNG renderer uses a fixed absolute grayscale function, `255 - min(224, 16 * count.bit_length())`, and visibly prints every exact integer count. It never normalizes to the current query, smooths, bins again, chooses units, or adds physical-command overlays. Saturated shades do not discard values because the exact count remains printed. The embedded bitmap font needs no installed fonts or image libraries. Full 90-bin views are wide; typed contiguous crops allow readable inspection of any part of the same evidence. No raster readability or model-viewer usability study has been run.

Calibration and development views are optional and retain their permitted deposited count and derived high/low labels. Query replies have no target, raw count matrix, pulse timing, reward, choice, animal/date identity or command diagnostic. Opaque case IDs and an index of every available case are preserved. This does not remove possible public-data contamination or signal fingerprints.

## Operator and participant interfaces

The sibling `../deposited-label/episode_boundary.py` is an unchanged required dependency. Its exact bytes and SHA-256 are checked before executing those same bytes. An operator may specify its directory with `boundary_directory`; that option is not a typed participant action. The episode's expected SHA-256 must come from the operator's prior authenticated preparation. A self-supplied hash is not source authenticity.

```python
from viewer import Session

# Operator only: use the existing strict input reader and frozen episode pin.
session = Session(episode, expected_episode_sha256)

# Participant-facing typed requests:
info = session.dispatch({"action": "describe"})
image = session.dispatch({
    "action": "view", "split": "queries", "case_id": query_id,
    "unit_start": 0, "unit_stop": info["unit_count"],
    "bin_start": 0, "bin_stop": 90,
})
# Host displays decoded image["png_base64"] as a PNG image.
session.dispatch({"action": "answer", "case_id": query_id, "count": 7.5})
# Repeat answers for every query, then:
finished = session.dispatch({"action": "finish"})
# Operator stores finished["response"] in the existing response-file location.
```

The only actions are `describe`, `view`, `answer` and `finish`, with closed schemas. Crops must be nonempty integer ranges within the selected episode. Labels cannot be requested from another split/session. Each query accepts one final finite numeric answer; booleans and nonfinite values are refused. Finite negative predictions are preserved for the existing scorer's later lower clipping. There is no upper clipping or rounding.

`finish` refuses missing queries and produces the existing seven-field response envelope with the original packet, episode, session and condition bindings. After successful finalization, every further action is refused. This is per-session completeness. The unchanged operator assembler still must require all 86 session-condition responses and both complete 2,199-query conditions before scoring; this module does not aggregate a successful subset.

The optional operator audit records a hash chain of successful requests and reply digests, without retaining repeated images. It is not an authenticated process transcript; rejected requests are not included. A real host must preserve both successful and rejected external exchanges, model/provider identity, resource limits, process closure and artifact commitments. Hashes alone cannot prove participant isolation or honest execution.

## Verification and remaining work

`test_viewer.py` uses generated data only. Twelve distinct controls cover real PNG decoding/CRC and fixed-scale pixels, all ten digits of maximum int32 counts, complete support availability, first-final responses, malformed actions and values, absent first-500-ms support, immutable episode copying, hash-chain consistency, source-pin refusal, and the unchanged complete-response assembler. The full generated integration fixture has 43 sessions, 383 session-unit pairs and 2,199 queries in each condition; support totals are 688/344 in `matched` and 6,482/2,150 in `full_calibration`. Only the assembler's file-to-JSON transport is replaced with generated in-memory responses. Ordinary response filenames and the original envelope/coverage checks still execute. No owner data, scientific arrays, fit or model call is used.

The first full-suite attempt had eleven passing checks and one fixture-path failure: macOS's temporary directory contained a symlink rejected by the existing ordinary-file guard. Resolving the generated fixture path fixed that check; the affected integration check alone was repeated. The failure is preserved in the private validation evidence. A generated cropped PNG was also rendered for visual inspection. These are software and rendering checks, not an authentic-data execution.

Run the generated controls from this component directory with Python 3.11 or later and `-I -S -B`. In the public layout the sibling source resolves automatically; private construction may set `APCX_BOUNDARY_DIRECTORY` to the unchanged sibling source directory. The intended CI entry is `python3 -I -S -B test_viewer.py` in this component, with the sibling included in its source closure. Integration enrollment has not occurred in this private proposal.

Remaining work is an externally enforced participant transport, full authenticated 86-episode engineering qualification on an admitted host, then a separately selected model study with the same information and compute conditions. None is implied by these generated checks.
