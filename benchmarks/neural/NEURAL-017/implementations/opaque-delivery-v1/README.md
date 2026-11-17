# Opaque full-panel delivery for NEURAL-017

The registered observation contract requires opaque trial/unit IDs and forbids
source identities usable for answer lookup. The inherited raw preparation emits
`train-nwb:trial-*` and `Jenkins-20090925:unit-*` labels in original source order.
This component supplies an executable, reversible delivery transformation for
that mismatch. It leaves the predecessor source and canonical contract unchanged.

`delivery.export_public` validates the exact public array allowlist, the supplied
operator fingerprint, all 1,721 training and 574 query trials, 137 observed and
45 withheld units, the 140-bin 5 ms clock, integer counts, complete observation
support, disjoint axes and training support for every query condition. It then:

- Replaces source trial and unit labels with keyed opaque identities.
- Independently permutes training/query trials and observed/withheld units by
  opaque ID order, applying each permutation consistently to counts, conditions
  and masks. Within-trial time order is retained.
- Preserves every count, its dtype, the original permitted condition labels
  (including any encoded factor structure), and all target
  obligations. No filtering, smoothing, fitting or target-dependent mask occurs.
- Recomputes the inherited public-content fingerprint. The source-manifest field
  becomes the digest of a private derivation record binding the original packet,
  mappings and secret-key commitment. The condition labels remain permitted
  source context and are not treated as forbidden trial/unit identities.

`delivery.restore_prediction` verifies the operator's independently retained
binding hash, units, all output cells and exact identity sets, then maps submitted
positive expected counts back to the predecessor scorer's original axes and
fingerprint. A participant may reorder trial and unit axes when IDs agree.
No query target or comparator is needed for either transformation.

## Operator use

These are trusted in-memory array APIs, deliberately separate from archive
parsing and process isolation. A caller must first authenticate the source NPZ
and source provenance through existing custody. Do not call `np.load` on an
untrusted submission in place of the inherited bounded NPZ parser.

```python
import secrets
import delivery

# `source` is the already-authenticated full public packet, with no query labels.
# `expected_source_fingerprint` comes from an operator-controlled source lock.
secret = secrets.token_bytes(32)  # Retain privately if exact re-export is needed.
public, private_binding = delivery.export_public(
    source, secret=secret,
    expected_source_fingerprint=expected_source_fingerprint,
)
binding_sha256 = delivery.digest(private_binding)
# Retain the binding and its hash in operator custody. Deliver only `public`.
# Keep the same immutable export across all participants in the comparison.

# `prediction` is admitted by the existing bounded prediction archive parser.
source_prediction = delivery.restore_prediction(
    prediction, private_binding, expected_binding_sha256=binding_sha256,
)
# Existing grade.evaluate(source_prediction, source_gold, fixed_comparator, ...)
```

The returned binding contains original identifiers and must never enter the
participant directory or public Git. Store its hash in an independent immutable
operator record; accepting a binding hash supplied by a participant defeats the
restoration check. Generate a fresh random 32-byte secret for each new delivery
freeze and keep that secret private. Test keys are only generated fixtures.

## Integration and scientific limits

This is a source-available preparation component, with generated software
controls. It has not processed authentic arrays in this revision. The existing
registered runtime, asset pins, programme compiler and source contracts are not
silently redirected to it. Integration must freeze the transformed packet and
mapping, bind the participant packet in custody, restore predictions before
existing scoring, and enroll the controls in CI. A new matched programme must
also regenerate its planned support/view/shuffle commitments from the common
opaque support before participant exposure. Preserve original acquisition
chronology privately for the existing chronology-block summaries; sorted opaque
IDs are not chronology. Historical results and commitments remain unchanged.

The fixed training condition/time comparator and intact/shuffled/context controls
retain their original scientific definitions. Numerical/programme performance
does not establish direct interpretation. This component supplies no no-tools
transport, raster viewer, model run or native runtime qualification, and leaves
those mode distinctions explicit.

Opaque labels remove explicit source-index lookup and original row-position
lookup. They do not anonymize distinctive recordings, remove the source's public
exposure, or establish an untouched test set. Counts can still identify public
recordings. This remains retrospective co-smoothing within one exposed Jenkins
session, not forecasting, latent-rate recovery or cross-animal inference.

## Generated controls

`test_delivery.py` uses the complete declared shapes with generated integer
arrays varying along trial, time and unit axes. It checks every transformed cell,
verbatim condition preservation, private/public separation, exact inherited fingerprint
parity, restoration of independently permuted predictions through the existing
metric, and rejection of incomplete panels, labels, shifted clocks, unsupported
conditions, malformed counts, wrong units and altered bindings. It runs through
the shared lightweight test pool; no scientific dataset or model is opened.

The scientific export and inverse checks retain the entire panel. The inherited
fingerprint's allocating reference implementation is compared on a separate
bounded packet spanning multiple streaming chunks, including mixed byte order
and nonconstant masks. This avoids large duplicate int64/byte buffers in tests;
it does not reduce the production admission or scientific support. An earlier
generated test run exceeded its 1 GiB declaration; its receipt and predecessor
test source are preserved externally rather than relabeled as compliant.

Sources are pinned in `SOURCE_PINS.json`. Acquisition and NLB source citations are
in the existing task contract. They were inspected through existing local source
and audit records; this component performs no new source acquisition.
