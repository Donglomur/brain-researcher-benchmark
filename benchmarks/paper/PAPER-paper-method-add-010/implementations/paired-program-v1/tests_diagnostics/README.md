# Diagnostic regression controls

Run with the standard library only, from the paired implementation directory:

```sh
python3 -I -S -B tests_diagnostics/test_diagnostics.py -v
```

The three tests execute the production candidate wrapper, owned Provider, bounded
CLI capture, archive parser, and strict receipt validator. A generated local
daemon supplies Docker observations; Linux process identity fields and pidfd
availability are explicit test substitutes. Real child processes and pipes are
used. These tests do not qualify Docker isolation, Linux signaling, original
data access, a full benchmark campaign, or scientific results.

The success child writes 128 KiB to each stream before producing its result.
Success must remain admitted with no forwarded child logs and exactly two
unchanged captured files: `RESULT.json` and `OUTPUTS.json`. The failure child
raises an exception. Production `main` must emit its bounded private envelope,
suppress a duplicate traceback, preserve failed status, and admit no output.

The tests use fresh generated directories under `TMPDIR` (or the interpreter's
default temporary directory). Passed scratch trees are removed after assertions;
failed prefixes remain for the caller's private review. No original data or
machine-specific source paths are needed. The retained fixture envelope and
raw generated diagnostic streams are never public test artifacts.

`ARTIFACT_DIR` is optional. When supplied, it must name an absent absolute leaf
whose parent exists. The tests create that leaf and write only aggregate
`RESULT.json` metadata, bounded by 16 KiB. CI can set
`ARTIFACT_DIR=${ARTIFACT_DIR}` through its existing environment substitution.
The ordinary unittest transcript remains the pass/fail interface.

All tests share a 100-second clock. Each Provider phase has a 37-second allowance,
at most 64 CLI processes, 112 KiB of Provider writes, and a 4 MiB Provider read
budget. Fixture writes are capped at 64 KiB per test. The selected generated
campaign reserves 640 KiB of cumulative output and 18 MiB of named reads,
excluding interpreter and library loading. An unexpected need for Linux signaling
fails the test; signaling is never emulated as successful cleanup.

The output-refusal test runs a child that exits zero after writing `RESULT.json`
and an extra symlink. The wrapper must keep its single-result refusal, publish
no `OUTPUTS.json`, and retain only bounded private entry names, types, and inode
metadata. Direct calls to the same collector check truncated names/entry counts,
a changed initial identity, and unavailable observation, while forbidding entry
opens and reads. Neither output contents nor symlink targets are exported.

To run only this affected control:

```sh
python3 -I -S -B tests_diagnostics/test_diagnostics.py DiagnosticRegressionTests.test_output_refusal_retains_bounded_private_metadata -v
```

Aggregate `methods` reports the number selected and completed.
`available_methods` is three; `full_suite_complete` is false for a one-method
run. The ordinary unittest result remains authoritative. A one-method campaign
reserves 256 KiB of generated artifacts and 12 MiB of named reads, with its
separate supervisor limited to 60 seconds and 256 MiB. The daemon protocol and
Linux identity observations remain explicit generated substitutes.
