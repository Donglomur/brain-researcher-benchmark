# N006 row-eligibility checker

This standard-library Python component compares complete model-row records
against independently recomputed missing-data masks. It catches cases where
the sample count agrees but the retained rows differ.

The schema describes eight processed exports and eleven named models. The
default cohort is 41 people with 180 ordered trials each (7,380 rows per file).
The component reads a supplied JSON record; it does not read CSV or RDS files,
run R, fit a model, or verify that the record came from those original files.
The included tests use two invented people and contain no authentic data.

## Row-coordinate calculation

All row indices are one-based. Let `F` be the increasing original row indices
remaining after the supplied author-filter omissions. For each model, let
`M` be the union of original row indices missing any declared formula variable.
The expected model-frame rows are:

```text
J = [j in 1..len(F) where F[j] is not in M]
expected original source rows = [F[j] for j in J]
```

The checker compares `J` with both reconstructed and saved model-frame rows,
and compares `F[J]` with saved original-source rows. It separately checks
omitted positions, omission class, observation/group counts and supplied
formula-match flags. It also compares the saved source/filter/person ordering.
A mismatch remains visible; the checker does not reorder data to make it pass.

## Run the invented controls

Use Python 3.11 with its standard library. From this directory:

```sh
python3 -I -S -B -c 'import sys, unittest; sys.flags.optimize == 0 or sys.exit("Tests require optimization disabled"); sys.path.insert(0, "."); suite = unittest.defaultTestLoader.loadTestsFromName("test_row_eligibility"); suite.countTestCases() == 16 or sys.exit("Expected exactly 16 tests"); result = unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not (result.testsRun == 16 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses))'
```

This requires all 16 tests, optimization disabled, no skipped tests and no
expected-failure substitutions. It needs no data download, package installation,
R or Docker.

The controls exercise nontrivial masks with independently stated expected row
lists; original/post-filter offsets; same-count wrong subsets; reconstructed and
saved frame disagreements; filter/person swaps; missing or reordered models,
files and variables; duplicate or boolean indices; changed omission policy;
formula/group disagreement; parse/nonfinite holds; zero-omission cases; strict
JSON parsing; input immutability; and summary omission of person identifiers.

The code and test bodies are unchanged from the reviewed component. This public
projection was prepared without running tests; no new test pass or authentic
scientific result is claimed here. The path-filtered workflow runs the command
above with a 35-second process deadline and three-minute job limit, retains
complete stdout/stderr/exit status for seven days, and propagates failure.

## Use the checker

The module exposes `strict_json(body)` and
`audit(wire, expected_people=41, trials_per_person=180)`. It has no command-line
entry point. For a separately prepared record matching the default cohort:

```sh
python3 -I -S -B - <<'PY'
import json
from pathlib import Path
import runpy

api = runpy.run_path("row_eligibility.py", run_name="_row_checker")
wire = api["strict_json"](Path("row-record.json").read_bytes())
detailed, summary = api["audit"](wire)
print(json.dumps(summary, indent=2))
PY
```

The complete small invented record is `fixture()` in
`test_row_eligibility.py`; its `checked()` function demonstrates the
`expected_people=2, trials_per_person=3` overrides. These optional dimensions
are available through the Python API and do not enforce a benchmark cohort.

`audit` returns a detailed report and a summary. The detailed report retains
person identifiers and exact row sets; keep it in the appropriate private
workspace. The summary omits those identifiers and row sets, but still contains
cohort and exclusion counts. Whether such aggregate counts may be shared
depends on the input's permissions.

The function operates in memory and does not impose file-size, memory, timeout
or isolation limits. The example reads the named file in full. Use trusted,
appropriately bounded records and an external evaluator if resource containment
or protected candidate execution is required.

## Input record

The top-level object has exactly `schema`, `source`, `runtime`, and `models`.
The schema is `neural006-original-row-eligibility-wire-v1`. Extra or missing
keys are refused. Use `strict_json` before `audit`: it refuses duplicate keys
and nonfinite JSON constants.

The exported `FILES` tuple gives the required order:
`BEH_ug.csv`, `df_FRN_N2_offer.csv`, `df_P2_offer.csv`,
`df_P2_base.csv`, `df_P3a_offer.csv`, `df_P3a_base.csv`,
`df_P3b_offer.csv`, `df_P3b_base.csv`.

The `source` object has these exact fields:

| Field | Meaning |
| --- | --- |
| `files` | Eight ordered objects with `name`, `rows`, unique nonempty `columns`, and `parse_problems`. These are supplied inventory claims, not opened files. |
| `subjects`, `trial_global` | One person string and integer trial number for each original row. Each person's encountered trials must be exactly 1 through the declared trial count. |
| `author_filter_missing_rows` | Increasing unique original row indices removed by the first filter. |
| `saved_original_rows` | Saved original row indices, compared with the complete 1..N range. |
| `saved_subjects`, `saved_ordered_people` | Saved person sequence and first-appearance roster, compared with the current supplied sequence. |
| `saved_author_filter_source_rows` | Saved first-filter support, compared with independently recomputed `F`. |

`runtime` has exactly `na_action`, `R`, `platform`, and
`package_versions`. `na_action` must equal `"na.omit"`; the package-version
mapping must name `readr`, `dplyr`, `lme4`, and `jsonlite`.
The strings report the producer's claims; the checker does not authenticate a
runtime or select historical package versions.

`models` must contain all 11 records in the exact order of the exported
`MODELS` tuple, including its exact variable lists. Each model has:

| Fields | Meaning |
| --- | --- |
| `name`, `variables` | Literal model identity and ordered formula-variable list. |
| `missing_rows_by_variable` | A complete variable-to-original-row-list mapping. |
| `nonfinite_rows_by_variable` | Original rows with nonmissing nonfinite values; disjoint from missing rows for the same variable. |
| `native_frame_rows`, `native_omitted_rows` | Reconstructed positions in the post-filter frame. |
| `native_na_action_class` | `[]` or `["omit"]`, compared with the independently derived omission set. |
| `saved_frame_rows`, `saved_source_rows` | Saved post-filter positions and original-row identities. |
| `saved_nobs`, `saved_group_count` | Saved observation and person counts. |
| `saved_formula_matches` | Producer-supplied Boolean formula comparison; no formula AST is parsed here. |

Row lists must be increasing, unique integers in range; Boolean indices are
refused. Person strings are nonempty and at most 128 characters. The fixture
shows every required field and the checker defines the complete validation.

## Results and limits

Malformed records are rejected. Schema checks use `ValueError`; malformed field types can also raise `TypeError`. Validly structured comparisons
retain findings across all models. The summary is `consistent` only when all
source comparisons and all 11 model comparisons agree, with no parse problems
and no nonfinite values in retained modeled rows. Otherwise it is
`inconsistent_or_held`. There is no forced target exclusion count.

A consistent supplied record does not establish its provenance or independent
ERP-event alignment, raw preprocessing or scaling correctness, exclusion
causes, historical omission settings, statistical inference, publication parity,
or full-paper reproduction. The native extraction and authenticated input
pipeline are separate and are not distributed here. This component supplies
no protected evaluation, real-data benchmark score, model-performance result,
new benchmark registration, or scientific qualification.
