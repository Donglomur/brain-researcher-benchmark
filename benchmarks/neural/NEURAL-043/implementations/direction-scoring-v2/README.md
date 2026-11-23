# NEURAL-043 direction scoring, version 2

This evaluator repairs the per-case target join and adds the contract's paired neural-minus-history and neural-plus-history-minus-history endpoints. It consumes the existing prediction packet format. The registered runtime and its source locks remain unchanged; switching the operator to this evaluator is an integration proposal.

The registered `score_prediction_cohort` concatenates all private labels and mouse units before checking their total lengths. It does not validate each private `case_id`. Consequently a short private target packet and a compensating long packet can be accepted, and an unrelated private case identity is ignored when trial IDs match. Version 2 validates each original case before any pooling, joins case lists by identity, and requires a separately supplied complete expected case roster. Submission omissions are errors, not a smaller scored cohort.

`direction_scorer.score_cohort` takes lists of submissions, public packets and evaluator-only private packets, plus keyword arguments `expected_case_ids` and `access_mode`. It retains these scientific choices:

- Full ordered 16- and 25-direction spaces, separate held-block and held-mouse results, and deterministic first-maximum tie handling.
- Pool held-out trials within mouse before class recall; average mouse balanced accuracy and log loss equally. Test classes absent from a mouse remain disclosed rather than receiving invented recall.
- Clip true-class probabilities at `1e-15` for log loss. Constant valid predictions remain scoreable controls.
- Preserve the approximate 95% mouse t interval, with no population interval for one mouse. Cross-validation training overlap and the small source mouse count limit its interpretation.
- Reject per-case target or mouse-count mismatches, duplicate trials within a split claim, changed class order within a layout, and inconsistent target/mouse/layout identity when a trial occurs in both split claims.

`direction_scorer.score_matched_features` takes dictionaries keyed by `history_time`, `neural`, and `neural_history_time` for submissions and public packets, one shared private packet list, and the same roster/mode keywords. Every family must contain exactly the expected cases and identical held trial IDs, class order and split claim. It returns the individual family scores and the paired per-mouse differences before mouse averaging and uncertainty. Balanced-accuracy differences above zero favor the neural family; log-loss differences below zero favor it. This function does not fit or select a model.

The evaluator is callable with `direct_observation`, `typed_viewer`, `tool_assisted`, or `frozen_program`; the requested mode is retained and never pooled with another. A mode name is an annotation from the trusted host, not evidence of an implemented participant transport. Neither function creates a direct-observation episode, viewer, tool runner, frozen-program sandbox, or target-isolation boundary.

## Check a submission without private targets

`direction_scorer.validate_submission_cohort` checks the public parts of the same
packet format: complete expected cases, ordered trial and class identities,
probability simplexes, one feature family, consistent native layouts and no
repeated held-out trial within a split claim. It shares per-case validation with
the scorer. It needs no private packet, target label or mouse identity and
computes no accuracy, loss or uncertainty.

The public-only CLI accepts three JSON lists: public case packets, submission
packets and the evaluator's independently frozen complete case-ID roster.

```sh
python validate_submission.py \
  --public public-cases.json --submission predictions.json \
  --expected-cases expected-case-ids.json --access-mode frozen_program
```

Successful validation prints a JSON summary and SHA-256 identities of the exact
input bytes it parsed. Invalid inputs exit nonzero without a success summary.
The default combined input limit is 32 MiB; `--max-input-bytes` makes a larger
operator-selected limit explicit. Files are read once, and duplicate JSON keys
and nonfinite JSON numbers are rejected. The summary contains no predictions,
trial identities, labels or private mouse joins. Its `targets_checked`,
`submission_sealed`, delivery and scientific qualification fields remain false.

This preflight is a participant convenience, not a trusted final submission or
an authentication of the supplied public roster. The host must still capture
immutable submissions, authenticate source preparation, check every private
target/mouse join and qualify the execution condition. No registered runtime or
historical source lock is changed by this interface.

The caller must freeze the expected roster from authentic source preparation before outputs exist, retain every source/trial/fold exclusion, capture every submission before reading private targets, and establish the same fitting and allowed-input conditions across feature families. The roster is not authenticated merely by passing a Python list. The existing packets lack explicit public training-trial identities and physical grid identifiers; source preparation must establish fold and cross-recording grid equivalence. This evaluator cannot recover those facts or missing recordings. It uses the two already contracted native layout sizes and rejects inconsistent class sequences within either size.

`test_direction_scorer.py` contains generated controls, including a hand-computed unequal-block/unequal-mouse example and the closed-form two-mouse Cauchy interval check. Run with `python -m unittest -v test_direction_scorer.py` in this directory using the coordinated test pool. The metrics and validation use Python's standard library; the retained t interval additionally requires the already-used SciPy dependency. No install, authentic preparation, decoding model trial or new empirical result is part of this component.

`test_submission_preflight.py` covers public-only completeness, class and trial
alignment, invalid probabilities, snapshot binding, bounded input, ambiguous
JSON and fresh-process CLI success/refusal. Run both modules with
`python -m unittest -v test_direction_scorer.py test_submission_preflight.py`.

Scientific provenance remains the current [understanding contract](../../understanding.v1.json), the preserved [scientific scope](../registered-runtime/SCIENCE_AND_SCOPE.md), the versioned [DANDI release](https://dandiarchive.org/dandiset/001612/0.250927.1801), and the [pinned author repository](https://github.com/arsenyf/Finkelstein_et_al_Nature_2025/tree/19fe755ce3b7e2b6d3c6c5f4afccda2829af303d). This is a correction to the prospective benchmark scorer, not recovered author decoding code. The canonical task, all prior evidence and all scientific/deployment qualification states remain unchanged.
