# NEURAL-100 public directory mode repair

The delivered producer now explicitly finalizes newly owned public directories to `0755` after constructing each public view. This makes nested inputs traversable by the selected nonroot reader under `umask 077`. Private host roots remain `0700`, private metadata remains `0400`, and existing public-file finalization remains `0444`. Descriptor ownership, type, identity and no-symlink checks fail closed. Owner write permission is retained so the existing retirement path can remove its view.

The same boundary also finalizes the captured source capsule, including `upstream/`, before its grader mount.

`REPAIR.json` records predecessor and current source identities. Historical derivation/provenance records remain unchanged; their earlier byte-identity statements describe their predecessor. Generated controls exercise real local file operations and controller preparation/retirement. They do not establish Docker behavior, authentic-data correctness, runtime qualification or scientific qualification.

Run the small generated control file with:

```sh
python3 -B benchmarks/neural/NEURAL-100/implementations/publication-mode-repair-v1/test_publication_modes.py
```
