# Complete-support paired oddball comparison

This operator utility compares a frozen reference and candidate using the
unchanged [original-fold scorer](../oddball-auroc-v1/README.md). Before scoring,
it requires identical declared retained-epoch metadata for every original
participant, including early epochs excluded from scoring. Equal class counts
or equal array shapes are insufficient: every opaque trial identity, run,
shape, condition and early/late designation must agree. Participant and trial
row order may differ because the scorer aligns predictions by identity.

The comparison retains both complete input score panels and candidate-minus-
reference AUROC differences at every participant/fold/shape/time cell, their
equal-fold participant curves, and their equal-participant group curves.
It preserves all twenty participants, 158 runs, six directional folds, eleven
shapes, 301 code-axis times and two smoothing branches. It never pools the
overlapping fold predictions, selects favorable times, clips below-chance
scores, or reduces across shape, time or branch to make a scalar result.

## Use

Use an existing Python environment with NumPy, from this directory:

```sh
python3 -B paired_oddball.py reference-packet.json candidate-packet.json comparison.json
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Both packets have exactly the original scorer's documented input format.
They contain evaluator-owned labels and must remain outside participant
inputs. The output is created exclusively and records both packet byte hashes
plus a canonical declared-support hash. This utility loads both full prediction
packets in memory; it is an operator component, not a resource sandbox or a
streaming reader. Its generated fixtures do not qualify authentic-input memory
requirements. Keep packets and full comparison outputs outside Git.

The output's `reference` and `candidate` objects retain the complete original
scorer results, including axes and class counts. The `paired_differences`
objects have the same axes and contain:

- `subject_fold_shape_time_auroc_difference`: shape `(20, 6, 11, 301)` per branch.
- `subject_shape_time_auroc_difference`: equal mean over the six folds.
- `mean_shape_time_auroc_difference`: equal mean over twenty participants.

Positive differences favor the candidate, negative differences favor the
reference, and zero means equal supplied predictions' AUROC at that cell.
No pointwise counts or scalar win/loss summary are emitted. Participants remain
the independent biological unit; no confidence interval, significance or
multiplicity decision is inferred from the many dependent cells.

## What remains unresolved

This implements a missing descriptive pairing step in the
[selected endpoint contract](../../primary-endpoint-v1/improvement.v1.json).
It does not implement scientific admission. `scientific_outcome` remains
`unknown`, `research_qualified` is false, and `superiority_decision` explicitly
states that the source policy is unresolved.

Identical metadata declarations do not authenticate original epoch lineage,
MEG feature bytes, final-paper correspondence, an independently exported
`Epochs.selection`, or the strongest author comparator. The caller-supplied
reference is never automatically labeled an author baseline. The source's
code-axis versus paper-axis discrepancy, normalization, published smoothing
producer, authentic complete predictions, numerical reproduction tolerance,
meaningful gain and paired participant uncertainty/multiplicity policy remain
open. A gain in one displayed cell does not establish a paper result.

This utility can serve either assistance condition after an independently
qualified execution, but it does not deliver participant inputs, verify which
condition produced predictions, enforce training isolation across reused
directional folds, or establish matched access/resource budgets. It performs
no model fitting, neural-data preparation or authentic-data execution. The
original scorer and all scientific contracts and historical identities remain
unchanged.

Generated controls exercise both complete real scorer panels, reordered
identities, a single localized gain, branch-wide losses, unequal fold sizes,
equal-count label swaps, renamed identities, changed early-epoch metadata,
near-equal but nonidentical time axes and incomplete original support. They
establish software behavior only.
