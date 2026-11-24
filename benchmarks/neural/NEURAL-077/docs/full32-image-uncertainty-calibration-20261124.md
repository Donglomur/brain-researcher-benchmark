# Full32 fixed-view uncertainty-reference calibration

One fresh measured-budget operation completed the full 6,400-query diagnostic reference calibration. The earlier root-selected timing stop remains a separate unscored operation. Both use the same previously exposed 32-person population, 200 queries per person, and four fixed demonstrations. The full32 complement differs from the originally registered two-person, 400-query development condition and is not the entire 40-person collection.

| Operation | Fits | Capture attempts | Complete captured responses | Interrupted | Unattempted | Scored queries | Complete reference calibrations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Root timing stop | 1 | 2,123 | 2,122 | 1 | 4,277 | 0 | 0 |
| Fresh measured-budget calibration | 1 | 6,400 | 6,400 | 0 | 0 | 6,400 | 1 |

Each row is one engineering execution. Summed capture counts repeat the same cohort; they are not unique cases or additional benchmarks. The earlier [refusing-reference failures](full32-image-reference-calibration-20261124.md) remain separate historical records.

## Complete measured-budget result

| Reference or analytic comparator | Equal-person macro balanced accuracy | Equal-person macro natural-log loss |
| --- | ---: | ---: |
| Four-demo fixed-image uncertainty reference | 58.3203125% | 0.6361099286467982 |
| Analytic constant 0.5 | 50% | 0.6931471805599453 |
| Analytic constant 0.2 cohort prior | 50% | 0.5004024235381879 |

The reference's balanced-accuracy point estimate is above the 0.5 comparator. Its log loss is better than the uniform comparator and worse than the predeclared 0.2 prior. No sampling interval or competence threshold was evaluated. Constant 0.2 is an analytic cohort-prior diagnostic; that prior was never supplied to the image classifier. The [JSON report](full32-image-uncertainty-calibration-20261124.json) preserves the exact emitted floating-point aggregates, including balanced accuracy `0.5832031249999999`.

All 6,400 cases remain in the score denominator. There were 13 zero-shared-support cases and 6,387 positive-support cases; the mean shared-support fraction was 0.9744672403140983. Valid zero-support cases return probability 0.5 and are classified positive by the original threshold of at least 0.5. They are not omitted abstentions. The JSON retains full-population defined counts and mean coverage/shared weight for all 30 features, plus both baseline coverage means; these are aggregates, not case arrays.

The separately versioned method uses the fixed initial Cz/Pz gain20 view, without filtering or adaptive gain. Positive-support probabilities retain the predecessor arithmetic. The zero-support branch defines a response when the view lacks support; it does not recover clipped signal. Stored display units do not establish a hardware amplitude calibration. Scores retain equal-person aggregation and metric-only log-loss clipping at 1e-15. “Uncertainty reference” names the zero-support response policy, not a sampling uncertainty estimate.

The fresh operation reused no earlier captures or partial resume. Its frozen work allocation was 90 seconds for freeze, 4,200 for collection and 1,710 for evaluation: 6,000 seconds total, with a separate 600-second closure allowance. Observed stage times were 0.4777034169965191, 1,958.0717260419915 and 916.3021465000056 seconds, respectively. Native wall time was 2,875.059 seconds. All 6,400 capture receipts and all three outer stages closed; all 6,405 known process IDs were absent. No outer stage was forced to exit. Whole-run peak RSS was not measured and the declared CPU/RAM envelope was cooperative, not a hard OS quota.

Root settled the complete operation at a conservative inclusive charge of 256 MiB of artifacts and 10 GiB of named reads, including preparation, controller and closure bookkeeping. These charges do not measure syscall-complete I/O or retained disk size.

The closed source result asserts that all images, first responses, quality records and owned closures were admitted before protected scoring access. The custody basis is the exact source/result/contract bindings, reviewed evaluator ordering and closed owned receipts. The prediction child was restricted by the image-only protocol. This is not a kernel file-read census or a claim about every operator action.

## Preserved root timing stop

The earlier operation fitted once, retained 2,122 complete captured responses, interrupted one capture and left 4,277 queries unattempted. It never entered complete-arm evaluation and produced no scores or completed calibration. Captured responses are not admitted or scored benchmark cases.

Root stopped that operation after 2.2832334517236963 captures/s projected 2,813.35991702751 seconds for collection against the unchanged 2,400-second run allowance. Actual native wall time was 904.478 seconds. This was a prospective timing decision: no deadline overrun was observed. The downstream empty-response error followed the deliberate interruption and does not establish a spontaneous classifier defect. The native ledger remains failed. The later successful operation changes neither this historical outcome nor its frozen quote.

All 2,123 capture END receipts reconciled closed owned cleanup and streams. All 2,127 known process IDs were absent; outer stages closed without a forced outer-stage exit. Root's inclusive conservative charge was 128 MiB of artifacts and 3.25 GiB of named reads, including controller bookkeeping. These charges are not syscall-complete I/O measurements. Neither operation qualified escaped-descendant containment beyond its checked owned scopes.

## Exposure and interpretation

The population had prior image-pilot, aggregate, numerical-reference and clipping-diagnostic exposure. During a separate root metadata-hash lookup, an accidentally recursive search over the old materialization conservatively machine-read 33 protected JSON bodies totaling 756,023 bytes. It emitted no matches, label values or predictions. A global assertion that protected bodies were never read would be false. This is one associated disclosure, not a new search counted separately for each operation.

Root and the owner attest that the selected isolated target-last path remained unchanged. The complete scorer's admission assertion applies to that pipeline; it does not erase wider operator exposure or establish independent generalization.

This four-demo diagnostic reference is not an AI solver, established trained EEG competency baseline or human benchmark. It adds zero AI attempts and zero benchmarks. Its full-panel metric is not a paired comparison with the earlier 32-query direct-image pilot. No physiological P3-presence endpoint, native AI understanding, paper improvement, SOTA or general runtime readiness is qualified. Execution, fit, capture, scoring and completed reference-calibration counts remain separate.

The public JSON contains aggregate results and digest-only closed-result provenance. Images, raw arrays, labels, predictions, per-case and per-participant outputs, and private locators are excluded. Report hashes identify this transcription; they do not independently reproduce the original experiment.
