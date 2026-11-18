# NEURAL-073 canonical corpus query input

This adapter connects the existing admitted original-map corpus and export plan
to the accepted typed map viewer. It adds no NIfTI converter, renderer, label
taxonomy, process controller or scientific scoring rule.

The trusted operator supplies the **same loaded `corpus` module that issued its
`CorpusBundle`**, the accepted viewer module, the issued `ExportPlan`, and the
existing verified export capability. These modules and objects remain private.
The exact runtime import closure and viewer pin are in `SOURCE_BINDINGS.json`.
Importing this adapter performs no source or neural-data I/O.

```python
query = adapter.QueryInput(
    corpus_module=corpus, viewer_module=viewer,
    bundle=admitted_bundle, export_plan=issued_plan,
    export_authority=verified_export_capability,
    inventory_pin=admitted_inventory_pin,
    converter_contract=pinned_contract_bytes,
    conversion_result=pinned_result_bytes,
    conversion_result_pin=selected_result_pin,
    limits=explicit_viewer_limits,
)
# Only query.dispatch(request) responses may enter participant transport.
# After every query case has an answer or explicit abstention:
operator_result = query.finish()
```

The existing source emits 64-hex HMAC case keys; the unchanged viewer expects
32-hex keys. The adapter derives context-bound display aliases, rejects any
collision across the complete query roster, and preserves its issued order.
Its operator-only final wrapper restores every original 64-hex query key. It
retains the unchanged 32-key viewer collection and its commitments under the
original schema, alongside a separately named source-result schema and digest.
It never relabels altered records as an unchanged viewer result. The alias
table, bundle, source records and final operator result must not be handed to
the participant.

The adapter checks the complete held-person query and complementary training
membership, query labels against the private catalogue, and the exact ordered
25-class ontology. Only the ontology is public. Training/calibration keys,
group identities, per-query labels and source provenance are absent from its
dispatch responses. Existing training/calibration export is a separate route;
this component neither delivers calibration nor asserts its completion. Arm
and repetition stay bound through the issued context and export capability.
This does not qualify interactive chronology or activate a viewer access mode.

Only `original` is supported. `spatial_scrambled` and `C_only` are refused before
any canonical access: original maps cannot substitute for those conditions.
No complete 234-context study is claimed.

The canonical source geometry does not carry spatial units. The adapter uses
the exact existing converter `RESULT.json` instead of inferring units. Its
caller-selected bytes/hash are checked, then its inventory extent/hash,
catalogue/domain, geometry, record count and complete canonical extent are
joined to the bundle. Every original receipt must bind the accepted converter
contract. The result must preserve native units and declare no independent
fidelity/rights qualification or deployment. `unknown` remains `unknown`; no
unit conversion, reorientation, cropping, masking or resampling occurs.

Actual array access goes through the existing `CanonicalMapping`. The returned
immutable canonical bytes are shared with `CanonicalMap`; no second loader or
per-voxel re-encoding is introduced. A finalizer retains the `_CanonicalValues`
owner until the map dies, so its canonical workspace reservation cannot be
released while the viewer still holds the bytes. Existing read/hash/deadline,
cache and failure accounting remains in effect. Additional adapter Python
metadata and viewer rendering still require externally qualified host capacity;
this component makes no physical-RSS or OS-isolation claim.

Run the new generated controls from this directory after the exact dependencies
are composed:

```text
python3.11 -I -S -B test_adapter.py -v
```

The public command uses adjacent published dependencies. Private construction
uses explicitly pinned dependency snapshots via the test-only path flags; it
does not use mutable working-tree code. These nine tests use 75 invented
metadata records (three people, 25 labels), one deliberately repeated 2,048-byte
map, real invented-domain catalogue/assessment/export factories, and the real
canonical reader. The fixture explicitly constructs the sealed bundle data
class: it **does not execute or establish authentic `load_corpus` admission**.
Invented duplicate adjudications and capabilities are not authentic evidence.
No previous viewer suite is rerun, and no scientific model is run.

Source integration, exact final-tree dependency pins, all applicable CI and
maintained ownership/catalog enrollment remain with the sole integrator.
Authentic conversion fidelity, source taxonomy/rights, biological identities,
calibration delivery, complete matched contexts, reference competence, live
transport and OS/provider isolation remain separately qualified. Quantized
RGB8 slices do not establish numerical-information equivalence or native
neural understanding. No readiness, endpoint or benchmark-count change follows.
