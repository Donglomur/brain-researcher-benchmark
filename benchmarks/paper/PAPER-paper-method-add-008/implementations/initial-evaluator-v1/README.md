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
