# Neural epoch and regressor lineage prerequisite

This standard-library component checks **declared metadata alignment**, before source-space regression. It complements the behavioral source-statistic component; it does not compute EEG, likelihoods, regressions, reproduction scores or improvement scores. The task remains source-unresolved.

## Source question resolved narrowly

The pinned [author notebook](https://github.com/andlab-um/FreeEnergyEEG/blob/80418e5d1949631b0e2b54432e6b6956773c43da/code%20for%20data%20analysis/source_localization_and_linear_regression.ipynb) explicitly orders both EEG concatenation and behavioral regressors as participant 1, then 4 through 25. Its inverse helper specifies eLORETA. Response and covariance epochs have separate window/drop operations. Stage selection uses event labels; some second-result regressors delete flat row 719. These are browser-observed source instructions, not authenticated local notebook bytes or publication-linked execution evidence. See [PROVENANCE.json](PROVENANCE.json) for locators.

Under the declared 23-person, 120-trial block order, flat index 719 names participant 8, zero-based trial 119. This conditional arithmetic does not establish why the original event was absent, that every source regressor file has 120 rows, or that the saved notebook is the final analysis.

## Operator metadata interface

`audit_lineage(document)` accepts exactly the fields documented below. Use IDs from operator-maintained native records, never regenerate identities from an already truncated array's row numbers.

- `schema_version`: `freeenergy-neural-lineage/v1`; `task_id`: `PAPER-FIND-037`; `source_commit`: the pinned 80418e5d revision.
- `stage`: `first_choice`, `first_result`, `second_choice` or `second_result`. Event-code families are checked, but complete source selection predicates and their scientific eligibility are not inferred from those families.
- `behavior_rows`: all 2760 original declared identities, ordered by participant then zero-based trial. Each has `participant_id` and `trial_index`.
- `selected_behavior_indices`: unique, increasing indices into that complete reference. Every selected row must match its response epoch by participant/trial identity, not merely by array length.
- `response_events` and `covariance_events`: ordered metadata records with `participant_id`, `trial_index`, `event_index` and `event_code`. `event_index` means the original concatenated annotation index before any epoch rejection, not a current epoch ordinal.
- `omissions`: every unselected behavioral row, exactly once, with `behavior_index`, matching participant/trial identity, `reason` and `evidence_sha256`. Supported reasons are `source_stage_selection`, `epoch_rejection` and the narrowly identified `source_literal_719`. Hash syntax alone does not authenticate evidence or justify a removal.

**Covariance support may differ from response support.** The audit reports both counts and their event-set differences without changing either sequence. It rejects contradictory identities for a shared original event index. It does not impose a new rule requiring identical negative-time and response windows.

The metadata declares one stage at a time. Passing one stage does not establish the complete Figures 6–9 family, FDR family, sensor groups, source regions, amplitudes/power conventions or final EEG participant/trial exclusions. It also does not authenticate behavioral regressors, fitted parameters, original signals, or the proposed reason for any omission. All scientific/authentication/readiness flags remain false.

## Run and check

```sh
python3 -B lineage.py --input /operator/lineage.json --output /operator/lineage-audit.json
python3 -B -m unittest -v test_lineage
```

The CLI bounds JSON to 2 MiB, rejects duplicate keys/nonfinite tokens and creates a new output file. The result records the input SHA256. Keep operator metadata/results outside Git.

Ten distinct generated-metadata controls are covered across two bounded attempts: nine original checks passed, then four affected/new checks passed after correcting the covariance-support rule. The earlier support-equality design is superseded, with its test/cost history retained. No authentic arrays, EEG package imports, model fits or participant runs occurred. Maintained CI enrollment and independent integration review are still required.
