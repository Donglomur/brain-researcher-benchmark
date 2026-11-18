# MindBridge target7 preparation-to-panel composition

This operator-private component connects the existing complete preparation index
to the registered original Table2 evaluator. The legacy index contains32 cases,
with case-specific opaque query IDs; the evaluator requires six Vanilla/MindBridge
conditions sharing one982-image gallery. `compose_panel` performs that identity
join and carries the source exposure and calibration bindings into the packet.
It does not copy the archive parser, prepare images, run models or compute metrics.

The composer first requires the complete88-file provision receipt, exact original
source pins, all32 indexed cases and all four subjects'8559/300/982 train/validation/
test inventories. It checks full image identities and cross-subject exclusions
before selecting target7. Three target7 metadata/test objects cannot satisfy this
interface. None of the existing completeness checks or preparation files change.

The existing `source-protocol-v2.calibration_memberships` determines all three
train-only prefixes. Calibration IDs retain exact source sample keys, including
variable-width names; the private composition metadata separately binds those keys
to coco73k image IDs. Actual image-ID disjointness is checked across all subjects.
Validation stays separate. The source reset arm retains full8559+300 pretraining
exposure for subjects1/2/5 and each condition's K-example adaptation plus300
validation examples for source and target subjects. Scratch retains target7 only.

Each complete six-condition descriptor bundle declares one information condition:
`paper_data` or `paper_data_author_code`. This field is separate from the source
method arms `vanilla` and `mindbridge`. It has no default. Both information
conditions require their own evidence; no claim of compliant access follows from
a string. Reproduction and improvement remain unknown.

For each registered budget500/1500/4000, the source `scratch` case maps to
`vanilla`, and `reset` maps to `mindbridge`. Opaque query IDs are resolved against
the validated target7 index, regardless of incoming descriptor order. Every query,
condition and gallery entry must be present exactly once. The existing
`original-panel-v1.validate_packet` then checks the shared target descriptors,
eight ordered candidates per image and the original eight-metric payload schema.
No payload is opened. Constant or repeated candidate image contents are not
rejected merely for being identical: those are legitimate poor predictions.

The full inputs and resulting packet are operator-private. They include gallery
identities and target-derived descriptor locations and must never be put in an
agent's candidate view. This module has no candidate-view writer or protected
execution service. The original `prepare.make_view` remains the exposure operator.

## Executable inputs

The CLI requires explicit `--operator-root` and `--implementations-root`. There is
no default pointing to a developer's private directory. The operator root is the
existing private delivery tree; its `../public/protocol.py` must match the private
protocol alias. The implementation root supplies the existing source-protocol-v2
and original-panel-v1 modules. `dependency_pins.json` binds every dependency. The
composer executes only the pinned delivery/protocol/provision and existing
calibration/panel helper bytes. The original preparation generation digest is
recomputed over its existing ordered file list; source parser code is not executed.
NumPy remains an existing transitive import, even though no arrays are created here.

Supply `--plan`, `--receipt` and `--bundle`, each with `--NAME-bytes` and
`--NAME-sha256`. PLAN is the complete unchanged `prepare.index` JSON; RECEIPT is
the complete unchanged `provision.verify` JSON. BUNDLE has exactly:

- `source_kind`, `information_condition`, `skimage_version`,
  `feature_pipeline_sha256`, `image_prior_sha256`, and `conditions`.
- Each of six conditions has `case_id`, `freeze_receipt_sha256`,
  `generation_frozen_before_target_selection`, and982 `images` entries.
- Each image entry has `query_id`, `target`, and eight ordered `candidates`.
  Target and candidate descriptors use the existing original-panel payload schema.

`--max-read-bytes` reserves the sum of the three pinned metadata lengths plus one
EOF/growth probe each before opening them. Individual metadata limits are60MB,
1MB and128MiB respectively. Dependency reads have a separate fixed bound from the
packaged pins, including the protocol alias and a16KiB pin manifest allowance.
Use `--output` for a fresh private file and `--max-output-bytes` for an explicit
allowance no greater than128MiB. These are application I/O bounds, not OS memory
limits or an execution sandbox; a full panel can be large and needs outer resource
admission. Failed reads, output allocation and partial writes remain operator costs.

Hash agreement establishes metadata consistency with the provided pins. It does
not prove that provision/index actually ran on authentic inputs. Input provenance,
historical publication membership, model/runtime identities and freeze chronology
are external obligations. All authenticity/runtime/scientific flags added by this
component are false, and existing metric/protocol holds remain intact.

## Generated checks and integration boundary

The test module builds all four full inventories, all32 cases and all six982-query
conditions in memory. It writes no datasets, image arrays or full fake JSON packets.
Controls exercise wrong or incomplete source receipts, nonselected-source loss,
image leakage, altered prefixes/exposure, opaque query misjoins, condition loss,
target inconsistency, candidate truncation, variable-width sample ordering, access
condition separation and pre-open read-budget refusal. Its combined output is
capped below16KiB. Run it only through the existing shared pool with the two
explicit MINDBRIDGE_OPERATOR_ROOT and MINDBRIDGE_IMPLEMENTATIONS_ROOT variables.

Proposed task-local location is `implementations/target7-composition-v1`. Existing
`source-protocol-v2` and `original-panel-v1` remain sibling dependencies. The legacy
delivery operators are not currently a registered repository implementation, so
public CI cannot silently depend on this workstation's copy. The integrator must
provide the already reviewed exact operator artifact as an explicit CI input, or
separately adopt that existing artifact into the repository. This package does not
vendor or rewrite it. Local composition checks do not establish portable public-CI
readiness, a functioning agent runner, scientific reproduction, or improvement.
