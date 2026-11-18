# Complete Figure 2d paired-panel support

This operator-side component joins two complete outputs from the existing
`feature-decoding-v1` scorer. It preserves the full ordered source panel and
returns coordinatewise candidate-minus-baseline correlations. It does **not**
decide reproduction, improvement, statistical significance or a paper win.

The selected endpoint needs the original AM, PR and TP populations, every source
window, one original condition and all ten stimulus-identity-shuffled controls.
Within every cell, the original scorer preserves 1,000 unfamiliar correlations
and 1,000 × 36 familiar correlations. Familiar fold predictions remain dependent
repeated predictions of the same 36 faces. This component neither averages them
nor calls them independent observations.

## Operator interface

1. Independently recover and qualify the **complete** source scope. Construct a
   `PanelContract` with original population/face/feature/window identities and
   exact external source/condition-map artifact hashes. Each population retains
   its own ordered windows; no time edges, neuron counts, scaling population,
   seeds or shuffle maps are guessed here. Multiple populations in one region
   are supported; including one AM/PR/TP record does not prove cohort completeness.
2. Freeze the candidate and competent baseline predictions before inspecting
   protected targets. Run the existing feature-correlation scorer separately for
   each complete population/window/control cell. Preserve its undefined states.
3. Supply `ScoreCell` streams in `contract.schedule()` order, each carrying the
   exact contract hash, its prediction commitment and the existing scorer output.
   Compare only within one information condition (`paper_data` **or**
   `paper_data_author_code`); never pool the two assistance arms.
4. `compare_panels(contract, baseline, candidate, emit)` validates and emits one
   immutable `CellComparison` at a time. The 1,000 × 36 familiar structure and
   face IDs survive. A null correlation stays null; its paired difference is
   undefined, not zero. Negative differences remain negative. If both runs claim
   the same actual target but disagree whether it is constant, comparison fails.
5. Only after exact exhaustion of both streams does the function return a
   complete-support receipt, including contract/output/prediction-chain hashes.
   Missing, extra, duplicated/reordered, malformed or cross-contract cells fail.
   An output consumer may retain earlier cells after a later failure; **those are
   partial, uncertified outputs**, never a complete panel. Consumers must require
   the returned receipt and preserve any failed attempt.

The adapter does not load source data or private targets. It reuses the existing
scorer result structure and does not reimplement the correlation metric. One cell
is materialized at a time; whole-panel storage belongs to a separately admitted
consumer. There is no command-line data runner, numerical source replay or model
trial in this package.

## Scientific limits

Hashes and support checks bind supplied inputs; they do not authenticate a paper
source, establish that a score was computed from a committed prediction, or prove
that the declared feature order/normalization was used. Source records must bind
the actual target and preprocessing history externally. All original roster,
solver, time-grid, feature-scaling, shuffle-map, reference-curve and panel-reducer
questions in `primary-endpoint-v1/selection.v1.json` remain open. The earlier
geometry scripts' encoding regressions, RMS feature normalization and time-window
helper must not silently become a Figure 2d decoder.

No original scalar reduction is known, so this package deliberately exposes no
mean, regional best score, win count, SEM or superiority threshold. A later
scientifically reviewed complete-panel comparison criterion must resolve the
dependence/uncertainty and companion-control requirements before any improvement
decision. Current outcomes remain unknown. This component does not adopt a new
task, change the selected endpoint, update a central contract or promote readiness.

`test_panel.py` uses generated complete-shape scorer records. It exercises all
three regions and eleven conditions, exact 1,000/36 support, signed and undefined
differences, omitted/extra support, cross-arm contracts, malformed correlations,
identity order and consumer failure. These are software controls, not empirical
reproduction evidence. Maintainers may enroll this task-local test command in the
component integrity matrix; no central workflow is modified by this proposal.
