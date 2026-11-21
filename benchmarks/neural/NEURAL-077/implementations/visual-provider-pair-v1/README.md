# Restricted visual provider and matched programme pair

This additive NEURAL-077 component connects the existing typed EEG viewer to a trusted image-capable provider client and compares its authenticated, complete first-final responses with the existing `matched_waveform_programme` arm. It preserves the original numerical provider/programme components and does not change the task's current default or readiness status.

The endpoint is the released ERP CORE **target versus standard stimulus identity**. It is not a physiological diagnosis of whether a P3 response is present. Both arms cover the same 400 trials from two previously exposed development participants: 200 trials per participant, with 40 targets and 160 standards. Four balanced training demonstrations are available in the visual condition; viewing them is optional. All 1,024 samples from Cz and Pz remain available through the original viewer. This does not establish generalization to unseen people.

`four_demo` is demonstration-assisted visual understanding through typed viewer actions. The programme sees numerical waveforms and the same four demonstrations. The comparison reports that the representations differ and that equal information has not been proved. The six existing references retain their original, richer training access; they are not relabeled as four-demonstration references.

## What is connected

- `transport.py` is an additive derivative of the original visual transport. Its only functional additions are an explicit trusted dependency root and a trusted child-launcher seam. The original viewer, strict actions, wire framing, image/frame journal, first-final lock, complete 400-session collector and transport audit are retained. Provider clients use `protocol_only`; this is not claimed to be the macOS participant sandbox.
- `visual_client.py` receives credentials, configuration and private custody through explicit inherited descriptors. It uses the unchanged original bounded HTTPS sender. Each query starts a new client process and a fresh local history. Every subsequent request repeats the complete history for that query, including prior images and exact rejected actions. Provider tools, server-side continuation and automatic history truncation are disabled in the request profile. Remote enforcement and capacity remain unqualified.
- `transfer_png.py` losslessly compresses the original viewer's fixed 1,400 × 820 RGB canvas for delivery. Original rendered files and transport bytes remain unchanged. Admission verifies original and delivered PNG hashes, IHDR, dimensions and exact decompressed zero-filter RGB scanlines. Zlib versions are recorded. A different compressed byte representation is acceptable only when the exact pixels remain equal.
- `provider_arm.py` authenticates every provider request, response, HTTP receipt, original frame, lossless image mapping, first final response and complete submission. It rejects missing/mixed/failed episodes, changed source, reused response identities, extra turns after final, altered probabilities and exceeded allocations. All 400 queries are mandatory; actual provider calls are counted across action turns rather than assumed to be 400.
- `protected_compare.py` retains the original protected public-validation/reference/target-loading/scoring logic, with explicit `four_demo` and `matched_waveform_programme` arguments at the actual comparator call. It does not change global numerical condition labels or relabel a score after computation. Both public predictions are admitted before private location files or targets are opened. The canonical validator also checks the visual submission's ZIP/NPY bounds before prediction arrays are materialized.

## Metrics and interpretation

The primary metric remains participant-macro balanced accuracy with threshold 0.5. Equal-participant log loss, paired differences and all six original reference comparisons remain unchanged. There are exactly two original private target loads. No population confidence interval, hypothesis test, new scientific pass threshold or SOTA claim is added.

A future successfully graded authentic run can report computed paired scores. The generated construction controls in this component are not such a run and do not establish native understanding, live model performance or scientific qualification.

## Finite execution and custody

The operator must choose and reserve query/campaign wall time, per-request bytes, cumulative query request/response bytes, and cumulative campaign request/response bytes before execution. The unchanged sender's request ceiling is **8 MiB**. Lossless compression often saves bytes but is not proof that a model or provider accepts the complete condition. If complete history exceeds a selected cap, the query and arm fail; images and history are never silently dropped or downsampled. A declared full query allocation must remain available before starting each new query.

There can be up to 127 provider actions after the initial viewer frame in each query. The original viewer's action/image/output bounds remain operative. The first well-formed finalize envelope is terminal even if its nested probability response is invalid. Failed and partial attempts remain unscoreable and have no automatic retry or resume.

Credentials never appear in command arguments or configuration. The unchanged sender prevents literal credential echoes in retained response bytes, and the visual client rejects decoded echoes before retaining successful action/metadata or forwarding actions. This is not a guarantee that arbitrary JSON-escaped credential text is absent from private raw failure evidence. Failed-send response costs use the selected bounded upper extent when retained bytes alone understate consumption. Private custody, failed responses and operator inputs are never public source artifacts.

The runtime requires the existing original public packet, all dependencies in `BASE_SOURCES.json`, the original matched programme arm, and protected target/reference operands. The integration host must qualify its own environment, image-capable provider and complete-condition capacity. No model/API run, original EEG read, container build or scientific fit was performed to construct this component.

## Commands

Run generated source controls from the repository root:

```sh
python -I -S -B -m unittest discover -s benchmarks/neural/NEURAL-077/implementations/visual-provider-pair-v1/tests -p 'test_visual*.py' -v
```

Tests use the installed sibling implementations by default. For an isolated source preparation, set `N077_IMPLEMENTATIONS_ROOT` to the authenticated original implementations directory. They use the unchanged sender with finite fake HTTP responses, synthetic pixels and explicit injected qualifications. They do not contact a provider or read the original signal packet.

`provider_arm.py run --help` lists the required explicit credential descriptor and allocations. `provider_arm.py compare --help` lists the trusted completed-arm and private-location inputs. These commands are implementation entrypoints, not a claim that the runtime or a provider has been qualified. Keep participant source execution outside the protected grading process.

## Source provenance

The original source closure was captured from repository commit `a5ae02906f7f35fceb94b115fb311ed44479ccd2`; the per-file identities in `BASE_SOURCES.json` are authoritative. `SOURCE_BINDINGS.json` preserves the original visual viewer dependency pins. No original source, dataset, protected label or historical receipt is replaced by this component.

## Participant process cleanup

The current transport observes child exit without reaping, using Darwin kqueue or
Linux pidfd. It keeps the session leader owned until its process group has been
signalled, then reaps that exact child. Later group-presence probes use signal 0;
they cannot terminate a reused process ID. Missing observer APIs or a nondefault SIGCHLD handler refuse the launch.
Kernel registration can still fail afterward; that failed session enters owned
cleanup and cannot be admitted. The trusted operator must retain exclusive
wait ownership and must not install native automatic child reaping.

The shared [process ownership helper](../../../../shared/viewer-process-ownership-v1/README.md)
records this cleanup order separately from group absence. A group signal does not
contain descendants that escaped the group; `protocol_only` remains a trusted
operator bridge, not a hostile-code sandbox. The macOS participant policy is
unchanged. Historical execution receipts remain evidence for their original
source identities and do not qualify this lifecycle revision.

## Full32 visual source extension (2026-11-20)

The explicit `erp-full32-visual-v1` source profile covers all 6,400 queries using the same four demonstrations and image-matched visual arms. See [the source and qualification contract](../image-matched-programme-v1/FULL32_VISUAL.md). The historical 400-query visual default and 6,400-query numerical default remain separate. This extension does not establish a completed visual study or native/provider qualification.
