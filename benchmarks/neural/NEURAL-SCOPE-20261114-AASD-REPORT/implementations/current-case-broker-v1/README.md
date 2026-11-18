# AASD current-case observation broker

This component serves an existing normalized AASD packet and its complete stereo audio through a current-case API. It authenticates observation content against the private delivery binding, authenticates audio against the observation's digest, and commits each answer durably before advancing. The complete active and passive response set joins back to the unchanged initial evaluator.

It supports only the existing `tool_assisted` and `frozen_program` numerical modes. This is operator-side protocol construction. It is not a typed image viewer, direct-input arm, model runner, filesystem sandbox, fresh model context, authentic data preparation, or evidence of neural understanding. It adds no task and promotes no readiness claim.

## Operator integration

Import `aasd_broker.py` from this directory. The sibling observation-delivery and initial-evaluator source files are checked against their reviewed SHA256 identities before import. A future dependency change needs explicit review and rebinding.

```python
store = FileStore(public_root, "tool_assisted", max_artifact_bytes=admitted_size)
broker = Broker(inventory, private_binding, "tool_assisted", store,
                private_journal_path, max_actions_per_case=admitted_actions)
try:
    # The execution service relays only the following allowlisted messages.
    packet = broker.handle({"operation": "observe"})
    audio = broker.handle({"operation": "audio",
                           "resource_id": packet["audio_resource"]})
    broker.handle({"operation": "answer", "request_id": packet["request_id"],
                   "p_right": submitted_probability})
    # Repeat for every case. After participant termination is independently
    # established by the execution service, the operator may obtain predictions:
    predictions = broker.finish()
finally:
    broker.close()
```

The example illustrates one iteration, not a runnable model or scientific study. `inventory`, private binding, broker object, route metadata, journal, and export root must remain inaccessible to the participant. Pass only values returned by `handle`. Exposing the Python object would expose operator state and defeat this interface. `operator_route()` gives the operator the current participant/held-mixture cell; it is not an allowed participant request. Selection and freezing of correctly trained cell-specific models remains external and unqualified.

`observe` accepts no case identifier: only the current case is available. It returns the exact 256-sample common EEG content from the existing exporter, with the same target-relative alignment and full-waveform reference. `audio` accepts only that current reference and returns the complete authenticated waveform. It never fetches a neighboring case or arbitrary path. Returned objects are copies, so a client cannot mutate cached inputs. Repeated requests consume the declared per-case action allowance. At least three actions are required so observation, audio and answer are all possible; that minimum is an interface constraint, not a scientifically qualified resource budget. Authentic artifact-size and action budgets must be frozen before use and matched across conditions.

`answer` requires the current opaque request ID and a finite probability in `[0,1]`; booleans are rejected. The append-only-by-protocol journal is newly created with owner-only permissions and each record is flushed with `fsync` before advancing. A write/durability failure permanently invalidates that session, preserving the partial journal. Existing journal paths are never overwritten. Missing answers, including passive cases, cannot be converted into an altered denominator.

`finish` closes the journal, verifies saved bytes against committed responses, checks the ordered hash chain and reauthenticates the input artifacts, then uses the original delivery join. `replay_file` provides separate operator replay against the frozen inventory/binding. Hashes detect disagreement with the operator's saved inputs and records; they are not signatures against a malicious operator. An incomplete or oversized record fails closed.

## Boundaries that remain

Serving one case at a time does not erase a model's memory of earlier cases. A protected execution service must enforce fresh per-case participant state or another independently justified prevention of adjacent-window pooling. This component starts no process and cannot prove termination, network isolation, hidden-label isolation, cell-specific training provenance, or absence of cross-arm state. The service must establish those before scoring and must never mount the full packet tree for a candidate. The file adapter rejects path traversal and symlink artifacts, but does not claim protection against a malicious concurrent filesystem writer.

All existing AASD scientific limits remain: offline filtered EEG, behavioral report rather than true attention, native all-18 active/passive census, channel/event/audio alignment, three-fold stimulus-overlap census, source/stimulus rights, model baselines and motor/mixture controls. The source paper's reported accuracies are not comparison thresholds for this different common-context protocol. No authentic MAT/audio files, private labels, training, scoring campaign, model trial or new scientific result was used to construct this component.

## Generated controls

`tests/test_aasd_broker.py` exercises the real existing exporter in memory and the unchanged scorer, with all 1,260 nominal generated trial slots, 18 participants and 54 routed cells. Its deliberately short generated recordings produce 72 eligible cases, including 18 passive cases; these are software fixtures, not a reduced scientific cohort. Other controls cover exact EEG/audio preservation, private-field exclusion, current-only/cross-mode requests, omitted passive cases, artifact mutation, failed durability, immutable answers, bounded replay and complete coverage.

Run the focused standard-library tests through the project's existing generated-test pool. The integrator must enroll this new component and its test command; placing this directory does not itself establish CI enrollment. Local construction tests cannot establish scientific readiness.
