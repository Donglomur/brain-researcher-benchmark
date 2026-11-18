# Helsinki causal EEG raster adapter

This source component presents one existing, hash-bound `NEURAL-EXP-005`
30-second EEG packet as PNG waveform pages and collects one final probability.
It fills a representation gap between the existing causal packet API and a
future isolated participant transport. It does not run an agent or qualify the
task, its dataset, a baseline, or native neural understanding.

The operator supplies both the unchanged public packet and the protected
expected case binding from `Reference.case_rows()`. The adapter checks all fields,
the original ordered 18-channel montage, the exact rational sample clock, all
30 original quality flags, every finite sample and the protected full-input hash.
It authenticates the sibling `complete-support-evaluator/protocol.py` source by
its pinned SHA-256. The existing protocol and infant-macro Brier scorer are
unchanged. A source hash is not dataset or clinical validation.

## Operator API

Keep the session, packet, Python process, expected binding and underlying files
outside participant access. Only allowlisted action responses cross the future
transport boundary:

```python
from viewer import Session

session = Session(public_packet, expected_case_binding)
description = session.act({"action": "describe"})
frame = session.act({
    "action": "view", "start_sample": 7168, "stop_sample": 7680,
    "channels": [0, 1, 2, 3, 4, 5], "units_per_division": 25,
})
# Deliver frame["png_base64"] as an image/png image, plus its small metadata.
receipt = session.act({
    "action": "answer", "case_id": description["binding"]["case_id"],
    "input_sha256": description["binding"]["input_sha256"],
    "probability": 0.3,
})
prediction = session.finish()  # Trusted collector only: existing scorer row.
```

Each frame contains at most 512 consecutive original samples and six selected
original channels. All samples and all 18 channels remain addressable; pages
are views, not exclusions from the case or scientific denominator. At the
admitted source rate of 256 Hz, a full packet has 7,680 samples per channel.
The interface also retains the existing protocol's rational clock and phase
without resampling. Time labels are exact tick fractions relative to the packet;
they do not assert a verified physical/clinical acquisition clock.

The graph joins consecutive native samples with straight pixel lines. It does
not filter, normalize, infer missing values, or convert units. Zero is fixed at
each channel's central line; the requested positive scale determines units per
vertical division. Values outside two divisions are clipped for display, with
red endpoint markers and per-channel clipped-sample counts. The participant may
change the scale. Pixel quantization and gain clipping are representation
limitations: sample reachability does not establish information equivalence to
numeric input or sufficient clinical/model readability.

All 30 input quality flags remain visible in the header; the scored final
interval `[29,30)` is shaded where present in the selected page. Flags mean
original-input quality indicators, not proven pauses or missingness. A flag
never removes a sample, case, label or infant. EEG arrays, labels, absolute
recording offsets, source filenames and neighboring cases are not returned.
PNG files contain only image chunks, with no embedded waveform text.

`answer` accepts a finite probability in `[0,1]` under the exact case and input
binding. It closes the session to further actions; no revisions or partial
scores are provided. `finish()` requires that answer and returns the complete
binding plus probability for the existing evaluator. The operator must collect
every required case in its original frozen order. One successful session is not
evidence of complete 79-infant/400,534-case execution.

## Checks and integration

Generated tests exercise the real existing packet constructor and scorer,
rational phase, full original channel/sample addressability, actual PNG pixels,
quality flags, clipping and gain, mutation isolation, malformed/extra fields,
future/out-of-range requests and first-final probability semantics. A complete
79-recording invented fixture checks unchanged scorer compatibility and missing
prediction refusal. No authentic EEG, annotations or fitted model are used.

From the repository root, the focused test command is:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-EXP-005/implementations/typed-raster-viewer-v1 -p 'test_*.py' -v
```

The component requires explicit registration and CI enrollment by the shared
integrator. This private construction does not modify central manifests or
the task's `not_delivered`/scientifically unqualified status.

Fresh participant processes and enforced filesystem/network isolation remain
external requirements. Passing the session's Python object or interpreter to a
participant would expose its private packet. This component supplies no such
sandbox, participant transport, training-artifact delivery or model trial.
Complete authentic source custody/preparation, calibrated quality flags,
competent train-only seizure comparators, complete required controls and
representation/readability validation are also outstanding. The target remains
three-expert seizure-report fraction, not unique clinical seizure truth. Public
annotations prevent an unseen-pretraining claim from local folds alone.
