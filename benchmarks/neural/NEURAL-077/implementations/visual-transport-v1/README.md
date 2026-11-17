# Restricted NEURAL-077 image transport

This operator runner connects the existing ERP image viewer to a participant
over two anonymous pipes. The participant receives a prompt, a typed action
schema, allowed view metadata and **raw PNG bytes**. Its only accepted messages
are the existing viewer actions. Each query starts a new participant process,
with a new empty working directory and a new episode identifier. The runner
does not read query targets, score responses, call a model, or fit parameters.

This is human ERP target-stimulus classification. It is not mouse seizure
detection. A scripted client consuming images and returning a fixed scalar is
a software control, not evidence of neural interpretation or model accuracy.
The packet is the same previously exposed 400-query development population.

## Operator commands

The server uses an existing Python environment containing NumPy, needed by the
unchanged authenticated packet loader/NPZ validator. The participant example
uses only the standard library. All paths below are supplied by the trusted
operator; none is a participant action or returned field.

```sh
SERVER_PYTHON -I -B transport.py episode \
  --packet /absolute/authenticated/public \
  --ordinal 0 --mode zero_shot --output /absolute/operator/new-session \
  --client /absolute/visual-transport-v1/scripted_client.py \
  --python /absolute/system/python3 --sandbox macos
```

`campaign` takes the same options except `--ordinal`. It authenticates the full
packet once, creates a new output root, and attempts each ordinal 0..399 exactly
once, sequentially, retaining failures. It has no retry, resume, best-of or
response replacement. A failed episode does not become a successful one by
continuing the campaign. Collect a complete campaign with:

```sh
SERVER_PYTHON -I -B transport.py collect \
  --packet /absolute/authenticated/public --mode zero_shot \
  --sessions /absolute/operator/all-sessions \
  --output /absolute/operator/new-admission
```

Collection checks every transport message against the existing viewer's
replayed action/frame/final audit, then calls its unchanged complete400
collector. That collector alone parses scalar answers, assembles the original
NPZ layout, and calls the registered validator. Missing, failed, invalid,
mixed-condition, mixed-client/limit/sandbox configuration or altered sessions cannot produce a transport-qualified
collection. `TRANSPORT_COMPLETE.json` means complete unscored software
collection; it does not mean a qualified model/provider, test population or
scientific result. Scoring stays in the existing trusted operator route.

## Wire contract and complete capture

Each message is an 8-byte prefix of two unsigned network-order 32-bit lengths,
followed by UTF-8 JSON and then optional PNG bytes. The lengths are JSON bytes
and PNG bytes. Participant messages must declare zero PNG bytes and 1..8,192
JSON bytes. They contain one exact existing viewer action object, with no
wrapper or arbitrary method name. Duplicate keys, malformed UTF-8, nonfinite
numbers, extra fields, invalid parameters and undeclared actions are rejected
by the existing viewer. They consume an action when their framing is valid.

The first operator frame has `status: ready`, the current `trial_id`, an opaque
episode identifier, scientific prompt, action schema, explicit limits and the
initial view metadata. Its PNG is the initial unlabelled query image. Other
nonterminal frames have `rendered` or `rejected` status; terminal frames have
`valid_unscored`, `invalid_response` or `closed` status. There are no packet
paths/hashes, output paths, exceptions, process receipts, numerical samples,
query labels, scores or other-query identities in these projections. A
demonstration target is returned only while displaying that demonstration in
`four_demo`. The ready schema lists all actions; demo selection is rejected in
`zero_shot`. Labels and feedback never carry across episodes.

Every complete frame accepted from the participant and every complete frame
written to its pipe is retained byte-for-byte in `transport/`, including the
initial prompt/schema/image and final acknowledgment. Each direction is bound
to a sequence/hash chain. Viewer requests, deterministic images and immutable
final response remain in the original viewer artifacts. The transport auditor
checks their correspondence, exact projections, counts and bytes. Terminal
capture is still the **first** well-formed `finalize` envelope, even when its
answer is invalid. The connection closes immediately after its acknowledgment;
no second answer is admitted. The client must then exit successfully within
two seconds (and within its episode deadline); its exit code and any forced
stop are recorded. A client failure after final capture fails transport
admission without changing that first answer. Bytes queued after closure are not read, accepted
or claimed to have been captured.

An oversized/invalid frame is rejected from its 8-byte header without reading
or allocating its declared payload. A truncated frame or timed-out input has
only the exact bytes read recorded as incomplete. A broken output pipe records
only bytes successfully written. These are failed episodes, not complete
capture claims. Successful pipe writes prove bytes reached the local OS pipe,
not that a remote provider consumed them. Hash chains are integrity checks,
not protection against a privileged operator rewriting all artifacts.

## Enforced episode limits

Defaults are 128 actions including initial overview and final, 32 images,
128 MiB of total outbound framing/JSON/PNG, and 300 seconds wall time. Operators
may choose stricter limits using `--max-actions`, `--max-images`,
`--max-output-bytes`, and `--wall-seconds`. The frozen values accompany the
initial input and operator manifest. There is no silent truncation, image
summary, retry or cross-query cache. Invalid bounded requests consume actions.
A denied capacity request terminates the episode without a submitted answer;
the participant can finalize after the last permitted image while action
capacity remains. The byte check conservatively reserves the maximum next
frame plus terminal allowance before rendering. A deadline or EOF fails the
episode, including a final that could not be acknowledged.

PNG dimensions remain 1,400×820 and roughly 3.45 MB. Default maximum outbound
data is a byte bound, **not a model token/context guarantee**. A real provider
must establish that its per-image dimensions/size, cumulative images and text,
context length, image preprocessing, tool formats, output limits and timeout
fit the frozen condition. No provider capacity was measured here.

## What isolation is actually implemented

`--sandbox macos` uses the real system `sandbox-exec` executable. The client
receives only stdin/stdout pipes, no other inherited file descriptors, a
minimal locale-only environment, and a fresh empty cwd. The profile denies
operations by default, with explicit denial of network operations, process
forking, process inspection of other processes and general sysctl operations;
it allows reads of the exact client script and system Python runtime locations
(`/System`, `/usr`, `/Library/Frameworks`, the root directory entry and selected
random/null devices), its own process information and five named OS identity
sysctl reads. File metadata remains available. Operator packets and
session paths under ordinary user directories are not on that read allowlist.
The sandbox's broad runtime locations must not contain operator secrets. Use
a system interpreter within those locations; a private virtualenv is not
automatically made participant-readable.

The test suite actually launches this client boundary on macOS and requires
denied operator-file reads/writes, network access, child-process launch,
parent argv/environment inspection through `KERN_PROCARGS2`, and absence of
inherited secret environment variables. An early allow-default profile leaked
the parent environment through that sysctl despite sanitizing the child's
environment; the deployed deny-default profile and explicit sysctl denial
repair that observed counterexample. The exact profile bytes are hashed in the
episode manifest and checked on collection. That is an observed local
scripted-client sandbox result, not a claim of adversarial OS security. The
trusted runner, source loader and renderer remain outside the sandbox and
hold processed arrays. macOS and the trusted operator are in the trust base.
No sandbox server/renderer is mislabeled as a sandboxed participant.

`--sandbox protocol_only` provides only separate-process and protocol
restriction; the client can use its host OS privileges. It is useful when a
trusted provider bridge runs elsewhere, but **does not qualify visual-only
participant isolation on a shared unrestricted filesystem**. A real provider
integration must expose only this action tool, deliver PNG as image content
rather than base64 prose, start a genuinely new model context per query,
disable memory/retrieval/code/file tools, prevent previous-query feedback,
and retain actual provider input/result evidence. A new local bridge process
alone cannot prove any remote-context policy. The default macOS sandbox also
denies network, so this local proof cannot be relabeled as a remote API run.

Neither mode implements parameter learning, sequential feedback, adaptive
training examples or a population prior. `zero_shot` and `four_demo` retain
the original viewer definitions; representation and processing permissions
remain different from the waveform/programme conditions.

## Verification

```sh
python3 -I -S -B -m unittest discover -s . -p test_transport.py -v
```

Tests use explicitly invented signal fixtures for transport controls. They
exercise actual child processes, malformed requests, real capacity/time/EOF
failures, immutable invalid finals, demonstration separation, exact PNG
capture, altered/missing transcript rejection and macOS sandbox denials.
`scripted_client.py` is a runnable provider-neutral framing example that
consumes the initial PNG and always submits 0.5. Use `campaign` followed by
`collect` with an authenticated existing public packet for the actual full400
engineering path. Authentic images, responses, submissions, sandbox probes
containing local paths and evidence directories belong outside public Git.
