# NEURAL-077: complete numerical-waveform pair

`pair.py` connects the existing waveform transport, complete response collector
and protected paired scorer. It selects exactly these two conditions:

| Condition | Input for each of 400 fresh queries | Allowed participant behavior |
|---|---|---|
| `legacy_waveform_no_tools` | Original complete Cz/Pz numerical waveform and four demonstrations | Original no-tools instruction; a script is an engineering control, not proof of model compliance |
| `matched_waveform_programme` | Identical numerical data and demonstrations | Frozen candidate program may calculate within the restricted query process |

Only the existing permission sentence changes. Nothing is truncated, resampled,
pooled across queries, or replaced by the separate richer feature-bank condition
with 1,200 training labels. Target labels identify experimental target/standard
events. They do not label physiological P3 presence. The cohort is the same two
previously exposed development people, 200 queries each.

**The scoped provider-neutral implementation is complete and validated.** One
complete 400-query programme control and protected paired grade passed on the
selected macOS route, reusing the accepted no-tools control. Both fixed controls
returned balanced accuracy 0.5 and log loss 0.693147; paired differences were
zero. These values validate the software route, not AI performance. See
[AUTHENTIC_CONTROL.json](AUTHENTIC_CONTROL.json) and the exact
[operator provisioning requirements](PROVISIONING.md). The pair is one
benchmark with 400 unique cases, not two benchmarks or 800 independent cases.

## Selected source and dependencies

The eleven exact dependencies in `SOURCE_BINDINGS.json` are unchanged. All are
captured and authenticated before trusted imports. Nested original loaders
still reopen their own pinned source files; this is not a claim that every
dependency lookup uses only the first captured bytes. A changed source refuses
admission. The operator's `pair.py`, `bundle.py` and bindings also bind every
new arm and grading request.

There is no duplicate metric implementation. The evaluator calls the existing
`paired-condition-v1/compare.py::compare_submissions`, its canonical validator
and metrics, and the captured `registered-runtime/worker.py::references` with
only the two fixed reference paths translated. The original six references,
391-check lineage requirement, label dtype, exact case/ID joins and paired
balanced-accuracy/log-loss arithmetic remain intact.

The operator requires Python 3.11+ and NumPy; generated numerical controls used
Python 3.11.6/NumPy 1.26.3. Real participant execution selects the existing macOS
`sandbox-exec` transport and a framework Python under `/Library/Frameworks`.
No install or runtime replacement occurs. The source-only controls can run on
other hosts; they do not qualify that host's real transport.

## Freeze and execute a participant

A participant directory contains only declared top-level Python modules and
`config.json`. The manifest lives outside it:

```json
{"schema":"neural077_python_bundle_v1","entry_module":"main","modules":["helper.py","main.py"],"config":"config.json"}
```

`main.main()` consumes and emits the existing four-byte-length-prefixed protocol.
The existing `waveform-transport-v1/scripted_client.py` is a fixed 0.5 control
example. Configuration is available as recursively immutable
`neural077_config.CONFIG`. The freeze supports at most 32 modules, 512 KiB raw
source/config, 64 KiB config, and the transport's 1 MiB final client limit. Declared
modules are embedded and ordinary undeclared imports are rejected. There are
no package installs or undeclared third-party dependencies in this profile.

```sh
python -B pair.py freeze --root /absolute/participant \
  --manifest /absolute/manifest.json --output /absolute/FROZEN.json

python -B pair.py run --condition matched_waveform_programme \
  --delivery-root /absolute/authentic-delivery-v1 \
  --frozen-file /absolute/FROZEN.json --output /absolute/new-arm \
  --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
  --max-prompt-bytes 262144 --wall-seconds 3 --campaign-seconds 120
```

Freeze the complete bundle identity before any query exposure. Original source
and configuration are not reopened by the participant. Standard-library/OS
state is supplied by the selected external runtime; the frozen declaration is
not an attestation of the entire host or of arbitrary Python self-modification.
The executable itself is pinned before and after an arm. Each query starts a
fresh restricted process with no network, process-fork, other-query or private
file access. Existing collection checks every complete original prompt and
first response. A failed or incomplete run retains `FAILED.json` and cannot
produce an admitted arm. It is never automatically retried or resumed.

`--condition legacy_waveform_no_tools` selects the original instruction. A
Python script executing this condition does **not** demonstrate native LLM
understanding or enforce a remote model's no-tools policy. The existing provider
bridge remains an injected sender adapter, not a live qualified backend. Any
remote provider communication belongs in a separately reviewed trusted operator
broker, outside the restricted participant. No provider/API call is made here.

## Compare after both producers close

Provide the trusted evaluator a private locations file:

```json
{"schema":"neural077_pair_private_locations_v1","targets":{"development-001":"/absolute/targets-001.npz","development-002":"/absolute/targets-002.npz"},"reference_grade":"/absolute/grade.json","reference_commit":"/absolute/prediction_commit.json"}
```

```sh
python -B pair.py compare --delivery-root /absolute/authentic-delivery-v1 \
  --a /absolute/no-tools-arm --b /absolute/programme-arm \
  --private-locations /absolute/private-locations.json \
  --output /absolute/new-comparison --timeout 60
```

The parent authenticates operator-owned closed-arm records and dispatches a
fresh trusted evaluator process. That process never imports participant code.
Both captured submissions must pass the canonical public validator before it
even opens the private locations file. Then it authenticates both reference
records and finally loads exactly two original target arrays with preserved
dtype and IDs. The unchanged comparator independently validates both snapshots
again. Results contain aggregate metrics and reference comparisons, not labels.

This is a selected **trusted operator pair evaluator**, not the old registered
Docker worker and not inherited Docker runtime qualification. Arm receipts
belong in operator-owned immutable output directories. Their pins authenticate
that operator's previously completed collector; they are not self-authenticating
claims from an untrusted participant. A malicious trusted host is outside this
threat model. The original proof says direct children were reaped and macOS
forking was denied; it does not independently attest descendant absence.

For the narrowly specified engineering comparison, replace `--a` with
`--legacy-control /absolute/native-validation-v1`. This admits only the exact
previously accepted fixed 0.5 no-tools proof and submission. It neither reruns
the 400-query campaign nor replays its transcript audit. Historical costs and
limits remain attached to that proof. Arbitrary historical model runs cannot
use this shortcut.

## Evidence and remaining qualification

Construction controls cover 13 bundle methods and 9 new operator/driver methods.
They include isolated real frozen-client processes, generated 400-row canonical
comparison, malformed-B-before-private refusal, reference-lineage failure,
target-attempt accounting, no float-label coercion, source drift, condition
separation, frozen-client tampering and failed-collection refusal. The two
orchestration methods use explicit generated transport/dispatcher doubles;
they do not claim a real full 400-query sandbox campaign or fresh evaluator run.

```sh
python -B -m unittest discover -s tests -v
```

The new complete programme campaign and protected evaluator executed once on
source `5d9bf5dd800a3b922001a5d8d73ca803ae8c001b`, in 15.01 seconds. Independent
inspection checked all 400 saved deliveries and 38,382 assertions, including
closure, exact source/bundle/roster identities, two reference/two target attempts
after both public validations, and all six unchanged reference comparisons.
The old no-tools campaign was not replayed. There was no extraction, fit, model
or provider call. Earlier generated-check failures and one corrected reviewer
metadata assertion remain in the evidence history.

`control_validation.py` records the completed one-shot engineering protocol;
it is not a command to replay an accepted result routinely. Construction and
validation are complete for this named finite route. Selecting a live provider,
measuring model accuracy and qualifying its no-tools/context policy are later
study prerequisites, not reasons to relabel the delivered implementation absent.

Scientific difficulty, native understanding or tool-use claims need real
named-model runs under the chosen provider policy. The completed engineering
control introduces no scientific pass threshold, unseen-person inference,
SOTA claim or qualification of optional visual/adaptive conditions.
