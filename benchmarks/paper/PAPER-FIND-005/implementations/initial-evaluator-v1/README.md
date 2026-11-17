# IBL brain-wide-map single-cell evaluator

This local evaluator implements the sorted-spike-to-regional-summary path for stimulus, choice and feedback single-cell sensitivity. It pools probes within sessions, preserves biological identities, applies common source trial/unit masks, counts event-window spikes, reconstructs the pinned source's condition-combined U test, computes the paper's dual-test fractions and regional statistics, and reports a separate prospective mouse-weighted summary.

**Construction status:** generated engineering controls only. Scientific qualification is unknown. The package does not establish source/figure agreement, a protected grader, complete paper reproduction, source cohort authenticity or benchmark difficulty. The canonical task remains unchanged.

Read [the task documentation](../../docs/initial-evaluator-v1.md) for the input contract, source conflicts, statistical interpretation and remaining gates. `provenance.json` records primary identities; `THIRD_PARTY_LICENSE.txt` records the pinned MIT source terms. Native IBL loading, data acquisition, model fitting and scientific campaigns are outside this evaluator.

Run from this directory with an existing Python interpreter containing NumPy and SciPy:

```sh
python3 evaluator.py --input local-export.json --output results.json --profile pinned-examples
python3 -m unittest discover -s tests -v
```

A profile is mandatory. `pinned-examples` counts choice activity before **stimulus onset**, reproducing the pinned example's alignment. `paper-choice-window-proposal` counts choice activity before **first movement**, matching the paper method while retaining the source conditional statistic. Neither profile settles the source/paper conflict or supplies a scientifically qualified result.
