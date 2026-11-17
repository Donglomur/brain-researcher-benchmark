# Current FIND050 source commands

Use the [programme package](../implementations/paper-find050-programme/README.md)
for the complete declared source scope: 26 operations, 40 dense 10,000-mode
spectra, 29 main sessions, both paper/data access conditions and the separate
prospective memory endpoint. The [registered task](../task.json) remains
authoritative. Source verification and generated checks do not establish a paper
reproduction, native deployment or scientific qualification.

The package's original `SOURCE_MANIFEST.json` and README are preserved. The
current numerical repair is selected through a separate
[current manifest](../../../integrity/current-closures/numeric-find050/SOURCE_MANIFEST.json)
and [source-binding record](../../../integrity/current-closures/numeric-find050/SOURCE_BINDINGS.json).
Use `--current-manifest` for this revision. The historical-manifest route refuses
the changed source; replacing its original pins would erase the predecessor
record.

## Verify, describe and check

Use a trusted Python 3.11 interpreter on a POSIX system. The source commands need
only the standard library. Before executing `package_tools.py`, authenticate that
bootstrap and the current manifest against an independently reviewed release
record. A descriptor read from an untrusted replacement tree cannot authenticate
that tree by itself.

Run from the repository root at a canonical absolute path without symlink
ancestors. Replace `REVIEWED_CURRENT_BYTES` and `REVIEWED_CURRENT_SHA256` below with
the current manifest's independently recorded byte count and SHA-256, not the
historical manifest's values or a hash freshly calculated from an untrusted file.

```sh
FIND050_PACKAGE="$PWD/benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme"
FIND050_MANIFEST="$PWD/benchmarks/integrity/current-closures/numeric-find050/SOURCE_MANIFEST.json"
FIND050_BYTES=REVIEWED_CURRENT_BYTES
FIND050_SHA256=REVIEWED_CURRENT_SHA256

python3.11 -I -S -B "$FIND050_PACKAGE/package_tools.py" verify \
  --root "$FIND050_PACKAGE" --current-manifest "$FIND050_MANIFEST" \
  --manifest-bytes "$FIND050_BYTES" --manifest-sha256 "$FIND050_SHA256"
python3.11 -I -S -B "$FIND050_PACKAGE/package_tools.py" describe \
  --root "$FIND050_PACKAGE" --current-manifest "$FIND050_MANIFEST" \
  --manifest-bytes "$FIND050_BYTES" --manifest-sha256 "$FIND050_SHA256"
python3.11 -I -S -B "$FIND050_PACKAGE/package_tools.py" check \
  --root "$FIND050_PACKAGE" --current-manifest "$FIND050_MANIFEST" \
  --manifest-bytes "$FIND050_BYTES" --manifest-sha256 "$FIND050_SHA256"
```

`verify` checks the current source bytes, unchanged predecessor manifest and
complete member roster. Scientific contracts and `PREREQUISITES.md` must retain
their historical identities. `describe` reports the operation roster and the
32 open scientific/runtime gates. `check` executes software controls on generated
inputs; their output is software evidence rather than biological performance.
Failed, skipped, expected-failure or unexpected-success controls refuse successful
completion.

The package tree remains closed. Keep the current manifest outside it, and put
logs, caches, environments, official source and runtime outputs elsewhere. Unknown
members, symlinks and hard links are refused. A successful source check does not
establish protection against a concurrent filesystem writer.

## External official source

The same current-manifest selection applies to `dependencies` and `verify-author`:

```sh
python3.11 -I -S -B "$FIND050_PACKAGE/package_tools.py" dependencies \
  --root "$FIND050_PACKAGE" --current-manifest "$FIND050_MANIFEST" \
  --manifest-bytes "$FIND050_BYTES" --manifest-sha256 "$FIND050_SHA256"
python3.11 -I -S -B "$FIND050_PACKAGE/package_tools.py" verify-author \
  --root "$FIND050_PACKAGE" --current-manifest "$FIND050_MANIFEST" \
  --manifest-bytes "$FIND050_BYTES" --manifest-sha256 "$FIND050_SHA256" \
  --author-root /ABSOLUTE/ordinary/external-selected-author-source
```

`dependencies` prints the exact 18-file exposure roster. The optional
`verify-author` command reads that already acquired external source, including the
two selected notebook-code drivers, without downloading, importing or copying it.
Its root must be ordinary, canonical and disjoint from the programme package.
It must contain exactly the printed relative roster, without the `author/`
prefix, and no extra files.
The separate 13-module native capture roster has its own role; neither roster may
be shortened to make a check pass. Exact extraction, rights and runtime
compatibility remain separate requirements.

For an independently admitted live operator, the source API also takes the
explicit current selection. Run this inside the qualified operator's trusted
entrypoint, with module lookup configured from the authenticated package:

```python
from package_tools import verify

package = verify(
    package_root, reviewed_current_bytes, reviewed_current_sha256,
    current_manifest=current_manifest_path,
)
```

This only obtains the verified source object. The existing live-operator API in
the preserved package guide still requires the original issuer, complete native
plans, protected references, qualified runtime and resource enforcement. There is
no native-run CLI or generic provisioning command in `package_tools.py`. Consult
[the prerequisites](../implementations/paper-find050-programme/PREREQUISITES.md)
and [the transport design](../implementations/paper-find050-programme/source/README.md)
before selecting an actual operation. This guide supplies no execution authority
or new scientific result.
