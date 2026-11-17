# Image/action provider seam

This additive operator-side component connects the existing NEURAL-007 and
NEURAL-077 viewer frame formats to an **injected** Responses-style image sender.
It contains no HTTP client, credentials, SDK, model, dataset loader, renderer or
score. Its controls use generated in-memory frames and fake senders only.

The route is direct interpretation **through a restricted waveform viewer**:
models receive PNGs and the viewer's allowed scalar metadata, then choose typed
viewer actions. They do not receive raw arrays or Python/file access and cannot
build a detector here. Tool/program construction remains a separate benchmark
condition. A viewer adapter and a successful scripted transport do not establish
native neural understanding, model accuracy, scientific readiness or a matched
effect of tool use.

## Supported source policies and an explicit capacity hold

* NEURAL-007 uses the original `whole_person_raw_viewer_zero_shot` policy: one
  persistent person session; complete three-channel target views before first
  accepted epoch answers; no replacement answers; finish only after every epoch.
  Its two original development people remain 2,780 and 2,670 epochs (5,450 total).
* NEURAL-077 uses the original `zero_shot` or `four_demo` viewer policy: a fresh
  query session, initial query image, typed navigation, and the first valid
  `finalize` action closes the session even if its inner scalar response is
  invalid. `invalid_response` is a terminal invalid answer, not a successful
  prediction. Only `four_demo` can expose the four permitted training labels.

The implemented memory policy is `full_visible_transcript_no_hidden_reasoning`.
Every prior observation and assistant action text is resent, in order, without
truncation, summarization, selective retention, image resizing or retries. A
response containing reasoning items is refused: this implementation does not
silently discard hidden state or claim full provider-state continuity. Provider
annotations or other extra message state are not accepted as conversation memory.
This excludes many reasoning-model response formats. Internal reasoning is
allowed in native interpretation and is not an external analysis tool; this
restriction describes the current adapter's compatibility, not a scientific ban.

As checked in the official [image input documentation](https://developers.openai.com/api/docs/guides/images-vision),
the request image limit is 1,500 (and the documented payload ceiling is 512 MB).
This is a **per-request limit**, not a claim about total-session or server-context
capacity. A full visible image history for either original sleep person exceeds
it. Therefore this exact mapping rejects either canonical person immediately
after authenticating its ready frame, **before any provider send**. Generated
two-epoch controls exercise the plumbing without weakening the public roster.
No full-person provider execution is qualified. Bounded EEG episodes can pass
these structural limits, but still require actual endpoint and context
qualification.

## Separate prospective sleep memory condition

`whole_person_raw_viewer_last32_turns_zero_shot_v1` is a separately authorized
**source-only, prospective delivery condition**, not adoption into the canonical
benchmark. It changes model-visible memory and must never be pooled with the
full-history condition as though information access were matched.

The complete original ready/instruction contract remains immutable in every
request. Before each request the deterministic rolling buffer contains at most
31 complete `(observation, assistant action)` turns plus the current observation.
After one response, that current pair becomes complete. Before appending a new
observation to 32 completed turns, only the oldest complete turn is removed.
The initial instruction-only action counts as one turn without duplicating its
instructions in an observation. All turns count, including non-image response
acknowledgments. Thus a request contains at most 32 observations/PNGs, never
32 completed turns plus a 33rd pending observation.

The source requires `Budget.max_images=32` for this condition. The other byte,
token, output, total-exchange, turn, wall-time and explicit image-detail budgets
must be selected and serialized in the ready receipt before any outcomes. No
successful generated control establishes a feasible real-provider budget. Token
or byte overflow refuses the exchange; it never evicts additional turns.

This is still one persistent original viewer session per person, covering all
2,780/2,670 epochs with the same first-valid answers and complete-person finish.
The original viewer's accepted-answer and seen-epoch sets persist outside the
model transcript; they are not supplied as extra memory. Collectors and scoring
are unchanged. All private attempted request/response bodies and exact original
wire journals remain retained even when model-visible turns are evicted.

No generated summaries, selective retention, automatic transcript retrieval,
saved-answer restoration, remote hidden state or cross-person memory is added.
The original explicit epoch/window actions may request a previously viewed
signal region again; that is a new ordinary observation, not automatic history
restoration. No epoch is split into an independent model session. Both people
use the same declared policy. This condition is not a native-performance result,
a matched effect of tool use, a provider capacity proof or scientific readiness.

## Operator API

Load `provider.py` from this directory using `importlib` (the checkout must include
the pinned task source closure). Construct one `Bridge` per fresh task session:

```python
bridge = Bridge(
    task="NEURAL-077", condition="zero_shot", model=explicit_model,
    budget=Budget(
        max_turns=127, max_images=32,
        max_history_bytes=history_bytes, max_request_bytes=request_bytes,
        max_response_bytes=response_bytes,
        max_total_provider_bytes=total_request_and_response_bytes,
        context_tokens=context_tokens, output_tokens=output_tokens,
        wall_seconds=wall_seconds, image_detail="original",
    ),
    send_json=send_json, input_token_bound=input_token_bound, record=record,
)
terminal_header = bridge.serve(binary_input, binary_output)
```

Every budget is explicit. This is an API example, not a frozen feasible provider
budget or an executable authenticated client. The operator supplies:

* `send_json(request_bytes, absolute_monotonic_deadline) -> response_bytes`:
  exactly one bounded exchange, no internal retries, HTTP/header/credential data
  excluded from the returned body. It must enforce deadline and response-byte
  limits while reading, before allocating an oversized body.
* `input_token_bound(request_bytes, absolute_monotonic_deadline) -> int`: a
  conservative complete-input upper bound including every image, the action
  schema and message overhead. A fake or heuristic bound is not provider context
  qualification. Actual reported usage must not exceed the bound or declared
  output/context allowances.
* `record(metadata, exact_request_bytes_or_none, exact_response_bytes_or_none)`:
  durable private retention or an exception. Each attempted exchange is recorded
  before any action is emitted. Separate events distinguish a prepared action
  from emission and the original viewer's acknowledgment. Metadata includes
  body/frame/text hashes, turn/episode, usage, retry count zero and a hash chain.
  A failing receipt sink withholds the action. Callback exception text is never
  exposed or persisted because it may contain secrets.

The original `!II` JSON-length/PNG-length framing is reused. Exact PNG bytes
become `input_image` data URLs, alongside `input_text` scalar projections; they
are not merely encoded into text. The model returns a strict root object with
`viewer_action`; the wrapper is removed and the existing typed action is framed
for the original operator. The original viewer and collectors remain final
authorities and retain their exact wire journals; bridge frame hashes bind to
those journals. Both provider text and emitted action bytes are identified.

The [Responses request reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
and [structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs)
support this request shape: root object with nested action alternatives,
`tools=[]`, `tool_choice="none"`, `store=false`, `stream=false`,
`background=false`, and `truncation="disabled"`. No previous response ID or
conversation is used. Unsupported model/schema/image-detail settings fail; no
fallback is attempted. The selected model identifier must match the response.
These source settings do not prove provider compliance or image consumption.
They preserve input PNG bytes at this seam, not provider-side pixel resolution:
the selected model may apply its own image preprocessing even at `original`.

## Boundary and verification limits

This is a trusted operator-side seam: imports reuse pinned codec, prompt,
transition and probability contracts; no packet/source methods are invoked.
Sleep probability validation uses the existing NumPy dependency. Python 3.11
and the complete source closure are needed. No task source, private filesystem
path, raw signal array or query target is placed in a provider request.

The current viewer participant process is network-denying and its sandbox is
unchanged. This module does not bypass that boundary or supply a network broker.
A future execution protocol must qualify broker placement, endpoint identity,
fresh remote context, image handling/capacity, token bounds, private receipt
storage and actual model behavior. Single-use Bridge objects enforce local
session separation only. The synchronous injected callbacks and streams must
enforce deadlines externally; source checks cannot preempt blocking I/O.

Per-turn/request/response/history/image/token/wall limits fail explicitly, with
fixed failure-stage codes in private receipts and no callback exception text. The
cumulative byte budget reserves the maximum response before sending, including
the repeated image history in every request. No shorter session is reported as
a completed sleep person. A capacity rejection or invalid answer is not a score.
Historical `f1dea1ee` scripted execution, its preserved startup failure and the
public `SCRIPTED_CONTROL.json` remain unchanged and do not qualify this adapter.

Run generated controls from the checkout with the existing environment:

```text
python3.11 -I -B benchmarks/neural/NEURAL-007/implementations/viewer-provider-v1/test_provider.py
```

Repository operators must use their admitted shared test pool. No real provider,
authentic image, raw dataset, model, scoring, rendering or installation is part
of these controls.
