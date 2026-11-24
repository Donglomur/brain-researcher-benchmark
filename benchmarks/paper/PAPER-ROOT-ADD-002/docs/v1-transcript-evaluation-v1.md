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

## EEG grouping and retained contract lineage

The retained [improvement contract](../improvement.v1.json) labels its aggregation
field `verified`. That field is preserved byte-for-byte as part of the original
improvement lineage; it does not establish source-exact EEG grouping parity.
The current [reproduction contract](../reproduction.v1.json) marks aggregation
unresolved, and the [paired outcome protocols](../outcomes.v1.json) explicitly
retain the EEG grouping discrepancy for both reproduction and improvement.
This note clarifies that discrepancy; it does not replace the retained
machine-readable improvement contract or create a new policy successor.

The [pinned author export](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/scripts/extract_predictions.py#L42-L49)
recognizes `S<n>` participant tokens and otherwise returns `unknown`. Numeric
EEG participant tokens can therefore collapse into one group. Its subsequent
per-group sentence means and across-group mean would then weight those EEG
sentences equally, instead of weighting biological people equally when sentence
counts differ. The evaluator uses the panel's explicit biological-person map;
accepting that map does not authenticate the original EEG grouping.

The required endpoint remains sentence CER averaged within each biological
person, then equally across people, with EEG and MEG reported separately. Do not
admit an EEG same-task comparison until the original grouping is reconciled;
pooling everyone as `unknown` is not a substitute. Original cohort, sentence
split, neural-only baseline, preprocessing, protected execution and matched
information/resource conditions remain unresolved. No reproduction, improvement
or readiness result is established by this source clarification.
