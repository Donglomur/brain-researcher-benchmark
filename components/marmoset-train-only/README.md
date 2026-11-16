# Marmoset training-response adapter

Portable source for the existing task `marmoset-retinal-contrast-generalization`.
This delivers the **response-loading component only**: all170 fixed selected
cells in both original preparations, every declared permitted stream/trial/frame,
and all six registered information conditions. It does not deliver a complete
candidate packet, stimulus reconstruction, scorer, native model or qualified task.

The official loader opens both training and protected test responses even when
its `responses` flag is false; its STA path always uses white-noise calibration.
The replacement reads only reconstructed, condition-permitted **training** leaves.
It never opens protected test responses or original STAs. Strict NM-only input
excludes WN response reads; mixed/assisted input preserves an explicit WN
`calibration_only` label. That label is not enforcement of downstream fitting.

## Use

`train_only.py` is byte-identical to the reviewed implementation and has only
standard-library dependencies. Place this component directory on Python's
import path, or load its module explicitly with `importlib`. The Unix file reader
uses `O_NOFOLLOW` and `O_NONBLOCK`; Windows support is not claimed.

```python
import train_only

result = train_only.prepare_training(
    externally_qualified_complete_policy,
    policy_sha256=externally_frozen_canonical_policy_sha256,
    source_root=original_release_root,
    read_byte_budget=complete_permitted_training_bytes,
    output_byte_budget=complete_selected_count_bytes,
)
```

This is the existing callable API, not a newly invented runner. It returns
immutable typed count buffers with explicit C-order shape, dtype, units, cell
and trial identity, condition permissions and hashes. All170 selected cells and
every declared permitted sample survive. Integer count bytes, including uint64
above2⁵³, are preserved without conversion to floating point. No output files
are written and no model is run.

Read the complete [SPECIFICATION.md](SPECIFICATION.md) before supplying a policy.
That specification is the accepted source documentation, unchanged byte for byte.
Policy/array hashes authenticate identity, not a biological census or source
permission. Original cell/seed/trial/frame identities, source array headers,
target-independent timing and animal relationships must be independently
qualified. In particular, declared NM seed1/2 vocabulary is not evidence that
both seeds exist in every original preparation.

The adapter authenticates each complete selected training NPY body, checks its
primitive count representation, and projects all frozen selected rows. It
refuses missing declared support, wrong shape/dtype, nonfinite/fractional/negative
counts, unknown fields, untrusted policy identities and insufficient whole byte
allocations. C and Fortran layouts preserve exact values. A later stream failure
does not return an earlier subset as success.

## Verification and limits

[SOURCE.json](SOURCE.json) binds the complete source package. The CI job verifies
its externally pinned identity and every member before importing tests. It
explicitly loads all10 retained scientific/input-boundary methods and3 new
relocation methods, requires13 executions and rejects skips/expected failures.
Local packaging checks run only the3 new relocation methods; the unchanged
accepted scientific suite is retained for CI without local replay.

The generated relocation checks verify package closure, execution from an
unrelated directory with only the standalone source copied, complete170-cell
projection, and refusal of a missing/mismatched policy identity before file opens.
All test inputs are invented. They do not qualify native data or scientific
performance, and there is no new benchmark ID or readiness promotion.

This source is not a sandbox or process owner. Parent-directory trust, effective
mounts, lifecycle/output custody and actual memory/time/storage admission remain
external. Read/output byte arithmetic is not a measured peak-memory guarantee.
Original STAs are never supplied: condition-permitted RF/STA and competent
reference fitting remain separate, especially unvalidated NM-only calibration.
Strict source-only labels restrict new fitting while retaining the historical
test-reliability selection of the170-cell roster; they do not make the cohort
target-unexposed. Stimulus preparation, full scoring/undefined coverage and
protected execution remain outstanding.

No official source body, original array, private reference, primary capture,
private integration metadata or credential is included. Scientific attribution
and source/rights limits are recorded in [ATTRIBUTION.md](ATTRIBUTION.md).
