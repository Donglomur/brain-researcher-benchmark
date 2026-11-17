# Recorded finger-EEG evaluator

For `PAPER-paper-signal-add-017`, this package converts safe numeric EEG exports
and source events into grouped trials/windows, enforces chronological training
and source calibration-folder routing, exports target-free test packets, and
reports hard-vote per-trial classification with participant-weighted paired
uncertainty. A complete NumPy spectral reference and label/alignment/no-neural
controls exercise the same evaluation path.

From this directory, with Python and NumPy (tested NumPy 2.4.6):

```sh
python3 finger017.py reference protocol.json report.json
python3 finger017.py packets protocol.json packet-directory
python3 finger017.py score protocol.json score.json --predictions predictions.json
python3 -m unittest discover -s tests -v
```

The [task documentation](../../docs/initial-evaluator-v1.md) defines protocol
fields, source semantics, prospective choices, data rights and remaining gates.
The test fixture provides a generated full protocol example. `provenance.json`
records pinned primary source identities.

Coverage is complete only for the explicitly frozen selected run/trial roster.
No authentic MAT payload, complete cohort or native TensorFlow EEGNet run was
validated. The reference is a prospective spectral comparator; it is not the
paper's fine-tuning algorithm. Generated checks establish engineering behavior
only. Scientific qualification, protected numeric references, source-population
admission and closed-loop reproduction remain unresolved.
