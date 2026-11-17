# Original Bugeon split recovery

This component recovers all nine Bugeon label/exposure split files from the
current public author archive without executing pickle constructors. It preserves
the original ordered neuron IDs, label-map rows, outer splits and CV arrays in
owner-side JSON. It supplies the missing source-to-JSON step for the existing
readout component. It supports future original-finding reproduction and
same-task improvement as separate outcomes; neither outcome has been run or
qualified here.

**The current E/I inductive file fails the original held-out-subject protocol.**
Its outer training set has 6,307 units from SB025, SB026 and SB030, and its test
set has 3,049 SB028 units. Each of its three CV training arrays also contains all
3,846 SB028 units: the entire test set plus 797 development-session units. The
pinned author evaluator uses these CV arrays directly. This is a defect in the
acquired December 2025 artifact relative to the registered inductive protocol;
it does not establish which splits produced the conference results.

`read_archive` preserves this ninth source projection for inspection and records
the mismatch. `select_readout_panel` rejects it. Neither function repairs the
split, intersects away held-out units, substitutes another panel, or generates
new folds. The other eight current files pass the existing structural protocol
validator; this is not eight qualified reproduction benchmarks.

| Label family | Label-map rows | Transductive test | Four transductive zero-shot test folds | Inductive test |
| --- | ---: | ---: | --- | ---: |
| E/I | 10,153 | 2,030 | 2,501 / 1,182 / 3,049 / 1,447 | 3,049; CV invalid |
| Five subclasses | 1,500 | 300 | 571 / 190 / 272 / 186 | 272 |
| Eleven classes | 1,491 | 298 | 570 / 187 / 270 / 185 | 270 |

Each label map covers all 17 source sessions. Within each label family, its
ordered label map is identical across the three current exposure panels.
Explicit source omissions are preserved only when they are in one of the four
documented development sessions. Session-local IDs do not prove repeated-cell
independence or their join to calcium columns.

## Source binding and format

The author repository is pinned to
[`0fa409b304147ace00507063d44f03155691af62`](https://github.com/nerdslab/nuclr/tree/0fa409b304147ace00507063d44f03155691af62).
The [split archive](https://ik.imagekit.io/7tkfmw7hc/nuclr/splits.zip) has 8,725,949
bytes, SHA256
`e168d754a2a9a281e66694aaa6a5e591cf337dceac0dbf198ae432ac8fb65d81`, and an observed
Last-Modified value of 14 December 2025. `source_audit.json` records every member
digest, ordered semantic hashes, counts, the CV-overlap audit, and authenticated
author-source file digests. ETag is not used as a content hash.

The parser in `inert_pickle.py` interprets a bounded stack grammar. `GLOBAL`
creates a symbol record, `REDUCE`/`NEWOBJ` create inert records, and `BUILD` saves
their state. It never calls a global, imports a name from source bytes, invokes a
constructor, or uses `pickle.load`. Unsupported opcodes fail closed. The source
reader then accepts only the observed object-string ndarray and single-column
DataFrame layouts. It validates both label axes and exact block placement.
Other encodings require an explicit new implementation, not a permissive loader.

The archive is read once with a byte bound; both its hash and ZIP reads use that
same buffer. Only the nine named Bugeon members are decompressed, each bounded to
2 MB. Array shapes, IDs, labels, collection lengths and operation counts are
bounded. The parser is not a general pickle compatibility layer.

## Use

Keep the archive and output JSON outside the repository because they contain
per-neuron source labels and memberships. In this construction wave, run all
commands through the reviewed shared test pool.

```sh
python source_splits.py "$SOURCE_ZIP" --owner-output "$OWNER_JSON_DIRECTORY" --summary "$SOURCE_SUMMARY_JSON"
python -m unittest discover -s tests -v
```

The CLI recovers source artifacts, including the invalid file with an explicit
audit. For a readout handoff, call `select_readout_panel` on the returned
projections; it reruns the unchanged topology validator and rejects the invalid
E/I inductive panel. It records the original Bugeon requirement
`required_readout_class_balance: resample`, as specified in the pinned author
evaluation README. This field is a source requirement, not enforcement of a
native readout: the preserved v1 evaluator still accepts its engineering
`weight` branch. A native reproduction or improvement protocol must bind the
author resampling branch explicitly.

Topology validation uses the existing v1 validator with an ephemeral generated
zero-feature matrix. It never calls fitting or metrics, and never writes that
matrix or synthetic validation receipts. The exported JSON contains only the
source projection and source audit. Its metadata identifies sessions/subjects
from source unit IDs; it is not a substitute for authentic metadata or a
fluorescence-column join. `project` by itself records only its supplied member
digest; only `read_archive` attaches the verified archive digest.

## Verified scope and remaining work

Nine generated controls exercise inert primitive parsing, executable reducer
nonexecution, unsupported/malformed opcodes, bounds, axis/order preservation,
unknown constructors, dtype rejection, exact archive pinning, and fail-closed
selection of a source split containing test labels in CV training. Actual
metadata-only recovery decoded all nine source members, found the E/I inductive
CV conflict above, and checked the other eight complete topologies. No
dependency was installed; no calcium data, representation model or readout was
run. Source payloads and per-unit JSON remain external.

The current archive is not established identical to conference-era splits.
Original calcium/metadata acquisition and joins, repeated-cell linkage,
author-matched resampling/runtime, five-seed native reference execution,
protected final evaluation and the paired paper-plus-data versus
paper-plus-data-plus-author-code conditions still need qualification. E/I
inductive additionally needs recovery of a conference-consistent fixed split;
the current file cannot be silently repaired for a reproduction claim. Its
stronger original LOLCAT comparator remains relevant to any future improvement
claim. Metadata/split redistribution terms remain unresolved.
