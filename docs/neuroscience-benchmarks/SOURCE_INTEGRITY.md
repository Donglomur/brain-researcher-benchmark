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
packages require an explicit registry entry. A future add-on needs a coherent
inventory arrangement before it can pass the complete-package census.

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

