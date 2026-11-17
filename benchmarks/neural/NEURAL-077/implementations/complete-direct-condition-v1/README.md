# Complete NEURAL-077 direct signal delivery

This source joins the existing full waveform condition to the registered
programme population, authenticates its numerical samples against the pinned
raw inputs, and admits only complete request-bound responses. It adds no task
ID, changes no score, and contains no recordings, labels or model responses.

The delivery has three conditions:

| Condition | Candidate information | Tools and independent unit |
| --- | --- | --- |
| `legacy_waveform_no_tools` | Same four labelled training demonstrations and one complete Cz/Pz query | No tools; fresh model context for each of all 400 queries |
| `matched_waveform_programme` | Exactly the same four demonstrations and query samples | Numerical tools/candidate code permitted; fresh process and no state from other queries |
| `ordinary_feature_programme` | All six training people's 1,200 labelled trials, fixed EEG/ocular/amplitude/history features; 400 unlabelled development trials | Frozen programme, separately executed for each development person |

The first two share the exact scientific instructions and numerical text; only
the tool-permission sentence changes. This is a matched-information delivery,
not an executed comparison. All three contain the same 400 development IDs,
200 from each of the same two previously exposed people. The richer feature
programme has a different representation and label budget; its result cannot
be interpreted as a tools-only effect. Training a feature classifier does not
establish native LLM signal understanding.

## Source and complete authentic coverage

`delivery.py build` reads only the exact five original public waveform members,
the eight public feature files in the registered asset manifest, and the four
raw signal files needed for two development people and the two demonstration
training people. It reads no private targets. Every input is byte/hash checked;
the raw arrays and features remain external dependencies. `SOURCE_BINDINGS.json`
binds the existing exporter, parser, validator and asset manifest to this route's
current dependency bytes without rewriting historical source manifests.

The builder joins all 400 query IDs to the feature packets, then independently
recomputes all 400 query waveforms and all four demonstrations from the pinned
33-channel float32 epochs. P9/P10 rereferencing promotes to float64 before
addition; Cz/Pz baseline subtraction uses exactly the first 256 samples. Every
supplied decimal must recover the exact recomputed float64 value; the four
training labels must match the public training assets. No sample selection,
rounding, interpolation, filtering, rejection, or class balancing is added.

The waveform representation retains 1,024 samples per channel at 1,024 Hz,
offsets -256 through 767. Its numerical class prior is not supplied. It is a
processed epoch in native EEGLAB amplitude units, not raw continuous voltage.
Physical display timing and independent amplitude calibration remain unresolved;
post-marker ocular, motor and other activity can be present. The feature route's
existing ocular, gross-amplitude, history, EEG+history and prevalence references
remain necessary comparisons. They cannot identify a specific P3 mechanism.

With an existing Python environment containing NumPy (materialization and native
controls checked with Python 3.12.8 / NumPy 2.2.6; standard-library controls also
checked with system Python 3.11), run from a trusted operator location:

```sh
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 delivery.py build \
  --packet /absolute/existing/erp-direct-signal-packet-002/packet/public \
  --asset-root /absolute/existing/asset-root \
  --output /absolute/trusted-parent/new-delivery
```

The asset root resolves exactly the paths in the pinned registered manifest;
there is no download, replacement-data option or production pin override.
Use trusted ordinary directories with no concurrent hostile writers. Collection
output and all of its ancestor paths must be unlinked, as required by the
existing NPZ validator (on macOS use the real `/private/var` temporary path,
not the `/var` alias). Input ancestor paths are operator-controlled; this is
not an adversarial filesystem sandbox.
Output is approximately 160 MB. Allow 2 GiB RAM and at most two numerical
threads; this command does not enforce OS resource isolation. A failed build
retains its partial directory; only a successful `COMPLETE.json` is completion.
Do not reuse an existing destination.

`public/` contains the five exact waveform packet members. Each waveform
condition's `contexts.jsonl` contains all 400 operator envelopes, each with
`ordinal`, `trial_id`, `context_sha256` and `prompt`. Deliver **only one `prompt`
string** to the candidate at a time. Do not provide the whole context file,
receipts, the auxiliary feature directory, other queries, source files or
operator identity metadata to a waveform candidate. A programme condition
must likewise receive one prompt through its independent process request.

The ordinary feature directory contains eight candidate-visible `features.npz`
files under their opaque case names. Six training cases include training labels;
the two development cases have none. Its labels and nuisance features must not
leak into either waveform condition.

## Complete response ingestion

The operator retains one envelope for **every attempted query**, including a
transport error. It must copy the request identity and context hash from the
dispatch record, and preserve the exact model-returned text in `response`:

```json
{"ordinal":0,"trial_id":"<request ID>","context_sha256":"<request prompt SHA256>","status":"ok","response":"{\"trial_id\":\"<request ID>\",\"target_probability\":0.25}","error":null}
```

For a failed request use `status: "error"`, `response: null`, and a string
`error`. That inventory is deliberately unscoreable. The collector requires
exactly 400 unique request ordinals and identities, no dropped requests or
replacement retries. It rejects missing/duplicate/foreign IDs, wrong condition
hashes, swapped response-body IDs, malformed scalars, nonfinite numbers,
booleans, duplicate fields, prose, extra keys, and failed requests.

```sh
python3 delivery.py collect \
  --delivery /absolute/new-delivery \
  --condition legacy_waveform_no_tools \
  --responses /absolute/complete-attempts.jsonl \
  --output /absolute/trusted-parent/new-admission
```

The collector reauthenticates the five original packet members and recomputes
all authoritative contexts. It does not trust an edited `COMPLETE.json` or an
edited exported context file. The request-bound hash must match the original
expected context for the selected condition. The raw attempt ledger is copied
before admission; invalid collections retain it and a `FAILED.json` receipt,
without a complete submission. Accepted collections produce the registered
two-array `submission.npz` (`trial_ids`, `target_probability`), validated by the
unchanged public scorer boundary. Both complete cases must pass before any
separate private grading. The collector never reads targets or scores.

The scorer remains equal-person balanced accuracy at the fixed 0.5 threshold,
with equal-person natural log loss secondary, all six registered fixed
references, and no scientific pass threshold. Waveform-specific matched
comparators still require their own prospective methods and execution evidence.
The ordinary feature references have a larger training budget than four demos.

## Enforcement and remaining limits

Context hashes bind bytes and claimed request identity; they cannot prove what
a service received or which tools it actually enabled. A real transport must
enforce fresh query contexts, no tools/retrieval/files for the direct arm, and
one fresh isolated process per query for the matched programme arm. This source
does not supply that transport. The separate per-person programme lifecycle
controller does not establish per-query waveform isolation. Shared-host file
access restrictions remain operator policy, not a security sandbox.
Ledger admission detects missing or repeated identities in the supplied records;
it cannot prove that an operator disclosed every earlier upstream attempt or
did not replace a failed request before handing over the ledger.

All contexts must fit the selected model without truncation. Existing original
waveform census reports roughly 72,024–77,878 prompt-text tokens per query;
service framing and the modified programme permission sentence need separate
capacity checking. No model or paid API was invoked to build this source.
Source tests and authentic materialization are not model results, hidden-test
qualification, scientific success or whole-task readiness.

Run generated software controls from the repository root:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1 \
  -p test_portable.py -v
python3 -I -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1 \
  -p test_native.py -v
```

The second command needs NumPy in the chosen interpreter's isolated import
path. The first uses only standard-library generated fixtures; the second
uses actual NumPy serialization and the existing validator on generated data.
Neither generated suite establishes authentic waveform identity. The separate
operator materialization receipt records that check without publishing its
input bodies or treating generated probabilities as a solver trial.
