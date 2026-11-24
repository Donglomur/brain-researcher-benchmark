# APCx typed viewer JSON-lines bridge

This operator process exposes the existing typed count viewer over standard
input and output. Previously a host had to import and own its Python `Session`
object; the bridge supplies a usable local request/response channel. It reuses
the exact pinned `typed-count-viewer-v1/viewer.py` and that viewer's pinned
`deposited-label/episode_boundary.py`. No observer semantics, labels, support,
response envelope, split, cohort, metric, or numerical reference are changed.

The trusted host launches one process with one already authenticated public
session episode and the canonical episode hash from preparation:

```sh
python3 -I -S -B bridge.py --episode /operator/one-episode.json --episode-sha256 EPISODE_SHA256
```

The operator-only `--source-root` option selects an implementations directory
when source is staged elsewhere; it cannot bypass either source pin. Paths,
episode bytes, process handles, and source access stay on the operator side.
The participant receives only the standard-output replies and sends only the
typed request lines. Do not expose a shell, the episode path, the entire input
directory, or the Python process object as a participant tool.

Each request is one UTF-8 JSON object followed by a newline, at most 16,384
bytes including that newline. The existing actions are `describe`, `view`,
`answer`, and `finish`, with the exact schemas in the
[viewer documentation](../typed-count-viewer-v1/README.md). Replies are the
unchanged viewer objects, one JSON object per line, flushed immediately. A
host must decode `png_base64` and display it as a PNG image; exposing a JSON
string alone is not a visual observation. All 90 observed bins and every
retained unit remain accessible through the same complete views and crops.

Malformed JSON, duplicate keys, invalid UTF-8, unsupported actions, invalid
viewports, repeated answers, and incomplete `finish` requests return
`apcx-viewer-transport-error-v1` with `invalid_request`; the process remains
available without accepting an answer for that request. Arbitrary submitted
text and operator paths are not reflected in errors. An oversized request or
EOF before successful `finish` returns a transport error and exits with status
2. Bad operator inputs produce only an error on standard error and status 2,
before participant input is consumed. The host should preserve the full input,
output, standard-error, and process-exit transcript, including rejections.

Successful `finish` emits the original `apcx-viewer-finish-v1` reply and exits
with status 0. Its `response` member is the existing seven-field
`apcx-candidate-session-result-v1` object. Store that object at
`<condition>/<session_id>.json` for the original complete-response assembler.
This process completes one session only. The existing assembler and scorer
still require all 86 responses, every one of the 2,199 protected queries in
each condition, and both conditions before any complete task score.

This is constructed source, not an OS sandbox, external participant
controller, provider connection, or admitted runtime. A trusted host must
enforce the channel boundary and reset context, state, storage access, and
tool caches between sessions and conditions. The bridge launches no candidate
code, model, fit, score, network request, or extra process. It does not establish
native interpretation, direct-versus-tool comparability, or process isolation.
The deposited `Total_pulse` endpoint, complete 43-session release, historical
42-session discrepancy, seven physical-primary holds, and current scientific
readiness are unchanged.

Run the generated controls with `python3 -I -S -B test_bridge.py`. For a staged
source-only checkout, set `APCX_IMPLEMENTATIONS_ROOT` to the unchanged sibling
implementations directory. The controls exercise the actual `main` entrypoint
with real episode files and byte streams, complete first-final output,
decodable query/support PNG replies, visible recoverable refusals, source and
episode pins, target injection, incomplete EOF, and request bounds. A separate
generated CLI smoke uses the real interpreter/stdin/stdout path. Neither uses
authentic inputs or a model; passing does not qualify the scientific task.
