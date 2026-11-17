# Current V1 transcript evaluator

The [V1 evaluator](../implementations/v1-transcript-evaluation-v1/README.md)
provides the pinned presented-sentence export metric for an independently frozen
complete assessment panel. It checks all declared test cases and ordered input
keystrokes, known MEG aliases, source recording identity, the selected split
condition and fixed output vocabulary. It reports literal CER/WER with equal-person
aggregation and explicit undefined support.

This is source construction for the existing task, not a new benchmark or a
completed paper reproduction. The original source split is by sentence cluster;
person-held-out and variable-length transcript conditions are separately declared
prospective designs. V2, online typed-target CER and final language-model rescoring
are not silently substituted for this endpoint.

The [implementation guide](../implementations/v1-transcript-evaluation-v1/README.md)
documents exact inputs, commands, resource bounds, output semantics, generated
controls, source provenance and remaining scientific requirements. Canonical task
definitions and historical source records remain unchanged. No authentic data,
decoder, paid model or native scientific campaign was run for this component.
