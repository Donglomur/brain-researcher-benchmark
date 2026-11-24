# Fixed nested Ridge: completed negative result

On 24 November 2026, the frozen training-sentence regularization candidate completed **42 original Figure 3b cells, 14 sessions, eight people, 5,685 prediction requests and 90,960 fresh Ridge fits**. It did **not** improve the original primary endpoint.

| Original equal-session mean Pearson | Value |
| --- | ---: |
| Fresh fixed-alpha reference | 0.04512071156679768 |
| Fixed nested-Ridge candidate | 0.04498980902383724 |
| Paired candidate minus reference | -0.00013090254296041978 |

There were 16 positive and 26 negative cell differences, four positive and ten negative session differences, and three positive and five negative person-mean diagnostics. Seven leave-one-person-out primary deltas were negative; one was positive. Every cell, session and person remains included. [RESULT.json](RESULT.json) retains the categorical directions for all 14 source sessions and eight source people, without publishing raw neural rows, predictions or individual numeric scores.

These counts describe heterogeneous results; they are not a significance test. Eight people are the biological clusters. The primary endpoint still weights the 14 sessions equally, after averaging the three fixed lag correlations within each session. Person means and leave-one-person-out values are diagnostics; neither changes the primary weighting. No favorable subgroup, new threshold or tuned grid was substituted.

- [Aggregate result and complete direction roster](RESULT.json)
- [Method, exact source/runtime identities and closure evidence](PROVENANCE.json)
- [Byte-identical measured guest driver and generic input contract](../../../implementations/trusted-figure3b-nested-ridge-v1/README.md)
- [Fresh fixed-alpha reference](../trusted-figure3b-reference-20261124/README.md)
- [Unchanged candidate method](../../../implementations/original-nested-ridge-v1/README.md)

## Same task and fixed method

The existing candidate searches alphas `(0.001, 0.01, 0.1, 1, 10)` using three deterministic folds of outer-training sentence groups. It chooses the largest pooled inner-validation Pearson correlation; ties within 1e-12 prefer 0.01, otherwise the smaller alpha. It then refits on all outer-training rows. Query targets never enter this selection. The source code and grid were frozen before this run.

All original features, layer 5, lag indices 17–19, response transformations, held-sentence exclusions, row order and pooled Pearson scoring are unchanged. The saved candidate and fresh reference receipts match all 42 target/support/qid/time/row/fold identities. All prediction and receipt hashes were verified. The fixed-alpha reference was reused from its completed authenticated run, not recomputed. Its scores were loaded only after candidate fitting completed.

The existing reducer uses `author_*` and `provided_author_reference` as mechanical field names. Here those fields contain the **fresh A3 fitted reference**, not merely the earlier provided-author array reduction. The inherited historical reducer wording about provided arrays not being reexecution does not describe this comparator. Participant and general scientific qualification flags remain unchanged and separately scoped.

## Execution and limits

The historical runtime was Linux/arm64, Python 3.11.3, NumPy 1.24.3, SciPy 1.10.1 and scikit-learn 1.2.2. All loaded numerical thread pools reported one thread. The measured worker took **74.402 seconds**, including its fit-count observer; complete outer execution and closure took **78.897 seconds**. Worker peak RSS was **131,993,600 bytes**, not whole-VM memory. Exactly 90,960 entries and returns of the unchanged Ridge fit method were observed: 85,275 inner fits and 5,685 refits. The container exited normally, was removed, and its absence and all process closures were verified.

This is an operator-authored classical comparison. It is not an AI result, novelty, SOTA, a clean unseen holdout, participant NativeProvider qualification, or complete 224-array/whole-paper reproduction. Training-only alpha selection does not undo the original supplied retrospective PCA, centered smoothing or public exposure. Including the original alpha in the grid does not guarantee better outer predictions. This fixed candidate is retained as non-improving; no retry, changed grid or follow-on method was run.
