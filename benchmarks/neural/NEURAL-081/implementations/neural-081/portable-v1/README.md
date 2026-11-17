# Build a new NEURAL081 source instance

This directory supplies the complete portable source constructor and metadata-stage implementation for NEURAL081. Use it from a public repository checkout that also contains the exact 105 prerequisite files listed in `release/PORTABLE_RELEASE.json`. The release preserves the full ten-person, twelve-class EEG and ZERO-control task, both numerical references and matched fixed-program/current-query investigation conditions. Scientific code is unchanged. Construction is separate from operational qualification and scientific execution.

The effective executable is [release/neural081_instance.py](release/neural081_instance.py). Its release descriptor is [release/PORTABLE_RELEASE.json](release/PORTABLE_RELEASE.json); [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) authenticates all nine release bodies. Four accompanying source fragments reproduce the executable byte for byte using the separator and order in [release/SOURCE_FRAGMENT_MANIFEST.json](release/SOURCE_FRAGMENT_MANIFEST.json). These fragments are useful source provenance, not additional installed modules.

## 1. Select roots and a real profile

Choose an absolute public checkout, a fresh absolute instance root outside that checkout, and separate external operator, raw, secret, protected and output roots. All selected external roots must be pairwise disjoint and disjoint from the instance root. Parent directories must already exist and have appropriate ordinary-directory custody; symlinks are refused. The release may live in the checkout. No existing instance root is overwritten.

Create a profile in your selected operator namespace according to [OPERATOR_RECORDS.md](OPERATOR_RECORDS.md). Construction can start with all three late input/environment/execution slots explicitly `{"disposition":"not_supplied"}`. That value means missing evidence; it never qualifies a run. Compute byte lengths and SHA256 from the exact ordinary files you supply, without changing bytes after pinning.

Every uppercase operand below is a symbolic value you must replace. In particular, there are no usable fake hashes, passing receipts or default resource approvals in this distribution. The constructor needs a compatible POSIX Python with directory-fd operations, `O_NOFOLLOW`, directory fsync and the standard library. Scientific execution has additional exact environment requirements; a successful source build does not establish them.

```text
ABS_PYTHON -I -B ABS_CHECKOUT/benchmarks/neuroscience/neural-081/portable-v1/release/neural081_instance.py build
  --release ABS_CHECKOUT/benchmarks/neuroscience/neural-081/portable-v1/release/PORTABLE_RELEASE.json
  --release-bytes EXACT_RELEASE_BYTES --release-sha256 EXACT_RELEASE_SHA256
  --public-root ABS_CHECKOUT --root ABS_FRESH_INSTANCE
  --profile ABS_OPERATOR_PROFILE.json --profile-bytes EXACT_PROFILE_BYTES --profile-sha256 EXACT_PROFILE_SHA256
  --read-cap SELECTED_LOGICAL_READ_BYTES --write-cap SELECTED_LOGICAL_WRITE_BYTES
  --live-cap SELECTED_MANAGED_BYTES --deadline SELECTED_MONOTONIC_ENDPOINT
```

Treat the displayed wrapped command as one argv sequence. The deadline is an absolute endpoint in the current host's monotonic clock, not a wall-clock date. Source reads, copies, hashing, JSON processing, publication/readback and helper worst-case failing reads consume explicit caps. These are logical/managed bounds, not physical I/O or RSS measurements. The command's bounded JSON output names the actual `BUILD_RESULT.json` descriptor. Retain the command, original streams and actual natural exit; a printed result alone does not prove completion.

The build archives all 105 originals under `INSTANCE/origin`, copies 66 active source/context bodies, and generates six metadata bodies in dependency order for a complete 72-source closure. Of the 66 active bodies, 59 are exact published originals, four are declared portability variants, and three are the new constructor/gate/protocol. The active graph has 54 Python bodies and 12 context bodies. New construction provenance replaces the old private instance's identity claims, rather than forging or rewriting historical receipts. The initial task registry is unqualified.

## 2. Bind independently supplied metadata

Use the installed `ABS_INSTANCE/tools/neural081_instance.py` for subsequent stages. Each invocation takes a pinned stage-input JSON and the same four explicit caps:

```text
ABS_PYTHON -I -B ABS_INSTANCE/tools/neural081_instance.py STAGE
  --input ABS_OPERATOR_STAGE_INPUT.json --input-bytes EXACT_INPUT_BYTES --input-sha256 EXACT_INPUT_SHA256
  --read-cap SELECTED_LOGICAL_READ_BYTES --write-cap SELECTED_LOGICAL_WRITE_BYTES
  --live-cap SELECTED_MANAGED_BYTES --deadline SELECTED_MONOTONIC_ENDPOINT
```

[STAGES.md](STAGES.md) gives all eleven stages, exact payload key sets, ordering and output domains. These commands perform bounded metadata validation and publication. They do not launch scientific workers, qualify an environment, contact a provider, generate an authority receipt or create independent approval. Only initially missing profile slots can be resolved later; an already pinned slot is immutable. Source bodies and the initial profile/build result remain immutable throughout.

## 3. Plan an actual invocation only after qualification

The default route and `full10_instructed_excerpt_v1` route select the same complete scientific support; each needs its own exact review. `admit-approved-review` emits the exact planned absolute argv and cwd after genuine source/metadata predicates. It does not execute that command. Preserve the generated command instead of improvising flag order. [STAGES.md](STAGES.md) distinguishes the relative registry template from the actual absolute invocation.

Authentic input eligibility, numerical/worker/provider capability, protected issuer identity, physical namespace isolation, source custody, original-clock budgets and independent original process/stream completion remain operational prerequisites. Supplied records must be true and independently administered; passing a JSON consistency predicate cannot establish those facts. This release provides the operative source path and constructor, not those external facts or a scientific result. No private WORK_ASSIGNMENTS/catalogue history is required by this task-local route; the global catalogue CLI is not its entrypoint.

See [SOURCE_DEPENDENCIES.json](SOURCE_DEPENDENCIES.json) for exact public source prerequisites and [PROVENANCE_AND_LIMITS.md](PROVENANCE_AND_LIMITS.md) for variant, historical and engineering-evidence distinctions.
