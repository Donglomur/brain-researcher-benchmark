# Retained decoder-score replay

This operator component checks the first-experiment predictions retained by the pinned author's `decodeTrialOutcome.m` save. It complements the existing Poisson encoding replay. It supplies an unexecuted MATLAB export bridge and a tested Python numerical replay; neither is a reproduction of the complete Figure 3 or Figure 4 findings.

The [pinned author decoder](https://github.com/sakoay/ErasmusAttn_2020/blob/130f5e64f86bd63980f70bb839c02cd264782aef/decodeTrialOutcome.m) calculates normalized trial-weighted accuracy, saves accuracy columns, and deletes prediction columns after the first experiment. Consequently only the retained prediction column can be independently recalculated from that save. The remaining accuracy columns are preserved source outputs, not replayed null experiments. The permutation helper's ordering and output width have not been authenticated here: requested shuffle count and observed accuracy-column count stay distinct.

The pinned variant uses three-fold SVM/ECOC decoding and excludes `condition_code` and `past_condition`. The [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11737872/) describes logistic decoding and has an unresolved Figure 4C prior-choice/past-outcome discrepancy. This component does not select a resolution or equate this source variant with the publication.

## Operator use

In a separately admitted, trusted MATLAB environment with the pinned author dependencies, explicit existing saves can be exported:

```matlab
export_decoder_scores({'operator-owned-decoder.mat'}, '/private/decoder-export.json')
```

The bridge checks the resolved decoder file's SHA256, preserves every supplied cell/subgroup, records source exclusions, and preserves source trial numbers, weights, event coordinates and matrix orientations. The prefiltered-list index is explicitly separate from original trial identity. MAT files can contain executable objects: this bridge is for trusted operator saves, not participant uploads. Its file-existence check is not a filesystem security boundary. MATLAB execution and numerical export equivalence remain untested.

```sh
python3 decode_replay.py --author-export /private/decoder-export.json --output /private/replay.json
```

An optional `--candidate` uses `dentate-decoder-predictions-v1`: one model record for every fitted source cell/variable/value-set/event, exact trial order and time coordinates, the operator support hash, and a trial-by-time prediction matrix. The comparison returns per-bin weighted-accuracy differences. Hashes establish consistency with supplied exports, not scientific provenance. Keep exports, support hashes, labels and comparison reports private.

The replay rejects missing events/variables, duplicated or overlapping subgroups, altered trial/time support, unknown labels, unnormalized weights and mismatched first-column scores. It preserves empty insufficient-trial exclusions. It does not infer significant-cell fractions, fit models, regenerate folds, aggregate across cells/monkeys, or qualify candidate information conditions and uncertainty. Two monkeys remain the biological population; model, cell, trial and bin counts are not independent animals.

## Construction validation and integration

Twelve generated tests passed in shared-pool run `wave21-dentate-decode-replay-01`. They include an independently calculated imbalanced-class example where weighted accuracy differs from unweighted accuracy, malformed support/weights, null-column limitations, source exclusions and candidate pairing. No authentic neural arrays, author fits, MATLAB or scientific experiment were executed. Run the task-local suite with `python3 -m unittest discover -s tests -p test_decode_replay.py -v`.

The component needs an explicit component/CI registration by the integrator; file creation alone does not enroll it. Existing task, outcomes, improvement and reproduction contracts remain unchanged and source-unresolved. Full source-to-panel identity, original cohort/folds, native recipe, author numeric references and same-task superiority criteria still require qualification. Source observations and retained pins are recorded in `SOURCE.json`.
