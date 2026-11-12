# Public source integrity checks

The GitHub workflow checks only the packages explicitly enrolled in
`benchmarks/source_integrity.json`: Morse EEG, cerebellar contact prediction,
and Neuroformer. It does not run benchmark modules, load neural data, download
models, or assess scientific qualification.

The standard-library checker verifies each declared source byte length and
SHA-256, rejects missing and unexpected package files, checks the manifest's
canonical and inventory bindings, and parses Python syntax without importing
the code. It rejects duplicate JSON keys, duplicate or ambiguous paths, path
traversal, symlinks, nonregular files and files outside the explicit package.
Reads are bounded to 1 MiB per member and 16 MiB in total.

Existing package inventories are authoritative for their declared members.
The registry pins any remaining public notices or manifest bodies and accounts
for the inventory itself. Changing a covered source file requires updating its
inventory; changing a supplemental file requires updating the registry. New
packages require an explicit registry entry.

Neuroformer's explicitly enrolled `complete_inventory` profile adds six exact
registry pins while retaining the original 95-row task inventory and manifest.
The registry authenticates `NATIVE_FACTORY_API.json`; the API never authenticates
itself or chooses its own checker profile. Its 102 unique rows plus the excluded
API must equal the complete 103-file census. The checker verifies both schemas,
typed counts, total row bytes, exact hashes, closed row fields and literal
`100644` modes with actual `0644` file permissions. The old inventory remains a
separate checked layer; its count is not changed to 103.

The selected profile also checks the V2 and historical V1 entry declarations
against top-level function definitions using Python ASTs, selected inactive and
unchanged-dispatch declarations, and the retained 46/85/7/6/20/29 scope counts.
Those checks do not establish arbitrary-code compliance or native correctness.
The earlier 89-row operator and 86-row source inventories remain byte-covered;
this extension does not independently interpret their semantics. Manifest
operator/API/qualification-reference semantics beyond the existing canonical
and source-freeze checks are not added by this profile. A new or different
profile requires an explicit reviewed checker and registry change.

Run locally with Python 3.11:

```sh
python3 -I -S -B -m unittest discover -s tools/tests -p test_neuroscience_source_integrity.py
python3 -I -S -B tools/check_neuroscience_source_integrity.py
```

A passing check establishes source consistency for the enrolled bundles.
It is not an independent review of scientific methods, a guarantee against
coordinated changes to both source and hashes, or a filesystem/process sandbox.
Benchmark admission flags and scientific holds are not promoted by this check.
The workflow uses read-only repository permissions and pinned GitHub actions.

