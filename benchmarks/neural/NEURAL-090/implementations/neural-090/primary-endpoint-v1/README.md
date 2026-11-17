# Executable primary endpoint selection

The current NEURAL-090 contract ranks absolute candidate neural log loss separately in eight primary conditions. The prior report provides 348 means and contrasts, including candidate control-minus-neural gains that can increase when the candidate weakens its controls. `primary.py` implements the contract's ranking rule and retains those contrasts as unranked descriptive values.

Call `endpoints(complete_report)` after the original scorer closes the complete point report, or use:

```sh
python3 -I -S -B primary.py --report /operator/complete-report.json --output /operator/fresh-endpoints.json
```

The CLI reads a trusted operator-local report, rejects duplicate JSON fields and nonfinite JSON constants, validates the complete report before creating output, and refuses to overwrite an existing file. Keep authentic reports and endpoint outputs outside the repository. This component is not a participant submission parser or a replacement for original prediction admission, label custody or scoring.

The existing pinned `investigation-claims-v1/claims.py` validator checks all 76,800 invocation rows, all 1,200 person-seed vectors, all 120 ten-seed means, all 61,440 control contrasts and all 7,680 candidate-reference contrasts. It reconstructs means with equal chapter, person and seed weights. Even an omitted secondary or exposed arm prevents endpoint output. Its 1e-12 arithmetic tolerance is unchanged. The selector does not accept an isolated table of means or change probability smoothing, 39-class support, loss units, seeds, people, chapters or calibration budgets.

The eight primary identities are the two modes crossed with `held_chapter/full`, `held_chapter/1024`, `joint_person_held_chapter/0` and `joint_person_held_chapter/1024`. Lower loss in natural-log nats per prediction is better within the exact same identity. There is no overall scalar or cross-condition ranking. Each endpoint also reports independent-reference neural loss, reference-minus-candidate gain, and fixed-reference timing and shifted-neural contrasts separately. Negative gains are retained. Reference competence and independence require their original external qualification; this selector does not establish them.

All 348 original numerical claims remain available with units and `ranked: false`, including exposed-person, acoustic/transcript and candidate self-contrasts. Fixed-39 macro F1 remains descriptive. No confidence interval, significance, new-person/new-story population claim, threshold, or scientific qualification is added. This is still the fixed 32-person, two-chapter, ten-seed phoneme adaptation, not the published word-classification benchmark. One visit with two chapter blocks is not two independent visits.

The four access conditions remain distinct: this operator postprocessing component works with programme or tool-assisted reports; it delivers no direct-observation or typed-viewer participant transport. Mode names alone cannot establish a frozen versus adaptive policy difference.

Run `test_primary.py` through the shared lightweight test pool. Generated controls exercise complete support, unequal query counts, an attack that worsens candidate controls, a worse neural candidate whose self-gain nevertheless increases, missing exposed observations, malformed summaries, duplicate/nonfinite JSON, and complete CLI output with overwrite refusal. The fixtures are invented scalar reports. No authentic recordings, targets, model/provider calls or native scientific jobs are used.

Authentic 64-source preparation, canonical event/clock verification, complete native execution, reference qualification and scientific reasoning review remain unresolved. No task or access status is promoted. The historical scorer, validator, canonical definitions and existing source manifests are unchanged.
