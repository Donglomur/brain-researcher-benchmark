# Dimension and split operation contracts

`operation_contracts.py` is an executable, standard-library compiler of immutable
source-operation contracts. It validates complete declared support and chooses
the released source branches. It does not open a feature or brain file, load a
model, create an array, run a native library, fit PCA/SRP, or calculate an RDM.
Every output keeps authenticity, native execution, historical equivalence and
scientific qualification false.

The contract combines the pinned author driver/reader with the separately held
**current** Net2Brain donor. Those source pins do not establish that this donor
version, its sklearn defaults, or any declared run profile produced a historical
paper figure. Figure 17's intended image-model/training scope and the known
missing historical facts are in `FIG17_SCOUT.json`.

## Public interface

The frozen source dataclasses are:

- `SplitSpec(name, stimuli, repetitions)`; only `TEST_SPLIT` (`test`,102,10) or
  `TRAIN_SPLIT` (`train`,1000,3) is admitted.
- `StimulusSupport(ordered_ids, order_sha256, admission_record_sha256)`.
- `BrainRecord(subject, roi, shape, stimulus_order_sha256,
  coordinate_admission_sha256)` and
  `BrainSupport(stimuli, records, metadata_admission_sha256)`.
- `LayerShape(layer, shape)`, `FeatureFile(basename, stimulus_id, layers)`, and
  `FeatureSupport(model_id, stimuli, expected_layer_order, files,
  metadata_admission_sha256, root_path="features",
  feature_format="NPZ_SEPARATE")`.
- `ReductionSpec(branch, method, n_samples_estim, n_components,
  max_dim_allowed=None)` and
  `RunAdmission(run_spec_sha256, admission_record_sha256, origin)`.
- `EstimationWitness(model_id, layer, run_spec_sha256, input_metadata_sha256,
  estimation_prefix_sha256, resolved_components, witness_record_sha256,
  admission_record_sha256)`.

All tuples are explicit, immutable metadata. A declared shape has positive
integer dimensions, at most16 axes; scalar feature shape `()` is supported.
These fields are not authenticated file headers, original coordinate bodies,
native dtypes, or proof of numerical compatibility. Admission pins are syntactic
and internal-binding gates. The parent must capture, verify and admit the actual
records they refer to; a matching digest alone cannot establish authenticity.

`compile_brain_contract(split, support, *, budget)` requires exactly all
10 source subjects ×17 source ROI identifiers. It validates each unaveraged
shape `(stimuli,repetitions,voxels)`, the shared stimulus-order declaration and
the presence of individual coordinate admission references. It emits split-key
selection, repetition mean along axis1, source `1 - np.corrcoef(raw)` with
`dim=None`, stacking in subject order, and `average_external=False`.
No subject, voxel, ROI or repetition is silently dropped. `IPS1` is the source
identifier; the paper displays it as `IPS1-3`.

`compile_model_contract(split, support, reduction, *, budget,
run_admission=None, estimation_witnesses=())` compiles one model. The parent can
stream models without retaining a whole paper's per-file metadata or contracts.
The result is `ModelContract`, with source-axis order and natural execution order
kept separately. Its per-layer contracts retain shape/squeeze/flatten decisions,
constructor keyword tuples, fitting/transform operation declarations, component
state before/after, and RDM declarations. They contain no numerical features.

`summarize_contract(contract, *, budget)` returns a small immutable
`ContractSummary`: kind, canonical contract digest, split, stimulus-order digest,
model ID, full producer layer order, run-spec digest and false qualification
flags. The parent may retain that linkage and discard the detailed body. The
body must be retained or reproducibly reconstructed if its digest is to support
later review. Summarization itself does not authenticate the body or execution.

`literal_script_pca()` returns the exact driver profile:
`ReductionSpec("literal_author_script","pca",102,100,None)`. This applies to
both test and train. The train branch estimates on the first102 naturally ordered
files and transforms all1000, according to the current donor. It does not quietly
change estimator rows to1000. `RunAdmission` is not attached to this literal
source branch because it conveys no historical-run claim.

Other profiles use `branch="explicit_run_spec"` and require a matching
`RunAdmission`, with origin `prospective` or
`declared_historical_run_metadata`. Missing SRP parameters remain unbound until
such an explicit run spec is supplied and separately admitted by the parent.
Neither origin promotes historical equivalence or qualification. A declared
historical reference is not a verified historical result.

## Source branch decisions preserved

**Complete support and ordering.** Test IDs are the exact102 held protocol
strings `vid1001` through `vid1102`. Train IDs are supplied independently with a
separate1000-element order/admission witness; they are never inferred from a
shape or a `vid0001` naming guess. Every separate-NPZ file must be declared,
have its stem equal the declared stimulus identity, and provide exactly the
full layer-key set. All declared per-layer shapes must match across stimuli.
Natural file order must equal the admitted brain-stimulus order.

The source naturally sorts file stems, then naturally sorts layer keys from the
first file. No lexical ordering is substituted. Natural-key ties, such as
`layer1` and `layer01`, require an original enumeration order that is not held;
this profile refuses them. It also refuses extra non-NPZ files instead of
implementing the source's misleading warning-and-continued-load path, and
refuses consolidated/HDF5 format or names that would trigger consolidated
format detection.

**Full producer keys versus analysis layers.** `expected_layer_order` is the
complete **emitted feature-key** axis. The source RDM creator processes all
those keys; `rsa_skips` is applied later by RSA. The parent must bind the separate
post-skip evaluation catalog and its source-order rules. Supplying only that
evaluation subset as a supposedly complete producer archive would narrow the
source operation. The leaf never performs that substitution.

**Reduction.** The threshold is source truthiness plus strict greater-than:
reduction applies if the method is truthy and `(not max_dim_allowed or
feature_width > max_dim_allowed)`. Thus a zero threshold means reduction always
applies, and equality with a positive threshold bypasses it. When the method is
`None`, RDMCreator calls `FeatureIterator(feature_path)` without **any** reduction
keywords. The compiler preserves supplied ignored values in the run spec but
does not forward them or invent replacements.

The source squeezes the sample shape and promotes a scalar shape to `(1,)`.
Reduced features use an estimator array for the selected prefix, reshape it to
`(n_samples_estim,-1)`, fit per layer, and transform every stimulus separately.
Requested estimator rows exceeding available files are refused: the released
source allocates `np.empty` and would leave trailing estimator rows uninitialized.
There is no padding, cycling, dropping or guessed replacement sample count.

**Constructor omissions.** Fixed PCA/SRP passes only `n_components`. Automatic
PCA passes `n_components="mle"`; automatic SRP passes no constructor keywords.
No solver, random state, epsilon, dtype or other backend default is supplied by
this compiler. Array allocations record `dtype_keyword="omitted"`, preserving
the source's constructor omission rather than inventing an original dtype.
Native library version/default resolution is a remaining execution requirement.

**Automatic component state.** `None` and integer0 enter the source's automatic
branch. The first layer that actually reduces must have a resolution witness
bound to the model, layer, run spec, complete input metadata and estimator-prefix
digest. That layer declares `fit_transform`; its resolved count becomes mutable
engine state and subsequent reducing layers declare fixed-count `fit` calls.
Bypassed layers retain the state. Later layers do not independently re-estimate
an automatic count. Missing, wrong-bound, duplicate or unused witnesses refuse.
Witnesses describe an admitted resolution; the compiler does not run or verify
the fit that allegedly produced it.

**RDM declarations.** After loading/reducing, the source converts to a torch
tensor, flattens from dimension1 and calls Pearson distance with no
standardization. The leaf emits that exact operation chain and explicit stimulus
order, without executing or qualifying the native distance implementation. It
does not perform raw RSA, best-layer selection, null tests, depth aggregation,
confidence intervals or plotting; those consumers belong to the parent.

## Remaining domains and resources

This is a complete operation compiler for its declared support profile, not a
promise that native numerical execution succeeds. Shape broadcasting beyond
identical declared input shapes, unsupported dtypes, solver/rank constraints,
memory, device availability, zero-variance Pearson inputs and finite numerical
outcomes require separate native/input admission. Source coordinates, stimuli,
features, graph/checkpoint identity and emitted layer completeness remain
unverified. The graph-derived catalog prerequisite is not satisfied by a digest.
Current donor provenance remains distinct from the paper's historical runtime.

`SerializationBudget(limit_bytes, used_bytes=0)` is explicit mutable cost
accounting, separate from immutable contracts. `canonical_size` measures exact
ASCII-escaped JSON size without producing the encoded payload;
`canonical_bytes` checks and precharges that count before encoding;
`canonical_digest` and `summarize_contract` use that same path. Nonfinite or
other float canonical values and opaque objects are outside this metadata-only
profile. Failed calls retain already incurred charges. A serialization cap is
not a process-memory, wall-clock, native-fitting or physical-retention cap.

The author's twelve groups executed once after a tiny serializer probe. Only
one full1000-file metadata model and one170-record brain fixture were built;
other controls use small102-file metadata examples and no feature/brain arrays.
All fixture-file writes were zero. The initial probe discovered a five-byte DEL
undercharge, which was corrected and retained in cumulative costs. Boundary
controls cover ASCII, DEL, non-ASCII, surrogates and non-BMP characters, including
refusal before the JSON encoder is called. See BUILD_RESULTS for the closed
799,345-byte cumulative canonical cost and measured live allocation.

The initial author canonical allowance/test cap was 8 MiB. After those tests
passed, the parent prospectively reassigned parent/child authority first to
10/6 MiB and later to 12/4 MiB, preserving their combined 16 MiB. The second
amendment followed parent-side pre-encoding guard refusals, retained in the
parent ledger; it did not refund or reset costs. This leaf's closed 799,345 bytes
remain below every applicable cap, leaving 3,394,959 bytes under its current
4 MiB cumulative authority. Original caps and the five-byte shortcharge remain
recorded. No further leaf fixture execution is planned. Future runs must apply
the then-current remaining allowance rather than blindly replaying the original
test module's historical 8 MiB cap.
