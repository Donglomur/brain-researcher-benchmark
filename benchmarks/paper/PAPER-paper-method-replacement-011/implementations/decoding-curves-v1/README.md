# Brain Treebank decoding curve component

This independently written component computes the original paper's missing
decoding metric from frozen predictions: held-out single-electrode ROC-AUC curves
for sentence onset, word onset and noun-versus-verb classification. It retains
per-contact peak values and computes regional mean curves from ten contacts
selected by peak **training-CV** AUC. It does not fit a decoder or claim that the
original examples, splits, window grid or numerical figure values are recovered.

Reproduction of the original finding and improvement beyond it are separate,
first-class outcomes. Neither is established by these software controls. Paired
paper-plus-data and paper-plus-data-plus-author-code runs retain separate
`access_condition` values and must use the same underlying frozen source panel.
This component does not deliver those participant packets or combine their scores.

The historical word-responsiveness implementation remains unchanged. Its t-tests
are not a comparator for this ordered endpoint.

## Computation and scientific units

The AUC kernel uses positive/negative ranking pairs, with half credit for exact
ties. Constant predictions therefore yield 0.5; a missing class is an error.
For each of the five training folds, AUC is computed separately at every window.
The five AUC curves are averaged, and the peak of that mean curve determines the
regional contact ranking. Pooling scores across folds is deliberately avoided:
fold-specific score scales can change the pooled AUC despite unchanged ranking
within every fold. Held-out scores never enter contact selection.

The regional result averages ten selected contacts' held-out curves, with the
selected participant/contact identities retained. All retained contacts,
including subject 5, appear in electrode-level results. Subject 5 is excluded
only from regional summaries because of the paper's lesion-related anatomical
exclusion. The reference lists corrupted contacts separately; overlap with
retained contacts is rejected. Every declared task, contact, example and window
must be present. A region with fewer than ten eligible contacts fails rather than
silently changing the source panel. A tie across the tenth/eleventh rank also
fails because the historical tie order has not been recovered.

No accuracy, significance count, all-electrode average, single best region or
single best time replaces the curves. Peak values are descriptive paper outputs,
not new inferential endpoints. Participants remain the independent uncertainty
unit; no electrode-based confidence interval or superiority decision is emitted.
No distinction between left/right hemispheres is inferred: the operator's region
identifiers must preserve the exact source panel groupings when recovered.
A contact may belong to multiple groups (for example an anatomical region and
its enclosing lobe), while remaining one contact in the electrode-level output.

## Operator interface

Only Python's standard library is required. A trusted operator supplies the
reference separately from candidate predictions:

```sh
python -I -B evaluate.py /external/operator/reference.json /external/predictions.json --output /external/curves.json
```

The output is created exclusively and cannot replace either input. It records
SHA-256 hashes of the exact input bytes and never emits example labels or IDs.
This is an operator-side computation, not an authenticated participant transport
or an input-preparation pipeline. Source input arrays, targets, predictions and
outputs must stay outside Git.

`reference.json` has exactly:

- `schema: "treebank-decoding-reference/v1"`, `task_id:
  "PAPER-paper-method-replacement-011"`, `scope: "operator_declared_panel"` or
  `"generated_control"`.
- `access_condition`: `"paper_and_data"` or `"paper_data_and_author_code"`, fixed
  by the operator. The prediction condition must match and is preserved in output.
- `source_manifest_sha256`: lowercase SHA-256 of the operator-frozen source
  reconstruction manifest. This is a declared identity, **not** verification of
  that external manifest. It must eventually bind original recording/transcript
  versions, electrode inventory, exclusions, window definitions, allowed
  single-electrode observations, example construction, label polarity, original
  80/20 partition and five training folds. None is invented by this component.
- `window_ids`: complete ordered window identifiers from that source manifest.
  They are opaque and preserved in output. The source's precise last-window
  treatment is unresolved; this package does not manufacture a 20- or 21-window
  reconstruction or infer timing from list position.
- `regions`: complete source panel region identifiers, including any source
  hemisphere distinctions. Authentic membership/grouping remains unresolved.
- `subjects`: entries with integer `id` from 1 through 10, `electrodes` as
  `{id, regions}` entries (`regions` is a list of group identifiers and may be
  empty for contacts without region-panel membership), `corrupted_electrodes` as
  excluded contact IDs, and `examples`.
  Example tables have exactly `sentence_onset`, `word_onset`, `noun_verb` keys.
  Each table contains `{id, label, fold}` rows: integer label 0/1 and training-CV
  fold 0..4, or `null` for the original test partition. Every fold and test must
  contain both classes. IDs are unique within a participant/task. The same
  participant/task table is used for every contact, preserving shared splits.

The operator panel scope additionally requires all ten participants and 114
declared corrupted-contact exclusions. These checks reject obvious incomplete
panels but cannot authenticate membership. Generated controls intentionally use
smaller invented populations and never acquire scientific status.

`predictions.json` has exactly `schema: "treebank-decoding-scores/v1"`, `task_id`,
`access_condition` and `subjects`. Each subject has `id` and `electrodes`; each electrode has `id`
and `tasks` with the same three task keys. Every task contains `train_cv` and
`test` lists of `{id, scores}` rows. `scores` is one finite real number per ordered
window. Training scores must be out-of-fold predictions, with preprocessing and
fitting confined to the corresponding other four training folds. Test scores
must come from the model fitted on the entire original training partition.
Identity checks can reject overlap, missing/extra predictions and duplicates;
they cannot prove training provenance or allowed observations. Boolean/nonfinite
scores and duplicate JSON keys are rejected.

The generated fixture in `test_evaluate.py` is a complete format example. It is
software test data, not an original-data manifest or scientific baseline.

## Evidence and remaining work

The canonical [improvement contract](../../improvement.v1.json) identifies
[the original paper](https://arxiv.org/html/2411.08343v1), Fig. 4 and Appendix A.9,
and the pinned author
[regression runner](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/regression_runner.py)
and [time-test runner](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/run_time_tests.py).
No author code is vendored. The code revision is
`c54ba38eab7814538bc03b1b6d29a3f50f034e12`.

This component closes the mathematical AUC/curve-reduction gap only. Authentic
source release and examples, original splits/seeds and negative sampling, native
preprocessing/alignment and window endpoints, exact source regions/top-ten
identities, original numerical figure arrays, author logistic-regression replay,
protected candidate delivery and fitting provenance remain unresolved. A frozen
meaningful effect, participant-aware uncertainty rule, equal access/resource
budget and original-panel comparison must precede any paper-win claim. The
returned qualification fields remain false even if declared inventory checks
pass. No authentic data preparation, fitting, native author run or solver trial
has been performed here.

## Bounded verification

Run `test_evaluate.py` through the shared two-slot test pool under the current
project policy. The tests compare the AUC algorithm to an independent pairwise
definition, demonstrate the fold-pooling error, force test-score/selection
disagreement, check subject 5 and corrupted-contact behavior, attack identities,
missing windows/companions, small regions, cutoff ties, and exercise CLI receipts
and overwrite protection. They establish software behavior only.
