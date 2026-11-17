# Cross-cohort seizure investigation: source package

This package implements the proposed NEURAL-012 investigation across CHB-MIT and Siena EEG. It is construction source, with no validated benchmark results or qualified execution environment. All 12 qualification gates remain open; generic `neurobench run` and `score` remain disabled.

The task retains all 686 CHB-MIT recordings and 41 Siena recordings, 37 declared people, four analysis arms, 96 logical jobs, 192 fit/predict invocations and 2,908 recording-arm outputs. It tests transfer of a detector trained on CHB-MIT to Siena while separating signal, preprocessing and timing effects. The original source audit keeps every held person's recordings together. Declared person counts require biological adjudication; chb01/chb21 identity is explicitly unresolved in the gate list.

From the repository root, inspect the source without reading EEG data or importing scientific modules:

```sh
python3 -I -B benchmarks/neuroscience/neural-012/central_operator.py inspect
```

The typed `HostRuntime` interface in [OPERATOR_CONTRACT.json](OPERATOR_CONTRACT.json) connects complete selection planning, independently copied signal staging, original source validation, private target construction, the complete campaign and original postprediction target release. It has no serialized-receipt-to-owner factory. The inspection command does not execute that scientific workflow.

[CURRENT_SPECIFICATION.json](CURRENT_SPECIFICATION.json) states the selected clocks, montage, target, fitting and comparison rules. [Participant instructions](runtime/source/neural012/public/TASK.md) define the candidate's inputs. Modules under `private/` are trusted-host implementation source, not answer data: original source maps, target values, preparation keys and owner capabilities are not distributed to candidates.

Both Siena clock discrepancies remain unresolved. The prospective EDF-origin clock condition is conditional on authentic adjudication. Retrospective whole-record processing and unlabeled query transduction are allowed, so this is not an online detector or a clinical validation. Reconstruction of analysis quantities and detector performance are separate outcomes.

Read [QUALIFICATION_GATES.json](QUALIFICATION_GATES.json) for the outstanding source, physical montage, clock, native runtime, target isolation, complete campaign, scoring and scientific interpretation requirements. Source checks establish no SOTA result. [PUBLICATION_SCOPE.md](PUBLICATION_SCOPE.md) explains the public projection, its unchanged executable roles and excluded inputs. No local private history or canonical acquisition notes are published.
