# PAPER-016 dimension and training branch source contract

This package supplies complete declared branch result consumers and nonexecuting
feature/brain operation contracts. It does not fit PCA/SRP, instantiate a model,
read original arrays or scores, calculate empirical RSA/noise ceilings, or claim
to reproduce a historical native run. The paper, released script, and currently
held Net2Brain dependency are separately identified rather than equated.

## Published scope and source-supported membership

Figure 16 compares the three default model types from Figure 2 under PCA, SRP,
and no reduction: 41 image-ImageNet models, 10 image-K400 models, and 41 video-K400
models (92 total). The seven other-action-dataset models are not added to this
figure. Figure 17 reports the two image types only (51 models) on 1,000 training
videos × three repetitions, not 99 models or the 102-video × ten-repeat test set.
Both top panels cover all 17 scientific ROIs and ten subjects. The displayed
depth panels show V2, V3ab, IPS1-3 and OFA; scientific IPS1 remains the identifier.
The released depth function transforms all 17, so the consumer returns all 17
and marks the four displayed ROIs separately.

Membership follows the released configuration order and paper categories. These
are complete declared source branches, not independent evidence that an exact
historical run processed every listed model. SOURCE_SCOUT.json and the peer
scout retain the source/primary-paper evidence and that provenance distinction.

## Operation compiler and its limits

`operations.compile_brain_contract` requires declarations for all ten subjects ×
17 ROIs, with each shape `(102,10,V)` or `(1000,3,V)` and explicitly admitted
stimulus/coordinate metadata. It emits repetition mean on axis 1, `raw2rdm`
without standardization (one minus Pearson correlation), and subject stacking;
there is no external-subject averaging. Training stimulus identities are supplied
and separately admitted. They are never inferred as vid0001…vid1000 from shape.
Test identities must match the held protocol's exact 102 strings.

`operations.compile_model_contract` takes one complete declared separate-NPZ
feature set at a time. It validates all 102 or 1,000 files and every emitted layer
key/shape, preserves natural file/layer execution order, and emits source
estimation, transformation, flattening and Pearson-distance operations. The full
producer key set includes features later excluded from RSA: `rsa_skips` acts at
evaluation, not during RDM creation. `source_axis_layer_order` and natural
`execution_layer_order` therefore remain separate from the post-skip evaluation
catalog. No smaller producer support is silently substituted.

The literal script always passes PCA with 100 components and 102 estimator rows,
including when reader selection is train. The first 102 naturally ordered
training feature files would supply that literal estimator, and the fitted
transform would be applied to all 1,000. The compiler does not change 102 to
1,000 or present this literal current-source contract as the missing historical
Figure 17 run configuration. Feature standardization is absent.

The publication and plot labels identify SRP and no-reduction comparisons, but
the runnable held script hardcodes PCA. Alternative run settings require an
explicit separately admitted `ReductionSpec` and `RunAdmission`. No SRP component
count, eps, density, PCA solver, or seed is inferred from a legend or invented.
Native constructor keywords omitted by source remain omitted. Falsy component
counts follow the source's auto-estimation path and require a resolved estimation
witness; its count then carries to later layers because the iterator mutates
`n_components`. Missing witnesses, natural-sort ties, incomplete or invalid
files/keys, and uninitialized-estimator domains refuse precisely. See the frozen
leaf handoff for its supported semantic domain.

The leaf starts at already-declared features. It does not implement or qualify
upstream frame/subclip extraction. The current MMA preprocessor uses test_mode
for either selection, and the released clip aggregator performs repeated pairwise
means (not uniform averaging of three or more clips); neither is silently
substituted by this package. Dependency/source identities do not establish
historical sklearn/NumPy/torch behavior or native arithmetic parity.

## Catalog and independent branch bindings

`bind_branch` uses the byte-exact frozen catalog compiler with
`require_complete=False`, then requires every member of the selected 92- or
51-model branch to be complete. Missing models outside that scientific branch
remain missing; global99 completion is reported separately and never promoted.
The frozen compiler's existing prerequisite is explicitly a **test102** graph,
checkpoint/framework and emitted-key witness. It is reused for layer identity;
it is not renamed as a training witness. A train-only workflow lacking that test
witness would need a distinct future catalog contract.

Every model/condition also needs separately admitted branch emission, operation
and score-generation receipt descriptors. Full producer layer order and complete
evaluation layer order have different pins. Figure 17 additionally requires the
independent 1,000-stimulus order and all1000 emissions; test metadata cannot prove
them. All ten-person/all17 brain shape/operation/noise-ceiling metadata is bound.
The current authentic catalog/run metadata does not satisfy these closures.

`linkage.model_condition_link` and `brain_support_link` derive compact records
from complete operation contracts so callers can process one model at a time.
The operator still admits the referenced records and numerical artifacts. Child
operation canonical JSON has no newline; frozen catalog canonical JSON has one.
Those byte conventions and hashes are explicit and are not interchangeable.
Neither dataclass construction, digest syntax nor matching hashes authenticates
original data, actual execution or historical provenance.

## Complete result consumer

Figure 16 requires exactly three known source folders: `models_no_dimred`,
`models` (SRP), and `models_pca_rerun`. Their order is explicitly admitted from
`other_folders_compare` followed by the base folder, not guessed from legend
dictionary order. Figure 17 uses one explicitly admitted run folder. PCA bindings
retain the literal 100/102 argument profile; SRP settings stay explicit and
unbound when absent. No-reduction retains any declared ignored arguments without
inventing a fit.

Each `ROIFrame` contains every branch model outermost, then every admitted folder,
then every evaluation layer in source order. `LayerScore.R` is a declared finite
floating signed fMRI RSA mean over ten subjects. The shared brain noise ceilings
are declared finite inputs, not calculated or authenticated here. Missing,
reordered, duplicate/foreign support and invalid numeric values refuse.

For each model/folder/ROI, best layer is the first maximum signed R, not the
maximum absolute correlation. All best-model rows are retained for the original
box/strip data endpoint. Mean and median are separately named summaries; neither
is presented as the complete rendered endpoint. No quantile/CI/jitter/rendering
algorithm is fabricated.

Depth uses the exact frozen source-domain kernel: SlowFast suffix reduction,
smallest tied modal layer count, repeated overlapping middle means, source
integer linspace, preserved endpoints and normalization. For Figure 16, each
ModelTypeFolder is adjusted separately, then all adjusted groups are concatenated
and normalized by Model **across conditions**, matching the released composition.
Output restores source group first appearance, model order and numeric depth.
Nullable aggregated layer names and duplicate singleton endpoints are retained;
no interpolation or silent repair is introduced.

Before obtaining a score iterator, binding validates catalog-known global/group
work bounds, combined normalization geometry, and modal-depth-one nontermination.
Actual counts are also bounded. `run_branch` yields 17 explicitly partial ROI
events, then one `BranchComplete` only after genuine EOF. Late failure, missing
or extra frames produce no terminal receipt. The receipt binds scope, counts,
run identity and length-framed canonical output digest; it is source traversal
completion, never empirical or scientific qualification. No output file is written.

## Remaining work

Actual feature/model/checkpoint/graph bindings, training materialization and
stimulus-order provenance, empirical RSA/null/noise-ceiling production and
native numerical checks remain separately selected work. The existing source
projection is test-only; no training-array conversion was performed here. The
source's unseeded permutation schedule is not replaced by a seeded one. Optional
null/significance, Seaborn defaults/bootstrap CI and historical rendering remain
outside these consumers. Historical SRP parameters and Figure 17 overrides remain
evidence gaps. Figure 18's extra VideoMAE pretraining checkpoint remains a data/
identity gap. This component does not claim whole-paper completion.
