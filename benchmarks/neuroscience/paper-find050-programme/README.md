# PAPER-FIND-050: complete programme source

This package implements the operator, reference-worker transport, scientific
consumers and scorers for **A critical initialization for biological neural
networks**. It preserves all 26 operations, 40 complete 10,000-mode connectivity
spectra, 29 main sessions, the two paper/data access conditions and the separate
prospective memory endpoint. All 32 scientific/runtime gates remain open.

The package is usable for source verification, generated engineering checks and
integration into an independently qualified live operator. It is not a qualified
native deployment, a historical reproduction result, a model result, or another
benchmark ID. There is no native-run command that turns JSON into authority.

## Verify and inspect

Python 3.11 with its standard library is sufficient for these source commands on
POSIX systems. No install, download, numerical library, model or dataset is needed.
Use a fresh interpreter and a canonical absolute path with no symlink ancestors.
The package tree is closed: no extra files, caches, hard links or symlinks inside.
Keep logs, environments, external author code and runtime outputs elsewhere.

Obtain `REVIEWED_BYTES` and `REVIEWED_SHA256` for `SOURCE_MANIFEST.json` from the
independent release record. The interpreter and this initial `package_tools.py`
bootstrap must already be trusted; a file cannot authenticate its own execution.
For example, after publication at `benchmarks/neuroscience/paper-find050-programme`:

```sh
PKG=/absolute/ordinary/path/benchmarks/neuroscience/paper-find050-programme
python3.11 -I -S -B "$PKG/package_tools.py" verify --root "$PKG" \
  --manifest-bytes REVIEWED_BYTES --manifest-sha256 REVIEWED_SHA256
python3.11 -I -S -B "$PKG/package_tools.py" describe --root "$PKG" \
  --manifest-bytes REVIEWED_BYTES --manifest-sha256 REVIEWED_SHA256
python3.11 -I -S -B "$PKG/package_tools.py" check --root "$PKG" \
  --manifest-bytes REVIEWED_BYTES --manifest-sha256 REVIEWED_SHA256
```

Replace the two pin placeholders with that reviewed release's literal values.
Verification requires every declared UTF-8 file and refuses unknown members.
`describe` reports the full operation roster and all gate requirements from the
authenticated contracts. `check` runs the 17 accepted author engineering methods,
8 accepted peer methods and the new packaging methods. These are generated
controls, not scientific experiments. Fork, cgroup effects and scientific
kernels remain inert in the inherited controls; local socket/pipe framing runs.
Any failure, skip, expected failure or unexpected success produces nonzero exit.

The source loader compiles authenticated captured Python bytes and refuses
preloaded `critical` modules. It does not use cached bytecode. Later contract
and native I/O retain their original producers and costs; the live operator
must provide an immutable source/input namespace throughout execution. Source
verification is not protection against a concurrent hostile filesystem writer.

## Offline official-source prerequisites

All official paper code remains external. The unchanged source catalogue pins
revision `2c15edf4e770165fc3962dcc3920c8bcaf555bed` of
[MouseLand/critical_init](https://github.com/MouseLand/critical_init).
`source/contracts/AUTHOR_EXPOSURE.json` selects 18 exposure files, including two
exact extracted notebook-code drivers. The native capture closure selects the
13 original Python modules from `ORIGINAL_SOURCE_CATALOGUE.json`; these two
rosters serve different purposes and neither is silently reduced.

```sh
python3.11 -I -S -B "$PKG/package_tools.py" dependencies --root "$PKG" \
  --manifest-bytes REVIEWED_BYTES --manifest-sha256 REVIEWED_SHA256
python3.11 -I -S -B "$PKG/package_tools.py" verify-author --root "$PKG" \
  --manifest-bytes REVIEWED_BYTES --manifest-sha256 REVIEWED_SHA256 \
  --author-root /absolute/ordinary/path/to/external-selected-author-source
```

The second command is optional explicit source I/O. It authenticates all 18
already acquired files without importing or copying them. Its root is disjoint
from this package and contains exactly the printed relative roster, without
the `author/` prefix. It does not fetch code or derive notebook drivers; exact
driver bodies must already have the reviewed extraction and pins. Do not guess
an extraction from notebook output or vendor primary bodies into this package.
Rights and runtime compatibility require separate review. No offline assembly
is needed for the authored package itself: every authored role is included.

## Live operator integration

The deployment's trusted Python entrypoint can import `package_tools` from its
independently authenticated release and use:

```python
from package_tools import verify

package = verify(package_root, reviewed_manifest_bytes, reviewed_manifest_sha256)
with package.installed():
    native = package.module("critical.native_worker")
    result_bytes = native.run_reference_programme(
        original_issuer, request, transport, design, cost,
        native_plans, bindings, input_root, output_root, device,
    )
```

`original_issuer`, `cost` and all request/design/binding objects are existing live
operator inputs, not defaults supplied here. Create a fresh exact
`critical.core.Costs` inside this context when the qualified operator selects
ordinary limits; do not import a second module owner to manufacture the object.
The complete native plan has one independently selected binding for each of the
26 operations. The original parent live lease handles every child phase via RPC;
the original ordinary-cost owner receives remote prefixes and unknown tails.
Retirement precedes remote capture admission. JSON, matching pins and passing
these tests cannot issue a live lease. The original full parameter constraints,
capture, scoring, closure and error behavior are unchanged.

See [PREREQUISITES.md](PREREQUISITES.md) for exact prerequisite categories and
[the accepted transport design](source/README.md) for the transport fields,
actual composition, failure behavior and live-issuer API. Scientific contracts
and numerical consumers live under `source/contracts` and `source/critical`.
An accepted source component does not close the historical-method or native
qualification gaps listed in those contracts.
