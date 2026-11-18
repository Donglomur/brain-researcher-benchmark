# Portable generated input-adapter controls

The production adapter, final03 fixture, independent tests and original README
are unchanged. `vendor/verify_saved_eeg_projections.py.txt` carries the exact
26,700-byte Reader source as inert bytes. All four executable dependencies are
checked by exact size and SHA256 before any dependency compilation or injection.
The adapter itself compiles the Reader. Its native verifier entry is never run.

Use POSIX Python 3 with its standard library. From any directory, pass absolute
paths to these commands (replace PACKAGE with this package's absolute path):

```sh
python3 -I -S -B PACKAGE/test_public_bootstrap.py
python3 -I -S -B PACKAGE/run_generated_controls.py
```

The first command runs one test method containing twelve mutation cases: each
dependency is altered at equal length, truncated and extended. Each must fail
before compilation, execution or module injection. The second command selects
exactly four generated adapter methods. These counts are reported separately.
Both print a bounded unittest summary and JSON to stdout, with no file writes.
The worker deadline is 15 seconds, CPU limits are 10/11 seconds, and declared
128 MiB RAM is checked against observed peak RSS; memory is not OS-hard-capped.

Enroll the two commands through the existing stdlib profile in
`benchmarks/integrity/parallel-source-controls.v1.json`; the existing workflow is
`.github/workflows/parallel-source-controls.yml`. The integrator owns enrollment.
Do not use unittest discovery: the accepted fixtures require injected modules.

The obsolete `test_input_adapter.py` remains in private historical evidence and
is excluded here. The tiny real-file method's attempt02 pass remains historical;
these four-method runs do not rerun it or establish five groups in one invocation.
No authentic metadata, EEG arrays, models, providers, native contexts or scoring
are exercised. This is portable source-control evidence, not scientific readiness.
