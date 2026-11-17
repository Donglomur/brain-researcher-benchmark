# Physical acquisition join: authoritative V3 source amendment

The model unit is one authenticated physical acquisition and modality. Saved
source keys identify representations and fragments; they never create separate
models for the same physical acquisition. This amendment supersedes the earlier
source-key unit behavior described by the V2 support integration receipt.
All actual original-data/native/model/scoring execution remains paused.

## External lineage certificate

The exact filio_i_lineage_v1 certificate now additionally requires
physical_acquisitions, keyed by private physical acquisition identity. Each value
has exactly animal, session, chronology_evidence, cells and chronology:

- animal/session are authenticated biological hierarchy identifiers.
- chronology_evidence is an exact bytes/SHA256 descriptor that must occur in the
  supplied independently approved evidence_pins list.
- cells maps both CF and GrC to the complete canonical cell-ID lists. A missing
  structural modality has an empty list. A selected source fragment's ordered
  local cell-ID list must be a full bijection to this axis; taking the cell
  intersection or trimming a fragment to convenient cells is prohibited.
- chronology is the reviewed acquisition-wide order of released physical-trial
  rows. Every entry is exactly {trial, source_rows}; source_rows is a nonempty
  list of {source_key, row} references to original released arrays. An entry may
  contain multiple source aliases for the same physical trial. Every original
  released row of member sources, including exclusions and excluded aliases,
  appears exactly once. There are no entries for unobserved physical attempts.

Original per-source acquisitions remain in the certificate. They retain the
complete source-row trial dispositions, modality cell axes, source sample support,
clock evidence, selected-row bijection and encoding binding. Only selected rows
require target/event/sample support. Excluded trial identities may remain null
in the old per-source field when the reviewed chronology supplies their released
row/alias ordering; no target or event values are fabricated for them. Empty
excluded sample-support lists remain explicit. A source containing selected rows
must provide the actual authenticated clock/binding required for those rows.

The physical_acquisitions mapping must cover exactly the required physical
acquisitions represented by selected native views and present required cells.
Its chronology also covers excluded source representations already assigned to
those same physical acquisitions. Outside-scope source census entries remain
preserved separately and do not acquire invented chronology or target data.

Before any fit, admission rejects missing/duplicated released-row membership,
chronology without bound evidence, contradictory source identity or biological
hierarchy, and any physical trial ID reused under another physical acquisition.
No ordering is inferred from filenames, source-array concatenation, local source
row numbers across fragments, or an unseen failed-attempt census.

Five fold positions are assigned once using min(4, floor(5*i/N)), where i is the
reviewed physical chronology ordinal and N includes its excluded released rows.
Every original alias receives its physical trial's same fold. Direct sample
support is compared across all original aliases/modalities; only training trials
are purged against held support. Queries retain every originally eligible
physical trial. Each joined physical acquisition/modality must support all five
outer folds and all four inner folds after purge; incomplete required support
fails rather than creating a reduced experiment.

## Support join

support.prepare still accepts paper_i_worker_support_v1 and writes SUPPORT.json.
Its existing units array now has exactly one unit for each required physical
acquisition/modality, with source_key naming a joined acquisition. The existing
unit_id/modality/cell_tokens/time_count/selected_rows/outer fields and nested
train/query/validation/purged_train shape remain unchanged. Rows in those arrays
are physical chronology ordinals, not fragment-local ordinals.

SUPPORT.acquisitions contains private paper_i_joined_acquisition_v1 objects:

- key: deterministic private joined key; original_trial_count: released chronology
  length; views: union of native views contributed by eligible representations.
- source_acquisitions: original admitted source objects, retaining each original
  array descriptor, behavior clock, source dtb, source context and clock binding.
- trial_sources[modality]: a complete chronology-length list of either null or
  {source_key, row, cell_indices}. cell_indices maps the canonical physical cell
  axis to the original source axis. A null entry is not an omitted query: it is
  an explicit row without originally eligible observed support for that modality.
- modalities: present modality cell counts and a common target_time descriptor,
  or an explicit structural absence. Joined targets are never fabricated as a
  concatenated NPY body. Original target bodies remain behind source references.
- released_chronology and chronology_evidence: complete reviewed row/alias order.
- observed_modalities: one list per chronology ordinal, derived only from non-null
  trial_sources. It describes observed structural support, never neural values.
- private_unit_metadata[modality]: the existing animal/session/acquisition/trials/
  cells/categorical_vocabulary fields, plus trial_views[str(joined_row)] lists.
  trials is the full physical chronology; trial_views includes only views
  contributed by originally eligible representations. Excluded aliases never
  add diagnostic view membership.

SUPPORT additionally retains original_source_acquisitions and the complete
all_original_row_dispositions map. The aliases list includes original/canonical
source rows, joined rows and physical IDs. An excluded source alias may coexist
with an eligible representation without becoming eligible itself. Multiple
eligible representations are collapsed only after complete canonical-cell
trajectory, exact target grid and legal retrospective record equality checks.

Within a physical acquisition/modality, every selected fragment must have the
exact same native target grid. A mismatch fails explicitly; the join does not
resample targets. Behavior clocks may differ between fragments and are retained
exactly. Each record is computed through its original one_record source path and
source clock; there is no synthetic common behavior grid or invented dtb.
Paired observed modalities must agree on the authenticated discrete physical
trial context before the shared null is admitted.

## Views and trusted worker

views.source_reference resolves a physical row to its original source, local row
and canonical cell permutation. views.context_for_row extracts the private source
context through that reference. views.target_trajectory is operator-only and
returns the complete canonical cell trajectory from the original target body.
A query never calls target_trajectory or dereferences a neural target body.

one_record supports both original source objects and joined objects. A joined
record checks the exact common target grid, then delegates to the original source
record builder. All 47 movement features, source timing, measured delay, profile
field restrictions and source mask checks are unchanged.

training_view supports joined objects without synthesizing shared source arrays.
It gathers complete original trajectories, applies the canonical cell permutation,
then applies the private training-only whole-trajectory reassignment (if selected),
then flattens physical trial/time rows. Weights and overall fold-training means
are computed once over the complete joined training population. Private indexing
retains joined source_row, original source_key and original_source_row. No fit
occurs during view construction.

worker.make_view accepts the same paper_i_worker_views_v1 payload with a joined
acquisition object. It loads only the referenced original source collections
needed by the selected training/held rows plus the common target-grid descriptor.
Public TRAIN still contains the full selected population Y and relative Y.npy/
weights.npy paths; final reference column selection occurs only during fitting.
Held private truth uses canonical physical cell order. Every original target
path is removed from the array map supplied to query construction. Public M
records remain movement-only, with no physical IDs, categories or row clocks.

## Paired modality null

The private wrapped permutation request remains exactly {physical_trials, seed}.
Physical IDs are reviewed private strings: any nonempty UTF-8 string up to
1,024 bytes is legal, including ':' and '/'. Public opaque-token restrictions do
not narrow this private identity domain. IDs must be unique and correspond to
the supplied training rows; the controller authenticates that partition binding.
The seed is a shared private int63 per physical acquisition/fold/inner fold.

For joined views, strata are the four discrete source categories plus the
source-derived observed_modalities signature. This preserves paired observed
trajectories while allowing legitimate unpaired structural support. Inside each
stratum, physical IDs are sorted and shuffled using PCG64. Each stratum's private
seed is the first 128 bits of SHA256(encoded({seed, stratum})), where encoded is
core.encoded and stratum is (canonical category tuple, ordered availability tuple).
Thus additional unpaired strata cannot advance the RNG for a shared paired
stratum. Paired rows get the same reassignment even when modality training sets
are not identical. Explicit private row maps must also preserve both context and
availability strata. No map, seed, identity or private receipt enters public
TRAIN/query/model candidate metadata.

## Focused engineering controls

physical_join_controls.py uses only invented RAM primitives and no fits. Its 19
checks cover interleaved fragments, a shared physical unit and training mean,
canonical reversed cell order, original 21/41-point behavior clocks, excluded
released rows with unavailable targets/support, all five-by-four folds, paired
and unpaired null support, private slash/colon IDs, source alias eligibility and
view unions, incomplete chronology/cells/grids, cross-acquisition physical-trial
reuse refusal, no neural query exposure and the controller-shaped absolute
/input/CLOSED.json report reference. Old V2 receipts and worker/views sources
are preserved; their historical checks are not promoted as V3 execution evidence.
No runtime/readiness/qualification, benchmark IDs, shared registry, OpenBMI hold
or actual scientific result is changed by this source amendment.
