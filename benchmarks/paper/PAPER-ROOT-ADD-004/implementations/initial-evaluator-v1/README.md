# Respiration–retrieval epoch analysis

Computes localizer-to-retrieval AUC, peak respiratory-phase resultant length versus memory, and exhalation-aligned confidence–8–20 Hz power coupling for `PAPER-ROOT-ADD-004`.

Requires Python 3, NumPy and SciPy already available in the chosen runtime. From this directory:

```sh
python evaluator.py normalized_epochs.json analysis.json
python -m unittest discover -s tests -v
```

The input contains normalized cue/localizer/exhalation EEG epochs, trial identities and labels, respiratory phase/events, and the complete pinned 18-participant roster. The [interface and provenance guide](../../docs/initial-evaluator-v1.md) specifies every field and frozen choice.

This is a prospective computational recipe, not native MATLAB equivalence or a frozen grader. The native MAT adapter, authentic reference results, full trial/channel admission, rights, protected assessment and scientific qualification remain unresolved. Tests use generated engineering controls only; outputs never award a binary reward.
