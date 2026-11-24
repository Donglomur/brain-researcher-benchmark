# Author workbook lineage inspection

The paper's author script reads `2022food_safe.xlsx`, range `A1:O274`, and uses
the first four columns for day, animal, sleep-session type and food condition.
The task's existing processed-event packet does not retain that complete
workbook lineage. This component inspects the exact released workbook without
loading neural observations or running the author analysis.

The reader checks the recorded byte length, publisher MD5 and saved SHA-256
before decoding the bounded OOXML container. It resolves the first worksheet
through workbook relationships, groups complete literal values and type categories, retains all
nonblank records within the author range and reports their animal/day groups. Within each group, `records` retains
the original worksheet row number together with its typed session and condition.
This keeps their association and source order: identical marginal totals can
otherwise hide different PRE/POST condition assignments. `rows` and the
existing group counts remain available. Missing values and numeric-versus-text
distinctions are preserved in each record; recording paths are not included.
Mixed conditions and missing values are retained. It rejects formulas in the
selected range, external relationships, macro/active content, duplicate cells
and unsafe or oversized containers. It neither runs spreadsheet formulas nor
converts dates according to guessed Excel or MATLAB import behavior.
Shared and inline strings normalize to the same text category; numeric and
textual conditions with the same displayed characters remain distinct.

The emitted report retains strings whose compact ASCII JSON representation is
at most 96 bytes. Longer values become explicit `value_identity` objects with
the full UTF-8 SHA256 and byte extent; their type and count remain separate.
Sheet/member names use the same bounded representation. Grouping and summary
indicators are computed from complete source values before projection. An
opaque digest cannot recover a label or establish source/figure equivalence.
Nothing is silently truncated. The report schema is
`food-ripples-workbook-lineage/v3`.

```sh
python3 -I -S -B inspect_metadata.py \
  --workbook /path/to/2022food_safe.xlsx --output workbook_metadata.json
```

The output path must be new. The original workbook is not modified or copied.
Recording paths are not emitted. Generated, in-memory controls run with:

```sh
python3 -I -S -B test_metadata.py
```

The report establishes source-metadata grouping only. Matching a
count of animals or days does not authenticate the corresponding MAT records,
the original chow/chocolate/Jello figure membership, detector revision,
PRE/POST recording separation or NREM rate denominators. This component does
not calculate a paper reproduction score or an improvement endpoint. Larger
biological effects and smaller p-values are not a method-performance win.

Source: [author release, Figshare version 1](https://doi.org/10.6084/m9.figshare.28691093.v1).
`MainAnalysisScript.m` lines 2–4, 10–29 and 80–104 define the metadata selection
and grouping used to motivate this inspection. The saved script and workbook
identities are recorded in `SOURCE_BINDINGS.json`.

The report bound is derived from the original range: at most 273 data rows
produce 2199 typed-value occurrences (eight per row plus 15 headers, including
two typed values for each row association). Each emitted
typed value including count is at most 192 bytes. Group scaffolding is bounded
by 273×128 bytes; row indices by 273×8; the at most 128 member descriptors by
128×320; record association scaffolding by 273×48; and fixed/top-level fields by 8192.
The resulting 521592-byte bound is
below the 512 KiB report cap. Generated controls exercise the maximum row and
member counts, long Unicode/escaped values, and typed identities. Stdout is a
separate receipt of at most 2 KiB containing numeric summaries and the report
hash, without duplicating label lists. These are output bounds, not a neural
data or scientific-analysis budget.

The new row associations are source metadata, not inferred experimental labels.
The author constructor reads session and condition from the same selected row
(`MainAnalysisScript.m` lines 22–28) and stores its condition after the row loop
(line 102). Inspecting the row-level values can expose ambiguity in that lineage;
it cannot resolve which released MAT records or paper panels they generated.
The report schema advances to v3 because `groups[].records` is now delivered.
No biological effect, full-panel coverage, or improvement eligibility changes.
