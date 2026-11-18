# Original Figure 3b improvement endpoint

This selector implements the explicit task-specific scope decision recorded in `docs/proposals/figure3b-improvement-scope-v1/ROOT_SELECTION.json`. Improvement uses the original contextual population-predictivity comparison: zero-based layer 5 and lag indices 17, 18 and 19, across all 14 sessions and eight participants. The 42 job correlations require 5,685 original held-sentence software callbacks. Those counts do not prescribe native process or AI API calls.

The author notebook's cell 5 fixes this selection. It was recovered before new benchmark candidate evaluation; author preregistration is not established. Full 224-array reproduction, individual-neuron and temporal/layer maps, context-length results and author controls remain a separate outcome. An improvement here does not establish improvement of all paper findings.

`contexts()`, `coordinates()` and `selection()` expose the fixed selector. `select_stream()` accepts the original source-context stream and rejects missing, duplicated or reordered selected jobs. A private store reader should apply the equivalent context predicate before array loading. The selector alone does not authenticate the store or candidate execution.

`compare(candidate, reference)` accepts two complete 42-cell packets bound to the same original support. It uses NumPy float64 means: three fixed lag correlations per session, then the equal-session mean of all 14 paired differences. It reports every session difference, each of eight participants' contribution to that estimand, and all leave-one-person-out sensitivity values. Participant-equal means are diagnostics and never replace the original estimate. Undefined correlations propagate; sessions are not dropped.

The provided-author comparator is 0.04512071156679768, distinct from the paper's rounded 0.05. It is the strongest supplied original Figure 3b comparison, not a verified current SOTA or an authenticated new baseline computation. Packet hashes are attributed upstream bindings. The function does not independently qualify execution, a meaningful-effect threshold or uncertainty procedure, and always leaves `binary_win` unset.

Original global PCA, centered response smoothing before the qid split, public exposure, and the 567-versus-579 representation identity gap remain explicit. Fresh participant state prevents additional cross-fold target accumulation; it does not repair the original retrospective preprocessing exposure.

Run the eight generated controls:

```sh
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-001/implementations/original-figure3b-improvement-v1/test_improvement.py -v
```

They exercise selection from all 58,926 source coordinates, unequal session counts per person, fixed three-lag reduction, undefined-value propagation, complete support/order checks and refusal to turn asserted provenance into a win. No authentic data, model or native provider is run. The full-source compact collector retains its separate complete-reproduction contract; its engineering fixture scope must not be relabeled as this scientific endpoint.
