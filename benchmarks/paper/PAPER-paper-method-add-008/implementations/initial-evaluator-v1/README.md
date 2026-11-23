# Modular spike-sorting curation component

Reconstruct the pinned paper's four-sorter curation table from complete native label exports, and stream the Kilosort4 Bombcell-`good` spike raster. Outputs preserve all-unit denominators, both curation distributions, proposed SLAy group counts, and artifact hashes.

Requires Python 3 with its standard library; no installation or native sorter dependency is needed for these generated engineering checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 example_control.py /tmp/modular-sorting-input
python3 evaluator.py \
  --owner-manifest /tmp/modular-sorting-input/owner-manifest.json \
  --expected-manifest-sha256 "$(cat /tmp/modular-sorting-input/manifest.sha256)" \
  --curation-json /tmp/modular-sorting-input/curation.json \
  --drift-spikes-csv /tmp/modular-sorting-input/all-kilosort-spikes.csv \
  --output-directory /tmp/modular-sorting-output
```

Run from this directory; use new example and output directories. Generated inputs contain explicit placeholder native identities and resources. Authentic use requires an independently owner-frozen manifest and audited native exports.

This is a complete post-native analysis component, not a native sorter runner or a scientifically qualified benchmark. Source A3702 filename binding, preprocessing comparability, dependency/model qualification, numerical drift and cross-sorter agreement, rights/exposure and protected references remain open. Quality and yield are not spike accuracy. Reports always preserve those limits.

See the [task documentation](../../docs/initial-evaluator-v1.md) for input schema, exact scope, primary-source mappings, source defects and trust boundaries.

## Prepare indexed native curation results

`prepare_exports.py` bridges already-computed native curation results to the
existing JSON input. The [pinned author curation script](https://github.com/SpikeInterface/sorting_components_benchmark_paper/blob/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/notebooks/real_data_figure/generate_curation_data.py#L37-L59)
computes separate Bombcell and UnitRefine label tables and SLAy groups, then saves
aggregate counts. Retain the per-unit outputs before that aggregation: the
published aggregate CSV cannot reconstruct individual labels or exact-good
raster membership.

For each of the four source sorters, supply these already-computed values:

```python
native_results[sorter] = {
    "native_unit_ids": analyzer.unit_ids,
    "bombcell_labels": bombcell_table["bombcell_label"].items(),
    "unitrefine_labels": unitrefine_table["unitrefine_label"].items(),
    "slay_merge_groups": slay_groups,
    "native_artifact_sha256": audited_native_artifact_sha256,
}
# Only after collecting all four independently audited results:
from prepare_exports import write_curation_exports
curation_digest = write_curation_exports(
    owner_manifest, native_results, independently_supplied_manifest_digest,
    "/absolute/operator/new-curation.json",
)
```

Each label iterable contains `(native_unit_id, label)` pairs, such as a native
pandas Series' `.items()`; each native index must identify the same units as its
analyzer. Confirm this against the qualified dependency before authentic use.
The bridge aligns by ID even when the two tables have different row orders,
requires every frozen unit exactly once, and preserves successful empty sorters.
Integer native IDs become decimal strings in JSON; string IDs stay unchanged.
Booleans, floats, duplicate IDs, integer/string collisions and changes of native
ID type between the analyzer and a table are rejected. Do not first coerce IDs
or zip table rows together. One-shot iterables are consumed once.

The bridge preserves source labels and SLAy groups and validates its output
through `evaluate_curation`. Output follows owner unit order, binds the existing
native artifact hashes, and is accepted by `evaluator.py --curation-json`.
Validation and serialization finish before a new output file is opened; an
existing destination is never overwritten. This helper does not generate the
owner manifest, recompute curators, verify native hashes against artifacts,
export spikes, or establish source/dependency fidelity. All existing population,
model, execution and scientific-qualification holds remain in force.

Nine generated preparation controls cover shuffled indices through the exact-good
raster, missing/duplicate/foreign units, label validation, complete comparators,
integer IDs and consumed iterators, lossy conversions, empty sorters, preserved
holds, native hash/group policy, and JSON output behavior. They run with the
existing standard-library test discovery command above; no native models or
recordings are loaded.
