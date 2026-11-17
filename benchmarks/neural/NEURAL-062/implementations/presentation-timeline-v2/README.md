# NEURAL-062 cross-table presentation boundary

This additive source component corrects a concrete admission error in the
registered extractor. Its next-presentation check looks only at the next row
of the current image table. A presentation at 1.0 seconds in one table can
therefore survive even when another image table contains an onset at 1.2
seconds, inside its unchanged POST window ending at 1.55 seconds.

`project.py` constructs the complete timeline of the image/omission tables
returned by the existing `nwb_source.presentations` adapter before applying
any event filter. It excludes a current row if the next onset is earlier than
the POST endpoint. An onset exactly at the half-open endpoint remains allowed.
Omitted rows and rows excluded for block, unknown context or invalid current
duration still bound earlier windows. IDs are paired with their table name;
IDs reused in separate NWB tables are not conflated. Duplicate times across
tables fail as ambiguous source metadata before neural or behavior reads.

The source authentication, published valid-ROI join, native dF/F and behavior
summaries, PRE/POST windows, feature counts, row-level exclusion categories,
mouse split, matched-support hierarchy and programme access mode are inherited
from the predecessor. This is a frozen-program preparation repair. It does not
deliver direct interpretation, viewer access or an interactive investigator.

## Scope and integration

Run the extractor in a fresh process with the same external dependencies and
exact pinned cohort required by the predecessor:

```sh
python3 -I -B project.py --source SOURCE.nwb --cohort COHORT.json \
  --experiment EXPERIMENT_ID --bytes EXACT_SOURCE_BYTES --output PROJECTION.json
```

The output uses `neural062_projection_v2` and binds both new modules and all
reused extraction dependencies. The predecessor's `prepare.py` deliberately
rejects this changed format/method. Programme integration must explicitly bind
the new generation after review; no existing projection, source lock, canonical
contract or registration is overwritten. The command itself is source code,
not permission to run native preparation without the programme's resource lease
and frozen protocol.

The original adapter enumerates image/omission tables only; it excludes
movie/spontaneous/trial tables. This repair establishes correct ordering within
that declared input domain. Authentic full-cohort schema and timing review
must still establish whether all relevant subsequent visual events are present
in that domain. No actual session support, native numerical projection, reference
fit, prediction, score, isolation or scientific qualification has been obtained.

## Evidence and controls

The source counterexample is grounded in the preserved local extractor's
`i + 1 < n` check and the multi-table return of `nwb_source.presentations`.
The original protocol fixes `next_presentation_must_not_precede` to 0.55 seconds.
Source identities reviewed for this repair:

| Preserved source | SHA-256 |
| --- | --- |
| `registered-runtime/source/private/extract.py` | `539ca9a054fb50ea4b6b8b2569c96f614eacf028b1857b16a3ef3c668aa976ae` |
| `registered-runtime/source/private/nwb_source.py` | `363ecf69e733fae907f474fa83306e913338717f964228afdb97f9d5d695a27e` |
| `registered-runtime/source/private/protocol.py` | `e02a6c6b93e2c4f2c8bfd4792ee7d1318a41fc5cf83092f1011dc67ea9234ea4` |
| `registered-runtime/source/public/PROTOCOL.json` | `0aa159248ca1df7edffe37cbf567f8d5a551317b03212917c27faa70d76f45cd` |

`test_timeline.py` uses generated clocks and exercises the actual replacement
projection's admission and census code with source I/O and numerical helpers
stubbed. It checks interleaved tables, legal ID reuse, table-order invariance,
strict clocks, exact half-open boundaries, exclusion-independent timeline
construction, and failure before numerical reads. These are software controls;
they do not test native HDF5 decoding, source hashing or physiological values.
Run them under the shared bounded test pool. No new source download is needed.

The eight generated controls passed on 2026-11-17 under pool run
`neural02-n062-controls-03`: 0.068797 child CPU seconds and 28,934,144 bytes
reported child peak RSS. Three earlier attempts found the pool busy and launched
no child. This result establishes the tested software behavior only.
