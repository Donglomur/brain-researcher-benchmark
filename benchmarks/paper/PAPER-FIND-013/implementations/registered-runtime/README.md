# PAPER-FIND-013: bounded CA trajectory reconstruction

This local component scores numerical reconstruction of the supplied processed CA1/CA3 center-of-mass trajectories. It does not reproduce raw imaging, upstream place-field selection, optogenetic analyses, model mechanisms, bootstrap paper statistics or the whole paper. Animal labels are source-assigned; small animal counts limit population interpretation.

Use only the public `CA1.mat`, `CA3.mat`, identity manifest and `PUBLIC_CONTRACT.json` listed in `public_assets.json`. The clean MAT files contain COM trajectories and onsets; precomputed `PFs` information is excluded. The public contract supplies the exact identities, active-case fingerprint and machine-readable submission shapes. Operator references and publisher workbooks are not candidate inputs.

[METHODS.md](METHODS.md) is the self-contained scientific protocol, including matrix orientation, onset indexing, all diagnostic formulas, summary populations and undefined-result rules. This is a protocol-guided component, not an established paper+data A/B task.

Submit one strict UTF-8 `submission.json`, at most 5,000,000 bytes. Report every declared plane and all 2,657 field IDs, including short-field and undefined outcomes, plus four condition groups, 22 animal-condition records and 16 contrast records. Partial submissions retain the entire identity roster and explicitly abstain on unreported results; whole abstention uses the contract's empty-table form. Equivalent finite OLS implementations are allowed.

Use the full raw post-onset lap clock starting at one, retaining gaps. Multiply source COM by six and subtract its onset value in the same units; fit the finite observations with an intercept. The 15-lap interpolated support span determines summary eligibility, not a first-15-lap fit. Pooled directional classification uses p<0.05 and nonsignificance p≥0.05; the helper uses p≤0.05; animal directional classification uses p≤0.05 with nonsignificance p>0.05 and its declared classified denominator. Undefined p is not a valid nonsignificance claim. Preserve the animal median-absolute-slope source contrast N−F separately from descriptive F−N. The machine-readable contract specifies exact fields, null masks and statuses.

Read every score family and its coverage. The grader retains column-specific continuous errors, exact status/count mismatches, four condition panels, animal/contrast signed residuals and candidate-ledger consistency. There is no blended reward, positive-effect reward or scientific accuracy floor. A complete but wrong answer is scored. A complete error is null for incomplete or unsupported comparisons; a small reported-subset error is not a complete score. Finished-file grading cannot establish that the submitted answer was computed from the public data.

The ordinary scoring interface is:

```text
python3 tools/neurobench.py score PAPER-FIND-013 --submission /absolute/path/submission.json --output artifacts-build/fresh-output --review /repository/path/review.json --other-reserve-bytes 352000000
```

The review must bind a fresh one-off allocation, current cost history and exact submission. No candidate program, network request or model call is launched. The numerical scorer, direct ordinary call and common-CLI integration are verified.

The capacity successor preserves the qualified scientific and isolation paths. Each attempt needs a separate root review with the current complete image/reservation inventory and latest closed additive cost; the source-only capacity policy is not an allocation. The five-file public view now includes the exact existing JSON token, shape and scalar limits in METHODS.md. Historical execution evidence remains historical; this capacity successor has not been run merely for registration.
