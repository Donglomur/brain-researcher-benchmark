# Original linear-readout audit

This additive component closes the missing decoder-output connection between the
[original producer](../source-producer-v1/README.md) and the
[submission bridge](../submission-bridge-v1/README.md). It retains coefficients,
predicted displacements, exact training/test supports, observed fit-input hashes,
and split-specific neural condition means. A separate evidence packet joins those
outputs to the existing score packet and verifies their arithmetic against
explicit operator inputs. Both predecessor implementations remain unchanged.

This is an **optional original-linear-readout route** for source calibration and
methods retaining that readout. A novel candidate with a different decoder can
still use the existing prediction interface. No linear-coefficient requirement is
added to the canonical improvement task. The original source-code ridge-1 and
paper-described OLS-0 recipes remain distinct.

## Preserved scientific computation

The public producer functions require the full source layout: 150 bins, 511
trials and 182 neurons. They retain 265 straight and 246 curved trials, twenty
repeats and five folds. Each of the eight named representation/readout slots has
200 decoder fits and 10,200 test occurrences. The complete evidence set therefore
contains 1,600 fold records and 81,600 repeated test occurrences. These are
dependent occurrences, not new biological samples or benchmarks.

Neural `[55:-15]` and movement `[65:-5]` windows retain the original ten-bin lag,
79 displacement predictions and 80 positions. Predictions start at the exact
provided initial hand position; displacements are integrated without multiplying
by a time step. Ridge penalizes the appended intercept. The separate raw
condition-average route retains both reversed halves in twenty repetitions,
the original MT19937 continuation and cumulative permutations, and the odd
straight-trial middle position. Its 80 fit records retain both neural means,
training movement means and original group counts.

The packet does **not** export or require held-out movement means. The verifier
derives them only from its operator bank, and checks their initial point against
the original prediction packet. The producer's private in-memory result still
contains targets, as its predecessor does; it is an operator numerical helper,
not a participant data-delivery interface. These evidence artifacts must remain
evaluator-private and must not be attached to a subsequent candidate attempt.

## Using the API

An operator with a separately admitted numerical execution can construct a
family from already supplied complete model representations:

```python
# Load audit_packet.py by an ordinary local module loader; it pins both inputs.
audited = audit_packet.a
bridge = audit_packet.b
prepared = bridge.load_prepared_bank(private_bank_path, plan["bank_manifest_sha256"])
family = {
    "single_trial_decoding": {
        name: audited.repeated_decoding(x, prepared["movement"], recipe=plan["recipe"])
        for name, x in representations.items()
    },
    "raw_condition_average_control": audited.condition_average_control(
        representations["raw"], prepared["movement"], prepared["target_angle"],
        recipe=plan["recipe"],
    ),
    "component_results": original_component_results,
    "preparatory_subspace": original_preparatory_subspace,
}
core_receipt = bridge.write_packet(
    family, new_core_path, plan=plan, declaration=declaration,
    reconstruction_predictions=reconstruction_predictions,
)
core = bridge.Packet(new_core_path, core_receipt["manifest_sha256"], plan)
pins = {name: audited.array_digest(x) for name, x in representations.items()}
audit_receipt = audit_packet.write_packet(family, new_audit_path, core, pins)
evidence = audit_packet.AuditPacket(new_audit_path, audit_receipt["manifest_sha256"], core)
report = audit_packet.verify_original_linear_readout(evidence, prepared, representations)
```

Representations are explicit little-endian float64 `[150,511,182]` arrays in all eight original
slots, including genuine supplied LFADS output and the separately named mixed
partials. No missing representation is fabricated. The bank passed to verification
must contain the original private manifest identity and arrays. The original
bridge still computes scientific metrics and paired differences using its
operator targets and masks. This sidecar introduces no new performance metric,
success threshold, reference result or uncertainty estimate.

Each representation is bound by a shape/dtype-aware content digest. Every source
fit record binds its actual training features, training displacements, ordered
support and returned coefficients. The verifier checks those bindings, exact
schedules, independently recomputed condition means/counts, and
coefficient → displacement → true-start position arithmetic. Its `1e-10`
absolute/relative arithmetic tolerance is numerical, not a scientific equivalence
margin. It performs no refit or decomposition optimization.

**Observed records are not trusted execution provenance.** A consistent coefficient
set does not prove optimizer optimality, minimum-norm OLS, honest fitting,
permitted information access, or authentic representation training. The verifier
explicitly leaves both fit-execution and representation-fitting authentication
false. The named representations are validated as supplied inputs, not recovered
historical models. Protected execution and independent source provenance remain
necessary for stronger claims.

## Storage and execution boundaries

The writer uses a fresh private directory, exclusive numeric files and a final
manifest bound to the exact original packet and plan. Failed writes preserve
artifacts and do not return a successful completion receipt. A partial or fully
written but unacknowledged manifest may remain: callers require the returned
bound receipt and validation, not the existence of its filename. Files are bounded gzip/NPY;
the reader authenticates the exact byte buffer it decodes, rejects aliases,
symlinks, extra/missing arrays and mismatched headers, and limits the aggregate
decoded extent before reading payloads. The maximum compressed packet, including
its captured manifest, is 512 MiB; the decoded arrays also have a separate
512 MiB ceiling. Manifest size is bounded at 16 MiB. These are logical artifact
bounds, not a process-memory or CPU sandbox.

At twelve angle groups per reach, the additional raw audit arrays occupy
336,778,240 bytes, before the manifest and gzip/NPY overhead. This is a planning
example, not a newly measured authentic group count or compression ratio.
Original score packets, representations, source data and temporary memory are
separate. The full fit-input digest checks also revisit many overlapping training
views. `decoder_fold` and `averaged_half` expose per-block production seams for a
future bounded collector; this release does not claim that a complete fitting
campaign fits the current local allocation or has an admitted execution budget.

All original paper/code discrepancies, unavailable LFADS/historical fits,
component identities/gauges, source-authoritative reconstruction masks/ranks/seeds,
qualified comparator, scientific reproduction/improvement criteria and protected
paired participant execution remain explicit. No authentic data, decomposition
fit, candidate campaign or paper improvement was run for this source addition.

The Python verifier does not independently reopen and authenticate the bank or
the process that created a representation. The operator must use its pinned
bank loader and keep the resulting inputs immutable; matching a caller-supplied
manifest string alone is not evidence of data provenance.

## Generated verification

Use the existing NumPy/SciPy environment; this component installs nothing:

```sh
python3 -m unittest discover -s . -p 'test_*.py' -v
```

Validation is summarized in `VALIDATION.json`. Producer parity tests retain all
original row/fold/half schedules with three generated features and a test-only
window adapter. Packet tests likewise lower feature count only inside the test;
the public 182-feature requirement has an independent negative check. Generated
transport tests use an in-memory stand-in for the already tested original bridge
packet and exercise the real new audit serializer/reader. They are not authentic
full-dimensional fitting, native isolation or scientific qualification.
