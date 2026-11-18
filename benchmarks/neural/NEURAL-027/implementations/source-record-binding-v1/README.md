# Original record and condition binding

This operator component connects the complete accepted `Imaging_Exp_info.npy`
metadata export to original file and behavior dictionary addresses. It preserves
all 142 records, their source order, typed fields and IEEE nonfinite bit patterns.
It never opens NPY/NPZ, executes author code, selects a cohort or creates predictions.

The source contains 89 physical recording stems and 33 stems appearing in multiple
records. The adapter preserves each original condition while retaining the original
mouse/date/block tuple. Its record identifiers are custody identifiers, not new
mouse identities, session filenames, samples or evaluation item IDs.

Run the portable public controls using Python's standard library:

```sh
python3 -I -S -B test_source_record_binding.py
```

With the already accepted metadata JSON export and original inventory available:

```sh
python3 -I -S -B source_record_binding.py \
  --export /path/to/metadata-export.v3.json \
  --inventory /path/to/find-rep-007-inputs.json \
  --output /path/to/new-source-binding.json
```

The CLI authenticates both exact input hashes before binding. It refuses changed
or truncated populations, inconsistent source pointers, invented identities and
inventory substitutions. Output is bounded to 512 KiB and existing output files
are never overwritten. In this construction programme, run controls and metadata
binding through the existing bounded two-slot pool; the CLI itself is portable.

The result contains every original typed record, the precise group-scoped behavior
key, a source-field map for eventual numeric safe export, dependency links by
literal mouse/stem/asset/group/condition address, and all 297 original inventory rows.
Each asset has its referring record ordinals. Storage totals count each file once;
unjoined files remain explicitly accounted for. Filename joins do not verify payload
equality or prove that the joined files are scientifically sufficient.

The current `initial-evaluator-v1` plan accepts only unique physical session stems.
The full original roster cannot enter that schema unchanged. This component emits
an explicit compatibility stop, not a five-field plan or safe NPZ. It does not alter
the existing consumer, manufacture suffixed mouse/session identities, drop repeated
conditions or transfer target descriptors between sources. A later condition-aware
consumer decision must retain shared recording and animal dependencies.

`source_contract.json` records the primary-source anchors. Behavior `stim_id`,
`UniqWalls` and `ft_WallID` jointly define target identities. Original metadata
`stim_id` is a separate descriptor whose relationship to behavior labels remains
unknown. Its NaNs stay typed and byte-exact; they do not become missing labels.
The exact behavior key, condition frame support, neural frame alignment, area
alignment and position units must be verified before safe numeric export.

No record is marked prereward from `before_learning`, `rewType` or an unrewarded
test stimulus. The paper's separate behavior-only pretraining cohorts cannot supply
the imaging records' missing chronology. All phases, splits and eligibility values
remain unset. Literal mouse identifiers are preserved for the existing mouse-level
scoring policy; biological alias identity and uncertainty choices remain unresolved.

This is preparation for a tools/programme benchmark. It provides no evidence of
native model understanding, scientific reproduction or improved performance.
