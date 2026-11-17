# NEURAL-078 public directory mode repair

The delivered producer now explicitly finalizes newly owned public directories to `0755` after constructing each public view. This makes nested inputs traversable by the selected nonroot reader under `umask 077`. Private host roots remain `0700`, private metadata remains `0400`, and existing public-file finalization remains `0444`. Descriptor ownership, type, identity and no-symlink checks fail closed. Owner write permission is retained so the existing retirement path can remove its view.

`REPAIR.json` records predecessor and current source identities. Historical derivation/provenance records remain unchanged; their earlier byte-identity statements describe their predecessor. Generated controls exercise real local file operations and controller preparation/retirement. They do not establish Docker behavior, authentic-data correctness, runtime qualification or scientific qualification.

Run the small generated control file with:

```sh
python3 -B benchmarks/neural/NEURAL-078/implementations/publication-mode-repair-v1/test_publication_modes.py
```

The historical outer manifest remains unchanged. The additive sibling `SOURCE_MANIFEST.json` selects the repaired current source and must be supplied explicitly to `verify_source.py --source-manifest`. Its identity is 6014 bytes, SHA256 `a681a439e234e2584fcc6797043d670791bc1939c54d25596819f7a5bc2d0637`. Central selectors and registered consumers require an integration successor before their existing tests select these bytes.
