# Secondary ordinal metrics and paired participant uncertainty

The additive [ordinal-metrics-v2 evaluator](../implementations/ordinal-metrics-v2/README.md) supplies ordinal MAE, per-category recall, classwise calibration tables/ECE and paired participant-bootstrap intervals for original-arm RPS and MAE. It retains the exact original primary scorer and all original case/support rules.

The task does not uniquely specify these secondary decision, calibration or interval choices. A required hash-bound prospective policy makes them explicit. The [recommended profile](../implementations/ordinal-metrics-v2/RECOMMENDED_PROFILE.json) records a lower-median/equal-person/fixed-bin/paired-percentile recommendation, its rationale and alternatives; it is not an author protocol or scientific qualification. See the [strict interface](../implementations/ordinal-metrics-v2/INTERFACE.json) for complete input fields and the implementation guide for CLI and test commands.

All original 7,328 assessment slots, 171 recording records and 1,129 separate transitions remain required. Biological people are declared independently of recording names. A person without evaluable original support makes full-person MAE, calibration and paired intervals undefined. Category recall explicitly reports its narrower supported-person denominator. Original transformed-packet diagnostics remain unchanged and separate.

These are evaluator-side reports. Authentic source/clock/person identity, complete causal EEG packets, physiological reference competence, protected execution and independent scientific agreement remain required. Generated controls establish software behavior only; this extension adds no benchmark ID or model result.
