# Alpha programme public-source publisher

The current task-local publisher selection for a separately authorized, captured
outer-source operation is `run_public_modes_v2.py`. Select this source through the
existing `launch_prelude.py` template as described below. This is a source-only
permission repair; runtime, scientific, and submission qualification remain
false, and the registration adapter continues to refuse execution.

## Current selection and preserved predecessor

`run.py` remains the byte-exact frozen publication predecessor from commit
`8482a7c022`, moved without changes by `4f071994a3`. Its 17,124 bytes have SHA-256
`e7e9346a804bfde1da7cf56c4e33481acc4cdce59ecbd984d53dc5d6185b4794`.
The original publication scope is recorded at that first commit in
`authoring/delivery-20261105/common/github-publication-audit-v1/visual-alpha-wave16-review/PUBLIC_SOURCE_SCOPE.md`.
The predecessor and its registration proposal remain historical evidence.

`run_public_modes_v2.py` inherits the predecessor's behavior and adds exactly one
statement: `os.fchmod(fd,0o444)` after the complete write and before `os.fsync(fd)`
in `IO.save`. Its 17,156 bytes have SHA-256
`10bee44e373f156c29ab8ba049872d19fd8edf91bb3e3fd1deefa469898c6d01`.
This restores the intended public read permission under restrictive umasks for
the source bodies passed by `frozen_sources` to worker and UID-65534 container
consumers. Exclusive creation, path guards, private parent directories, source
checks, resource budgets, failure retention, and scientific behavior are inherited.

## Captured operator route

For the current source selection, root must freeze the following substitutions
into a new authenticated command using the unchanged `launch_prelude.py`:

| Template operand | Current selected value |
| --- | --- |
| `__RUN_PATH__` | Absolute ordinary path to this directory's `run_public_modes_v2.py` |
| `__RUN_BYTES__` | `17156` |
| `__RUN_SHA256__` | `10bee44e373f156c29ab8ba049872d19fd8edf91bb3e3fd1deefa469898c6d01` |

The launch form remains qualified Python `-I -S -B -c <captured substituted
prelude>` with `--selection <ordinary selection path> --selection-sha256 <exact
selection digest> --output <fresh output path>`. Directly invoking either outer
source bypasses the required captured context and is rejected by its existing
gate. The successor uses its own directory for the source closure, preserving
the existing worker/controller/engine paths.

The public checkout omits `BINDINGS.json`, `SOURCE_MANIFEST.json`, selection
operands, and authenticated `ROOT_COMMAND.json`. Any future root-owned command
and source manifest must explicitly select and pin the successor and authenticate
the complete current closure; predecessor command or source digests must not be
reused. Those root-owned artifacts and central selection descriptors are outside
this source-only change. This documentation selects the current publisher without
creating execution authority or changing the historical registration proposal.

## Generated permission controls

`test_public_modes.py --artifacts <fresh ordinary evidence directory>` defaults
to the current successor. Its ten stdlib controls call the actual
`frozen_sources` / `IO.save` path with generated bodies under `umask 077` and
retain all fixtures, including intentionally failed writes. They cover holder,
candidate, baseline, support, and manifest modes; unchanged source bytes and
private paths; full short-write completion before descriptor mode restoration
and file sync; empty output; write/mode failures; exclusive and symlink guards;
budgets/deadlines; corrupted sources; and existing snapshot refusal.

Use the coordinating shared test pool with `python3.11 -I -B` and a unique run
ID. `--publisher run.py` selects the historical predecessor for a retained
negative control. These tests use no native/container runtime, models, authentic
data, fitting, or grading. They do not qualify the full program or repair the
omitted dependencies of the historical test suite.
