# Decision-times Table 1 reporting comparison

The completed author-law replay agrees with the published precision for **48 of 54 held-contrast RMSE fields** in both reporting implementations. All six RMSE discrepancies concern encoding. The other **72 fields are full-data R² companions**, and their agreement depends strongly on whether the released helper or the maintained scorer is used.

This is a reporting result for the existing benchmark, dated 2026-11-25. It does not establish a paper-reproduction pass, an AI improvement, SOTA or benchmark readiness. No agent was evaluated in this comparison.

## Scope and comparison rule

The closed replay covered 26 participants, nine targets, accuracy and speed instructions, all three author laws (linear, Pieron and Fechner), and 93 global contrast values per target/instruction cell. It completed 131,976 original-law fits using the qualified released targets and the separately recovered behavioral population. The target set preserves RT, six intervals, encoding and decision, including the distinction between behavioral RT and the model response endpoint. Reusing released targets does not regenerate neural events or attest the historical publication-generating environment.

The comparison retained every key in the [126-field reference contract](../primary-endpoint-v1/reproduction.v1.json): 54 held-contrast RMSE fields in milliseconds, 54 full-data latency R² fields and 18 Fechner accuracy R² fields. Accuracy predictions use the latency-fit parameters; these are not separately fitted accuracy models. Held-contrast fitting is within participant, not participant-held-out evaluation. The 126 fields are references within one task, not 126 benchmarks or independent biological samples.

Each result was compared with its literal printed [Table 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC12755882/#table1) token, retaining decimal precision and units. **Compatible** means that the absolute difference is strictly below half of the last printed unit; exact equality at that boundary is **ambiguous**. Exact decimal/rational arithmetic was applied to recorded JSON decimal representations, without an epsilon. This is a declared reporting convention, not a scientific tolerance or a new task pass rule. The same fixed reference and rule were used for both lanes.

## Complete results

| Endpoint group | Fields per lane | Released-helper compatible / incompatible | Maintained compatible / incompatible |
| --- | ---: | ---: | ---: |
| Held-contrast RMSE | 54 | 48 / 6 | 48 / 6 |
| Full-data latency R² | 54 | 50 / 4 | 3 / 51 |
| Fechner accuracy R² | 18 | 3 / 15 | 0 / 18 |

There were **zero boundary-ambiguous fields** in either lane. No endpoint was dropped and no more favorable reference was substituted.

All six RMSE incompatibilities are encoding: each of the three laws under each instruction. The four released-helper latency R² incompatibilities are also encoding: linear and Pieron under both instructions. The encoding discrepancy remains unresolved; these counts do not establish its cause.

The two R² lanes preserve different computations. The [released `r_squared` helper](https://github.com/GWeindel/decision-times/blob/76464a9ca15564897e58256081af4b99d08ae8db/utils.py) subtracts contrast-indexed Series, so label alignment affects residuals. The [maintained scorer](../implementations/initial-evaluator-v1/evaluator.py), used through the [complete panel](../implementations/contrast-panel-v2/panel.py), pairs intended contrast positions. They remain separately named outputs. Greater Table 1 compatibility in the released-helper lane does not establish that it was the historical Table 1 implementation, nor justify silently replacing either estimator.

## Table 1 and Results remain separate

The paper itself reports conflicting encoding/Pieron latency R² values: Table 1 gives **0.57 under speed and 0.30 under accuracy**, while the [Results discussion of encoding and decision](https://pmc.ncbi.nlm.nih.gov/articles/PMC12755882/#s2-3) gives **0.53 and 0.34**, respectively. Both public field identifiers occur among the released-helper latency mismatches. This is identifier overlap only: this operation did not evaluate numerical agreement with the Results values or use them as replacement references. The discrepancy needs clarification or version-specific producing evidence.

## What this result establishes

The complete released-target author-law workload and the Table 1 reporting comparison have been executed. The remaining encoding RMSE discrepancies, accuracy R² incompatibilities, estimator differences and historical-runtime uncertainty prevent interpreting these counts as a complete reproduction. The original source is pinned to [`GWeindel/decision-times` at `76464a9ca15564897e58256081af4b99d08ae8db`](https://github.com/GWeindel/decision-times/tree/76464a9ca15564897e58256081af4b99d08ae8db); the paper reference is [eLife 108049, version 3](https://doi.org/10.7554/eLife.108049.3).

Protected agent delivery, the strongest original comparator and a joint improvement decision, participant uncertainty, meaningful effect sizes and evidence of an AI gain remain separate requirements. This note changes no score, scientific acceptance criterion, access rule or readiness status. Earlier source-only notes retain their dated scope; the execution and reporting facts above are the later result.
