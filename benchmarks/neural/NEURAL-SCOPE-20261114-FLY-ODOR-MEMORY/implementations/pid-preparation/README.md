# Fly PID calibration preparation

This is the complete seven-trace calibration preparer for the existing
`NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY` benchmark family. It preserves all
44,984 released calibration rows. The implementation and its original tests
are exact copies of the independently reviewed source; no authentic
calibration preparation or neural prediction run is claimed by this package.

Python3.11 or later and its standard library are sufficient. There are no
installation, model, MATLAB, numerical-library, container or network steps.

## Private inputs and invocation

The operator supplies two private operands:

1. The exact accepted `BINDING.json`, placed beside `prepare_pid.py`:6,669 bytes,
   SHA256 `41df8c86740b663ea77b8ecfa457091240b09138e0edfc4a835bf7f8a6772956`.
   It contains the fixed complete member roster and provenance. This public
   package excludes its owner-local paths and does not regenerate or replace it.
2. The exact complete PID archive:1,525,818 bytes, SHA256
   `dcefdf148d7d1590946277c5601f845f4d4d178411b0a408f67a6c23e449fa91`.
   Keep it and all generated numerical products outside the repository.

```sh
python3 -B prepare_pid.py --archive /absolute/private/PIDdata.zip --output /absolute/private/fresh-preparation
```

Missing or altered binding refuses before opening the archive. No replacement
binding is accepted by the CLI. `.gitignore` excludes a locally provisioned
binding, but is not an access-control mechanism. The public package and its
CI fixtures contain no original archive, trace, imaging array, protected
target, native filename roster or private path. Data access and distribution
rights remain separate from this project-authored source package.

The output directory must be fresh. It is mode0700, with exclusive mode0600
files even under umask000. Seven JSONL projections and seven diagnostics
precede the final `OUTCOME.json`. A later failure preserves partial products
and attempts a private `FAILURE.json`; I/O failure can prevent that receipt.
An absent valid complete outcome or any failure is never success. There is
no retry, overwrite, deletion or crash-durability guarantee. This is a trusted
local operator interface, not a process sandbox or same-UID isolation boundary.

## Scientific behavior and limits

Every original data row retains its one-based identity and exact five scalar
token strings, including whitespace: native timestamp, frame, wind command,
odor command and detector. The unchanged lexical inspector still checks the
full21-column release profile. It does not pad into the different historical
35-column importer. Seven AppleDouble companions and all42 imaging files
remain in the accepted complete60-entry ancestry; their bodies are untouched.

Exact decimal arithmetic preserves time ordering, integral frame identity and
binary command identity. Missing/nonfinite values, binary64 overflow/underflow,
nonintegral frames, nonbinary commands, duplicate/decreasing clocks and frame
discontinuities remain explicit. No row is dropped, repaired or resampled.
The historical rate/shift formula is a diagnostic using exact decimals and
positive-half-away rounding, not MATLAB floating-point parity or hardware
clock qualification. Application byte/token limits refuse excess; they are
not empirical peak-memory or OS-level resource qualification.

Command edges are adjacent-sample timestamp brackets. Censored on-episodes
remain visible, and invalid rows are never bridged. A complete command cycle
does not establish valid physical timing. Detector values remain in native
units; no threshold, fixed delay, physical odor disappearance, averaging
subset, concentration conversion or downsampling is invented.

The eventual neural endpoint remains retrospective prediction of later
goal-aligned movement, conditional on released derivatives. Physical odor
calibration, full imaging alignment/units, biological identity aliases,
future-derived normalization, all-condition eligibility, animal-macro scoring
and competent neural/nuisance predictions remain unqualified. Seven calibration
traces are not seven animals or new benchmarks. No readiness/count promotion,
paper reproduction, LLM result or submission qualification is claimed.

## Public checks

In an unprovisioned source checkout:

```sh
python3 -I -S -B run_public_checks.py
```

This discovers the unchanged original suite, runs its11 operand-independent
methods and three focused public-interface tests. The original twelfth method
checks production rejection of an invented archive after the exact private
binding has been supplied; it remains unchanged and is deliberately excluded
from public CI. Once the operator supplies that metadata, the complete original
suite remains available with `python3 -B -m unittest -v test_prepare_pid`.

Public-interface tests check relocation/help, missing binding and altered
binding without opening any authentic input. Public CI first authenticates
the manifest itself against a fixed digest, then every package member and
the complete package file set before executing any package source. The
standalone command above assumes a trusted checkout; it is not itself an
external source-authentication boundary. A manifest hash is not scientific
validation. All test fixtures are invented.
