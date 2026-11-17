# Native retrieval metadata admission

`native_trials.py` reads the original 19-column retrieval behavior log and BrainVision marker file without opening EEG arrays. It produces a complete session census with stable trial identities, source numeric outcome codes, original cue samples, and the exact Figure 3a label masks. It is a preparation component, not an EEG exporter, author baseline, or improvement scorer.

The source is the existing [LMU 596 code archive](https://data.ub.uni-muenchen.de/596/5/code.zip), SHA-256 `22f245506d4c8a87887e1bd6cfbb47c133223fa5c2989963c27449bc0fcdcd1c`. The implementation is newly written; no author code is redistributed. Archive source has CC BY-NC-SA 4.0 terms. The precise inspection and limitations are recorded in [the source audit](source-audit.md).

```sh
python3 native_trials.py retrieval1_subject.txt recording.vmrk admission.json \
  --participant P02 --category object --block ret1 \
  --recording-sample-rate-hz 200 \
  --data-kind authentic_public_source_metadata
```

Store the output outside the repository: it contains trial labels and source metadata. The provenance declaration is supplied by the operator and does not authenticate the data. The output is created exclusively; an existing file is never replaced. No optional dependency is required.

The adapter preserves all rows. `label_group` is `remembered` only for `OldNew == 1` and `ExemplarAccuracy == 1`; it is `not_remembered` only for `OldNew == 1` and `ExemplarAccuracy == 0`. Other codes remain in the census with an explicit exclusion reason. `Answer1Accuracy` is preserved but is not an additional selection filter. This distinction prevents unknown outcomes from being collapsed into the complement of a remembered boolean. It also prevents dropping recognition misses from the source's nonremembered mask.

Category is the declared learning session (`object` or `scene`), not guessed from the image name. IDs qualify participant, category, retrieval block, source `Run`, and source `TrialNumber`. The nth metadata row is joined to the nth literal `S 41` marker, matching the source's positional assumption. Count mismatches, duplicate identities, wrong participants, reordered cue samples, malformed integers and changed headers fail explicitly. Equal counts do not prove that the join is correct; EEG/event reconciliation remains necessary. Floating-point behavioral fields are retained as their original numeric text, including `NaN`, so missing response times cannot silently exclude an otherwise eligible trial. They are not used for class admission.

The source helper converts positive one-based 1000-Hz marker samples using `round(sample / 1000 * data_ret.fsample)`. Declare the authentic continuous recording's sample rate explicitly (`200` in the example); the adapter does not authenticate that declaration. It preserves both the converted and original samples and does not insert an unrecorded zero-based offset. No `ret1`/`ret2` to pre/post mapping is inferred.

The 19-column header is verified against the names/order in the author helper. The archived helper itself merely skips one header line. This adapter's stricter check is an engineering guard; authentic header compatibility has not been tested. Text decoding is UTF-8 only. A different authentic encoding or header requires evidence and an explicit update, not silent guessing.

`tests/test_native_trials.py` contains generated controls for the exhaustive outcome-code truth table, cue rounding, complete census retention, identity isolation, malformed inputs, missing response times, and the actual CLI's refusal to overwrite evidence. Generated checks cannot establish authentic preparation or native MATLAB parity.

The original 18-person cohort, independent localizer training, all original eligible retrieval trials, ROC AUC time-generalization support, and participant-level comparison remain required. This component does not make a new participant split or use outcome significance as a performance score. The final article/source version, respiratory-event extraction, full cohort inventory, dependencies, author AUC results, and frozen improvement comparison remain unresolved.
