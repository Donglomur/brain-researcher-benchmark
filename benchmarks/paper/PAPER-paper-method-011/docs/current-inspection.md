# Current MotorMINT source inspection

Use the explicit
[current inspection binding](../../../integrity/current-closures/numeric-motormint/CURRENT_INSPECTION.json)
to inspect the repaired source for this [existing task](../task.json).
The [historical package guide](../implementations/paper-method-011/full-motormint-v1/README.md),
`SOURCE_MANIFEST.json`, `RUNTIME_MANIFEST.json` and `RUNTIME_BINDINGS.json`
retain their original contents. The separate current binding names the four
reviewed replacements: `run.py`, `central_sources.py`, the numerical scorer and
the phase-column recipe validator.
It does not rewrite the historical source record.

Run from the repository root with Python 3.11 or later and the standard library,
on a POSIX host supporting `O_NOFOLLOW`, `O_DIRECTORY` and nonblocking file opens:

```sh
python3 -I -S -B \
  benchmarks/paper/PAPER-paper-method-011/implementations/paper-method-011/full-motormint-v1/run.py \
  --source-bytes 1591 \
  --source-sha256 e91a3cf17849e1a713cc18a55194b1d5cc2a4e19baa9d8fcbfc125132cb7d651 \
  --current-source-binding "$PWD/benchmarks/integrity/current-closures/numeric-motormint/CURRENT_INSPECTION.json" \
  inspect
```

With this option, `--source-bytes` and `--source-sha256` authenticate the current
inspection-binding file, which in turn identifies the historical manifest and
the exact replacements. The values above belong to this reviewed revision.
Do not silently refresh them from a changed file. The explicit binding path must
be absolute and pass the command's ordinary-file and non-following path checks.

Inspection captures all 62 selected public source files, verifies the 39 runtime
bodies within that set, and checks the declared nine datasets, 17 analysis modules
and 17 scientific gates. Its report distinguishes historical manifest identities
from the current numerical-scorer and phase-recipe replacements. These counts
describe source scope, not verified datasets or completed analyses.

The recipe repair requires circular metrics on the original phase dimensions
and linear metrics on non-phase dimensions. It does not authenticate native phase
units, branch cuts, interpolation or source-data parity. The exact predecessor
validator is retained in the [phase-repair history](../implementations/behavior-recipe-v1/historical/bindings.before-phase-repair.py).

This binding is **inspection only**. The command rejects its use with `prepare`,
`run` or other execution commands before opening a protected review. Historical
run-route preflight is explicitly reported as not selected for this binding;
successful inspection does not qualify that route. Inspection does not open
deferred dependency bodies, original neural data, protected references or model
files, and does not run the scientific pipeline or native methods.

The supplied deployment remains disabled. The report retains
`scientific_execution: false`, `qualified: false` and `execution_authority: false`.
Original inputs, references, author-code rights, native isolation, runtime and
resource evidence still require the qualifications described in the
[deployment contract](../implementations/paper-method-011/full-motormint-v1/DEPLOYMENT_CONTRACT.md).
The source repair and inspection interface add no benchmark, empirical result or
execution authority.
