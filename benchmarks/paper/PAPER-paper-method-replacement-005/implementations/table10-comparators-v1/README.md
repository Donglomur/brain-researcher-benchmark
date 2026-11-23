# Original Table 10 decoder comparators

The existing NEDS export bridge requires all five encoding masks and all four
decoding targets for both paired methods. It cannot represent the original
Table 10 decoder-only comparators. This additive operator component scores the
actual RRR, NDT2 and POYO+ cells without assigning them invented encoding outputs.

`evaluate_panel` retains the unchanged full 84-session paired NEDS/candidate
evaluation, including all nine endpoints, and adds four decoding endpoints for
each of the three comparators on every original held-out session. The existing
74-session pretraining cohort and ten-session held-out cohort remain required.
The component performs no fitting, model execution, native-file capture or
scientific qualification. A method name is an operator declaration, not proof
of a particular implementation.

## Source and scope

[The paper's Appendix E, Table 10](https://arxiv.org/html/2504.08201v2#A5.T10)
reports RRR, NDT2 and POYO+ only for choice/block accuracy and wheel/whisker R².
All are pretrained on 74 sessions and adapted to the same ten held-out sessions.
The [selected original endpoint contract](../../primary-endpoint-v1/selection.v1.json)
retains that incidence. The final publisher paper remains the task authority;
the versioned author manuscript corroborates these cells. This component does
not introduce numerical reference values or infer reproduction tolerances.

The original author code's [evaluation path](https://github.com/yzhang511/NEDS/blob/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/utils/eval_utils.py)
and the pinned existing evaluator supply ordinary accuracy and flattened,
unclipped R². No binwise pooling across sessions or mixed-unit score is added.
Means and paired differences use equal session weights. Author SEM conventions,
authenticated animal identities and native result provenance remain unresolved;
the output makes no SEM or statistical superiority claim.

## Comparator export

Use the existing complete `neds-binned-panel-v1` operator bundle. A comparator
export has exactly `schema="neds-table10-decoder-export/v1"`, `source_commit`
equal to the existing NEDS pin, the bundle's `evidence_kind`, and `records`.
The records contain exactly the 30 pairs of ten source held-out EIDs and the
method roles `RRR`, `NDT2`, `POYO+`.

Each record has the existing receipt metadata: `eid`, `method`, `trial_ids`,
`unit_ids`, `fit_trial_ids`, `validation_trial_ids`, `pretrained_eids`,
`budget_contract`, `packet_sha256`, plus `predictions`. The ordered identities
must match the bundle exactly. `pretrained_eids` must name all 74 source training
sessions once each. `packet_sha256` contains only `decode_all`, committed through
the existing spike-only input-packet function. `predictions` contains exactly:

| Field | Representation |
| --- | --- |
| `choice` | One raw label `-1` or `1` per ordered test trial |
| `block` | One raw label `0.2`, `0.5` or `0.8` per ordered test trial |
| `wheel`, `whisker` | Finite arrays `[all_test_trials, 100]` in the same scale as the operator targets |

The producer must explicitly translate any native class indices, restore the
correct continuous-target scale and supply independently established identity
provenance. There is no guessed comparator file format or normalization. Strings,
booleans, nonfinite values, missing targets and shortened final-batch outputs fail.
Encoding arrays and extra target aliases fail. Every comparator remains in the
report; no favorable baseline is selected from evaluation scores.

Resources are declared separately for each author method because the paper's
training recipes differ. The existing paired NEDS/candidate budget-equality rule
is unchanged. Neither matching declarations nor hashes attest measured resources,
historical model identity, training isolation or correct prediction ordering.

## Use

Requires the existing NumPy environment. No installs or network calls occur.
The predecessor bridge, evaluator and roster are content pinned. The optional
`--implementations` path allows an isolated candidate to use the unchanged
predecessor implementation directory.

```sh
python3 decoder_comparators.py /operator/bundle.json /operator/paired-export.json \
  /operator/comparator-export.json /operator/panel.json --methods neds candidate
python3 -I -B test_decoder_comparators.py -v
```

The CLI inherits strict JSON parsing and exclusively creates its output file.
`score_comparators` is also usable by an operator without paired exports, but its
output is explicitly the comparator component, not a complete reproduction.
`evaluate_panel` is the complete integration entry point and retains the original
paired report. Candidate-minus-comparator differences cover all four shared
decoding endpoints for each baseline. Encoding superiority, joint decision
thresholds, authentic original splits and source execution remain unqualified.
The generated tests establish only component behavior.
