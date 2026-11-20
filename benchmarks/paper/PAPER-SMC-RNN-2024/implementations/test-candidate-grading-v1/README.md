# TEST comparison for the frozen rate-gain candidate

This component connects a gain selected on restricted VALID predictions to a distinct original MC_Maze 20 ms TEST comparison. It reuses the existing global-gain kernel and canonical evaluator. It does not select a gain on TEST, rerun the author model, or turn generated source controls into a scientific result.

## What is compared

The reference is the existing frozen noncausal author prediction. The candidate applies the genuinely completed VALID-selected gain to that same TEST prediction. The frozen grid, exact identity-first tie rule and dtype-preserving arithmetic remain unchanged. Identity gain copies the prediction bytes exactly; other gains scale all eight rate arrays consistently, including the inputs to the original velocity decoder.

TEST has 574 evaluation trials. The original decoder cohort has 2,295 TRAIN+VALID trials in the original recorded order. Rate fields retain 35 observed bins and separate 10-bin forecasts for 137 held-in and 45 held-out neurons. The 45-bin author inference input must not be confused with a 45-bin observed-rate field. These TEST decoder inputs cannot substitute for restricted VALID predictions used to choose the gain.

## Distinct identities and protected grading

`test_core.freeze_method` binds the original TEST baseline and its recorded checkpoint/order provenance to a genuinely completed VALID gain selection. The VALID and TEST phases retain distinct identities. Source and runtime descriptors are trusted operator configuration; participant-supplied success flags, arbitrary manifests or fabricated custody are not grading authority.

`transform/test_transform.py` applies the frozen method without a target operand. This API does not itself establish physical exclusion of targets from an ambient filesystem. Its output has a genuine candidate role; it is not relabeled as an original author prediction or a VALID artifact.

The bounded host revalidates the retained completed-selection gate before creating the TEST grading child. The full VALID proof tree remains host-only. The host creates the child custody and request internally rather than accepting a caller-written custody assertion.

The trusted grading child has the selected TEST target mounted read-only from startup. Its code admits target content only after authenticating and privately snapshotting both complete TEST predictions, validating their distinct freezes, and independently verifying the candidate's relationship to the frozen gain and reference. This is an audited ordering rule inside protected operator code, not a claim that the target file is absent from that child's filesystem.

The evaluator and original TEST scorer remain unchanged. The report includes reference and candidate co-bps, forward-prediction bps, PSTH R-squared and velocity R-squared, with signed candidate-minus-reference deltas. TRAIN decoder handling is preserved. No per-model or per-metric reset of the whole grader budget is permitted.

## Scientific interpretation

A positive primary delta would be an observed increase in the co-bps point estimate against this frozen reference on the original endpoint. It would not establish uncertainty, generalizable improvement, new representational learning, independent replication, or state-of-the-art performance. A global positive gain primarily changes rate calibration; the original canonical zero-rate and NaN behavior is retained, and the fixed grid is not replaced by a fitted closed-form rule. Changes in the other three metrics must be reported rather than assumed favorable or invariant.

The selected released smoothing checkpoint's adjacent configuration declares validation-mode inputs. TRAIN-only optimization follows only if the actual run followed that saved configuration. The pinned trainer selects checkpoints using VALID co-bps, but the actual run's configuration and checkpoint-selection history remain unproved; VALID therefore cannot be assumed untouched. Local-weight lineage, exact Table 2 identity and exact paper DANDI revision also remain qualified limitations. The 32 trajectory averages are Monte Carlo inference samples, not independently trained replicates. Original TEST targets are public, so this is not a newly hidden evaluation set.

## Source and runtime status

The TEST transformation and comparison are source construction. An authentic restricted VALID prediction, a genuinely completed gain-selection receipt, fresh runtime/resource admission and actual paired grading are still required before any result exists. The proposed whole grading actor retains 2 GiB, 600 CPU seconds soft / 605 hard, 720 seconds of work plus 60 seconds for cleanup, and one numerical thread. Those limits are fallible proposals, not measured adequacy or execution authorization.

Generated controls exercise the changed identity, transformation, ordering, reporting and ownership boundaries with explicit fixtures and doubles. They neither open original predictions, checkpoints or targets nor establish physical runtime qualification. The historical reference and existing VALID/gain routes remain separate and unchanged.

For grading, the existing scratch guard requires `R + C + max(R, C) + 16 MiB <= 512 MiB`, where `R` and `C` are the reference and candidate file sizes. With the fixed 87,250,290-byte reference, the largest admissible candidate is 216,421,703 bytes. A transform may produce a larger file within its separate 512 MiB output cap; grading then refuses it. These caps are not completion guarantees.

The source-control command requires a fresh external `ARTIFACT_DIR` outside every Git root and outside `/tmp`. A fresh directory beneath the CI runner home is suitable. This preserves the production readonly-input path guard; it is not relaxed for tests.
