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

## Complete retrieval cohort preparation

`native_cohort.py` composes the same metadata adapter over the original 18 participants, both learning categories (`object`, `scene`), and both retrieval blocks (`ret1`, `ret2`). It requires exactly those 72 cells before opening any metadata payload. It preserves every parsed row, source outcome code, exclusion reason, original and converted cue sample, and per-file byte/hash receipt. Session counts and participant summaries are preparation diagnostics, not decoding metrics.

```sh
python3 native_cohort.py retrieval-inputs.json retrieval-cohort.json
```

The input manifest has this structure; the abbreviated `sessions` list must be expanded to all 72 original cells:

```json
{
  "schema": "respiration-native-retrieval-cohort-inputs-v1",
  "data_kind": "authentic_public_source_metadata",
  "sessions": [
    {
      "participant_id": "P02",
      "category": "object",
      "block": "ret1",
      "recording_sample_rate_hz": 200,
      "behavior": "metadata/P02_object_ret1.txt",
      "markers": "metadata/P02_object_ret1.vmrk"
    }
  ]
}
```

The example paths and sample rate illustrate the interface; they are not authenticated source locators. Resolve them against the actual source inventory and continuous recording. Relative paths resolve from the manifest directory. Declare each recording's own sampling rate; no global rate or ret1/pre, ret2/post interpretation is inferred. For generated controls, use `generated_engineering_control`. Source cells may appear in any order; output uses the pinned participant, category and block order. Missing, substituted and duplicate cells fail, as do the existing single-session parser/join failures. An invalid session does not create a partial cohort output; an existing output or source file is never replaced.

The output is a **complete declared source-cell census**, not proof of authentic input identity or original trial completeness. Category and block remain manifest declarations; equal cue/behavior counts do not authenticate their positional join. No minimum label count, new exclusion, trial subsampling, localizer/retrieval split, or source-branch choice is added. The LMU archive's label masks are retained with their existing final-publication reconciliation hold. Both information conditions still require common authenticated inputs and matched exposure/budget protocols; this preparer does not create either protocol or establish reproduction or improvement.

`tests/test_native_cohort.py` exercises the complete generated 72-cell route, exact all-row retention including recognition misses/unknown outcomes, per-recording cue clocks and receipts, missing/duplicate/substituted cells, source errors, relative-path CLI use, and output preservation. Run both affected metadata suites with `python3 -m unittest discover -s tests -p 'test_native*.py'`. No authentic dataset, EEG extraction, respiratory-event detection, native MATLAB execution or AUC surface was tested by these controls.
