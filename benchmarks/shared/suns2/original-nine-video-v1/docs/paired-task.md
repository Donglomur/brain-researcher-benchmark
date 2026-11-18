# Paired SUNS2 paper tasks

This extension defines two assistance conditions and two requested outcomes on the original nine-video TUnCaT spatial segmentation endpoint. It adds material and submission bindings around the existing [fold projector](fold-contract.md) and [scorer](scorer-contract.md). It does not provide a qualified candidate sandbox, execute a method, or establish benchmark readiness.

## Scientific target and materials

The [paper](https://doi.org/10.1038/s42003-024-06668-7) specifies nine 50 × 50 × 6,000 recordings, 20 Hz, with eight training videos and one held video in each fold. Preserve all frames, all nine folds and the source coordinate convention. A movie uses `[time, row, column]`; its manual mask uses `[column, row, neuron]`. The equal spatial dimensions cannot detect an accidental transpose.

The complete current input bank has been authenticated and read. A separately admitted comparison established that the nine movie files, nine manual-mask files and quarantined temporal template from the fresh paper-linked v2 archive selection match the frozen v3 member references byte for byte. This is selected-file snapshot parity, not authentication of the entire 16.907 GB archive or its historical immutability. The accepted comparison result has SHA256 `8c3b738dc73e7ba32925e1d497d1273013c0d69e9351e3da69069dcd7a795997`; its independent review is `6f70eee2c73b9aa51ad081f6a64132da65a62d19dea05e62508eace17461de4a`.

| Assistance condition | Active-fold inputs |
| --- | --- |
| `paper_data` | The same three original PDFs, all nine full movies, and exactly the active fold's eight training-mask files. |
| `paper_data_official_code` | Those same inputs plus the reviewed 89-file official source allowlist, including its original license files. |

The common PDFs are the main paper, Supplementary Information and Reporting Summary. Keep their original bytes, roles and notices. The selected code is [v1.2.0 at commit `128eb4738e026b89a341a6013e7bd7b6dc7c3216`](https://github.com/YijunBao/SUNS2_ANE_paper_reproduction/tree/128eb4738e026b89a341a6013e7bd7b6dc7c3216). The paper-cited v1.1.0 is a different release; do not treat the two as interchangeable. Source availability does not qualify its dependencies or execution.

The participant receives no private held-mask file or hash, author prediction, evaluator output, checkpoint, complete operator inventory, or historical temporal-template file. A candidate may use no template or derive one solely from the active eight training videos and masks. Such derivation requires declared provenance and stays within that fold. It does not resolve the historical template's lineage.

Published material already exposes some answers: Figure 5a includes ground-truth and prediction outlines, and reviewed source contains public scores, constants and result links. Record this exposure in both conditions as applicable. File isolation cannot establish absence of prior access or pretraining contamination. The official source condition does not implicitly grant linked weights or result files.

## Eighteen fresh states, thirty-six frozen outputs

The operator freezes one procedure bundle **per arm and trial** before releasing any fold. Each bundle declares distinct recreation and improvement procedures or agent policies, including their adaptation and template rules. Algorithms may differ between arms; the scientific question, common material identities and declared budgets remain matched. A shared operator-pinned protocol identifies those common conditions. Source checks authenticate declarations, not the timing or enforcement of execution.

Use eighteen separate participant states: two arms × nine folds. Each state receives only its active eight training masks and produces both requested outcomes. Both procedures may use training-only validation within those eight videos under the frozen policy. The held video's unlabeled movie is available for inference; its private labels and grading results are not.

Freshness includes the participant's conversation, process state, workspace, caches, models, generated code and derived templates. None may carry learned information from one fold into another or from one arm into the other. Otherwise the union of successive eight-mask training sets would expose every held label. The shared bundle must not contain additional private benchmark-label information or artifacts learned in earlier folds. The declared public paper and reviewed-code exposure remains an explicit exception.

Only the trusted operator may retain all references and collect all fold outputs. A unique state identifier, reset receipt or signed declaration does not itself prove a reset or filesystem isolation. A compatible runtime must enforce the boundary and supply independently qualified custody evidence; this construction has not executed eighteen authentic isolated states.

Freeze **all thirty-six outputs** before any protected-reference grading or report feedback: two arms × two outcomes × nine videos. Four complete submission directories remain separate. Independently trusted fold receipts bind each state's two output files to its arm, procedure, held video and fresh-state identity. Participant-written custody claims cannot establish these facts. Verify every directory and output against the freeze before returning any of the four reports; a late substitution or incomplete panel invalidates the combined release. Operator-held reference paths never come from participant metadata.

The paired adapter enforces this barrier only on its own route. The standalone grader remains callable for operator controls; an external controller must prevent participant feedback through other routes. Re-admission and returned-pin checks validate recorded reads, not continuous filesystem integrity.

## Recreation and improvement stay distinct

Recreation asks the candidate to implement the declared paper recipe and report the same endpoint. The default ANE training-label recipe is the paper-described one-to-one Hungarian matching at IoU ≥ 0.5. The selected released code instead labels proposals using any IoU > 0.3; a recreation of that released behavior must be named separately. These training-label rules do not replace the scoring metric.

Released scripts include held-video validation, GT-loaded scoring, and GT-dependent caches or parameter selection. Protected adaptations must keep private held labels outside candidate execution and limit fitting, validation and tuning to the active training eight. Record every adaptation. Inspected fixed-epoch/final-save code does not by itself demonstrate validation-driven checkpoint selection. Replaying or calibrating the author baseline is an operator control, not participant recreation. Numeric agreement with released outputs does not establish the unknown historical producer, checkpoints or training procedure.

Improvement asks for a better result on the **same nine-video endpoint**. Reuse the existing grader without replacing its literal original arithmetic, mask order, multiplicity or undefined-result semantics. The separately declared audit deduplicates exact prediction geometry for both author and candidate, retains every GT instance and uses order-invariant maximum-cardinality IoU ≥ 0.5 matching. A descriptive improvement requires a positive exact original mean delta, a changed unordered geometry set, and a positive audit mean delta. Permutation-only or duplicate-only gains cannot qualify. Report the two outcomes and four arm/outcome panels separately; introduce no new recreation pass threshold or generic success flag.

The accepted saved-author control qualifies intake and scoring against its released reference. It does not establish candidate execution or method reproduction. A better exposed-panel score is not evidence of current global SOTA, nine independent animals, population generalization or biological significance. Animal grouping and historical producer provenance remain unresolved. No model, training, authentic projection or task registration follows automatically from these source components.
