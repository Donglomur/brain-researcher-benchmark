# BANC Figure 2e artifact witness

This inactive component checks that an explicitly supplied, complete source CSV
and saved same-versus-different report agree on their artifact identities,
declared metric, group counts, direction and W statistic. It adds report binding
to the accepted sensory-effector inspector; it does not rerun the connectome
analysis or replace the benchmark's scientific scorer.

The retained script extracts 14 diagonal and 182 off-diagonal matrix entries,
runs a one-sided Wilcoxon rank-sum test (`same > different`), and writes the
`influence_log_minmax_same_vs_different_body_part_test.txt` report. Its comment
identifies W with U. This component compares that reported W to the exact
half-integer pairwise U of the supplied, parsed finite values: count each
same-greater-than-different pair as one and each cross-group tie as one half.
It never calculates a p-value or selects R's inferential defaults.

There is **one biological specimen**. The 196 matrix entries are observations
sharing that connectome, not 196 animals. This is the pooled matrix comparison,
not the later cell-type/per-body-part tests with Holm adjustment. No 17-by-19
to 14-by-14 selection or normalization is inferred here.

## Inputs and use

Supply all three explicit artifacts:

1. The original `influence_log_minmax_body_part_similarity_data.csv` containing
   every ordered pair of the 14 source-defined body parts. The accepted
   `sensory-effector-result-inspection-v1/inspect_results.py` dependency checks
   columns, labels, diagonal flags, complete support and cosine consistency.
2. The saved report from the retained script's lines 780–811, including its
   entire 23-line structure. The metric, 14/182 counts, one-sided direction,
   single-test statement and W are checked. p is retained as opaque reported
   text. Rounded summaries, effect text and the legend are retained as
   explicitly unverified text, even when they contradict the numeric values.
3. A binding JSON with exactly the fields below. Byte counts and SHA256s for
   the CSV and report are checked against the supplied bytes. Input and producer
   receipt descriptors are required declarations; their actual bodies are not
   read or authenticated by this component.

```json
{
  "schema": "banc-figure2e-artifact-binding/v1",
  "metric": "influence_log_minmax",
  "source_commit": "2e78ce38e946ab80e120a42f504a019b3a567fef",
  "source_panel_sha256": "76149a9bea40688bdef0d2867c9c63ce22cc11d16a0b06d50c03cc461b4581df",
  "inspector_sha256": "95855f4fdb513ccef63979fdfb7d2cb759c27df7dae480ee412f991522b40285",
  "input": {"bytes": 1, "sha256": "<actual input descriptor>"},
  "producer_receipt": {"bytes": 1, "sha256": "<actual producer receipt descriptor>"},
  "csv": {"name": "influence_log_minmax_body_part_similarity_data.csv", "bytes": 1, "sha256": "<actual CSV hash>"},
  "report": {"name": "influence_log_minmax_same_vs_different_body_part_test.txt", "bytes": 1, "sha256": "<actual report hash>"}
}
```

The placeholder values above are intentionally not an executable fixture.
After both additive components are integrated, run:

```sh
python -B result_witness.py source.csv source-test.txt binding.json
```

The inspector is loaded from the sibling component by default. Private review
may set `BANC_INSPECTOR_PATH` to the already accepted private postimage. Its
exact bytes and SHA256 are checked before those same bytes are executed; an
arbitrary replacement is refused. Inputs have bounded reads: CSV 256 KiB,
report 16 KiB and binding 8 KiB. The CLI writes JSON to stdout only.

## Interpretation and limitations

A passing witness establishes internal consistency of supplied artifacts and
the rank statistic computed from their serialized operands. Declarations and
hashes supplied together cannot authenticate an author run. An altered CSV and
a correspondingly altered report can still pass; the result explicitly marks
producer/input lineage as unauthenticated. External trusted producer receipts,
actual source inputs and data-version admission remain necessary.

W agreement does not establish R runtime parity, especially if serialization
changed a tie or the source's native arithmetic differs from the accepted
inspector's stable arithmetic. The report's p, medians/IQR/ranges, effect text,
timestamp and legend are not scientifically verified. The exact report layout
is intentionally narrow and may refuse formatting from another runtime/release.

The paper's reported W=2535.5 and P=3.49e-10 are published references, never
success thresholds. Higher W or lower p is not an improvement criterion.
Deposited v2.0.5 versus retained 2e78 source correspondence, original data/output
authentication, ED4b branch identity, native numerical reproduction and the
canonical improvement endpoint remain unresolved. No readiness, reproduction
or superiority outcome is awarded. The component adds no benchmark count.

## Generated controls and integration seam

`test_result_witness.py` contains 15 new methods covering direction reversal,
all ties and a single cross-group tie, stale/altered artifact identities, wrong
W/metric/source/filenames, missing or duplicate support, ambiguous reports,
untrusted provenance and exact dependency loading. These are generated fixtures,
not empirical results. The inherited inspector tests are not replayed.

Proposed CI command, only after sole-integrator enrollment and dependency import:

```sh
python -B -m unittest discover -s benchmarks/paper/PAPER-FIND-NEW-003/implementations/figure2e-result-witness-v1 -p test_result_witness.py
```

No central authority, task contract, outcome binding or source-refresh record is
changed by this package. The sole integrator must check destination absence,
the exact accepted inspector dependency and source-refresh enrollment against
the final composed tree.
