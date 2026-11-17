"""Compile immutable declared operations; never open payloads or fit models.

Current held source is separate from the historical publication runtime. Every
shape, coordinate, support and admission input is a declaration, not evidence
that an original file was inspected or a native operation will succeed.
"""

from dataclasses import dataclass, fields, is_dataclass
import hashlib
import json
from math import prod
import re


class ContractError(ValueError):
    pass


class SerializationLimitError(ContractError):
    pass


@dataclass
class SerializationBudget:
    """Cumulative canonical bytes precharged before each actual serialization."""

    limit_bytes: int
    used_bytes: int = 0

    def reserve(self, size):
        if (type(self.limit_bytes) is not int or self.limit_bytes < 0
                or type(self.used_bytes) is not int or self.used_bytes < 0
                or type(size) is not int or size < 0):
            raise ContractError("serialization_budget_domain")
        if size > self.limit_bytes - self.used_bytes:
            raise SerializationLimitError("canonical_serialization_cap_before_encoding")
        self.used_bytes += size


def _string_size(value):
    size = 2
    for char in value:
        point = ord(char)
        if char in '\\"\b\f\n\r\t':
            size += 2
        elif point < 32:
            size += 6
        elif point < 127:
            size += 1
        elif point <= 65535:
            size += 6
        else:
            size += 12
    return size


def _mapping_items(value):
    if is_dataclass(value) and not isinstance(value, type):
        return tuple((field.name, getattr(value, field.name)) for field in sorted(fields(value), key=lambda f: f.name))
    if type(value) is dict and all(type(key) is str for key in value):
        return tuple(sorted(value.items()))
    return None


def canonical_size(value):
    """Exact ensure_ascii JSON size without generating the serialized payload."""
    if value is None:
        return 4
    if type(value) is bool:
        return 4 if value else 5
    if type(value) is int:
        return len(str(value))
    if type(value) is str:
        return _string_size(value)
    if type(value) in (tuple, list):
        return 2 + max(0, len(value) - 1) + sum(canonical_size(part) for part in value)
    items = _mapping_items(value)
    if items is not None:
        return 2 + max(0, len(items) - 1) + sum(_string_size(key) + 1 + canonical_size(part) for key, part in items)
    raise ContractError("canonical_domain_no_floats_or_opaque_objects")


def _plain(value):
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) in (tuple, list):
        return [_plain(part) for part in value]
    items = _mapping_items(value)
    if items is not None:
        return {key: _plain(part) for key, part in items}
    raise ContractError("canonical_domain")


def canonical_bytes(value, budget):
    if type(budget) is not SerializationBudget:
        raise ContractError("explicit_serialization_budget_required")
    measured = canonical_size(value)
    budget.reserve(measured)
    encoded = json.dumps(_plain(value), sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(encoded) != measured:
        raise AssertionError("canonical_size_measurement_mismatch_charge_retained")
    return encoded


def canonical_digest(value, budget):
    return hashlib.sha256(canonical_bytes(value, budget)).hexdigest()


SOURCE_PINS = (
    ("author_calc_alignment", "5fc377b8808d6a5c31752f54fb0d15ed16e96855d737f7266fe8246238070e25"),
    ("author_reader", "d515b5e2340cf965dfde3744711f1c1260bc75e2c57db7fb03e5831ae8bdcf20"),
    ("author_common", "045bb62b1d389d5ca9bd2cf626a8c3c44ea724b613b7fb626da7d7f8d439ac75"),
    ("current_dim_reduction", "c12faa637f2445b86b914d416fc9350daa1e6e9590260ed00a73325589d20af1"),
    ("current_feature_iterator", "0e6ebcfce2777caba2e6f0ce186576ca712eee86f111a8014a639c472994322e"),
    ("current_rdm_creation", "192a4560713bdeff6f72af2453ef76f6efe49556664e946df8e9efe008bb79db"),
    ("held_protocol", "59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c"),
)
# Derived from the held protocol's explicit 102 strings; NOT a train-ID rule.
TEST_STIMULI = tuple("vid" + str(number) for number in range(1001, 1103))
SUBJECTS = tuple("sub-" + str(number).zfill(2) for number in range(1, 11))
ROIS = ("V1", "V2", "V3v", "V3d", "hV4", "OFA", "LOC", "FFA", "PPA",
        "V3ab", "IPS0", "IPS1", "RSC", "EBA", "TOS", "MT", "STS")


@dataclass(frozen=True)
class SplitSpec:
    name: str
    stimuli: int
    repetitions: int


TEST_SPLIT = SplitSpec("test", 102, 10)
TRAIN_SPLIT = SplitSpec("train", 1000, 3)


@dataclass(frozen=True)
class StimulusSupport:
    ordered_ids: tuple
    order_sha256: str
    admission_record_sha256: str


@dataclass(frozen=True)
class BrainRecord:
    subject: str
    roi: str
    shape: tuple
    stimulus_order_sha256: str
    coordinate_admission_sha256: str


@dataclass(frozen=True)
class BrainSupport:
    stimuli: StimulusSupport
    records: tuple
    metadata_admission_sha256: str


@dataclass(frozen=True)
class LayerShape:
    layer: str
    shape: tuple


@dataclass(frozen=True)
class FeatureFile:
    basename: str
    stimulus_id: str
    layers: tuple


@dataclass(frozen=True)
class FeatureSupport:
    model_id: str
    stimuli: StimulusSupport
    expected_layer_order: tuple
    files: tuple
    metadata_admission_sha256: str
    root_path: str = "features"
    feature_format: str = "NPZ_SEPARATE"


@dataclass(frozen=True)
class ReductionSpec:
    branch: str
    method: object
    n_samples_estim: object
    n_components: object
    max_dim_allowed: object = None


def literal_script_pca():
    return ReductionSpec("literal_author_script", "pca", 102, 100, None)


@dataclass(frozen=True)
class RunAdmission:
    run_spec_sha256: str
    admission_record_sha256: str
    origin: str


@dataclass(frozen=True)
class EstimationWitness:
    model_id: str
    layer: str
    run_spec_sha256: str
    input_metadata_sha256: str
    estimation_prefix_sha256: str
    resolved_components: int
    witness_record_sha256: str
    admission_record_sha256: str


@dataclass(frozen=True)
class Operation:
    name: str
    source: str
    arguments: tuple


@dataclass(frozen=True)
class LayerContract:
    layer: str
    original_feature_shape: tuple
    squeezed_feature_shape: tuple
    flattened_width: int
    reduction_applied: bool
    components_before: object
    components_after: object
    constructor: object
    other_constructor_keywords: str
    estimation_witness_sha256: object
    operations: tuple


@dataclass(frozen=True)
class ModelContract:
    split: SplitSpec
    model_id: str
    stimulus_order: tuple
    source_axis_layer_order: tuple
    execution_layer_order: tuple
    input_metadata_sha256: str
    run_spec: ReductionSpec
    run_spec_sha256: str
    run_admission: object
    iterator_kwargs: tuple
    layer_contracts: tuple
    source_pins: tuple = SOURCE_PINS
    metadata_authenticity_verified: bool = False
    native_executed: bool = False
    historical_runtime_equivalence: bool = False
    scientific_qualified: bool = False


@dataclass(frozen=True)
class BrainContract:
    split: SplitSpec
    stimulus_order: tuple
    subject_order: tuple
    roi_order: tuple
    input_metadata_sha256: str
    operations: tuple
    source_pins: tuple = SOURCE_PINS
    metadata_authenticity_verified: bool = False
    native_executed: bool = False
    historical_runtime_equivalence: bool = False
    scientific_qualified: bool = False


@dataclass(frozen=True)
class ContractSummary:
    kind: str
    canonical_sha256: str
    split: SplitSpec
    stimulus_order_sha256: str
    model_id: object
    layer_order: tuple
    run_spec_sha256: object
    metadata_authenticity_verified: bool = False
    native_executed: bool = False
    historical_runtime_equivalence: bool = False
    scientific_qualified: bool = False


def _sha(value, label):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(label + "_sha256")


def _split(split):
    if type(split) is not SplitSpec or split not in (TEST_SPLIT, TRAIN_SPLIT):
        raise ContractError("exact_test102x10_or_train1000x3_split_required")


def _string(value, label):
    if type(value) is not str or not value or "\x00" in value:
        raise ContractError(label + "_nonempty_plain_string")


def _shape(shape, scalar=False):
    if (type(shape) is not tuple or (not scalar and not shape) or len(shape) > 16
            or any(type(value) is not int or value < 1 for value in shape)):
        raise ContractError("declared_positive_shape_domain")


def validate_stimulus_support(split, support, budget):
    _split(split)
    if type(support) is not StimulusSupport or type(support.ordered_ids) is not tuple:
        raise ContractError("stimulus_support_type")
    if len(support.ordered_ids) != split.stimuli:
        raise ContractError("full_split_stimulus_count")
    for identity in support.ordered_ids:
        _string(identity, "stimulus_identity")
    if len(set(support.ordered_ids)) != split.stimuli:
        raise ContractError("duplicate_stimulus_identity")
    if split == TEST_SPLIT and support.ordered_ids != TEST_STIMULI:
        raise ContractError("test_order_not_held_protocol102")
    _sha(support.order_sha256, "stimulus_order")
    _sha(support.admission_record_sha256, "separate_stimulus_admission")
    if canonical_digest(support.ordered_ids, budget) != support.order_sha256:
        raise ContractError("stimulus_order_digest_mismatch")
    # Train IDs are supplied and separately admitted, never inferred from shape.
    return support


def _natural_key(text):
    try:
        return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text))
    except ValueError as error:
        raise ContractError("source_natural_key_integer_conversion_domain") from error


def _natural_order(values, label):
    keyed = tuple((_natural_key(value), value) for value in values)
    if len({key for key, _ in keyed}) != len(keyed):
        raise ContractError(label + "_natural_sort_tie_requires_unheld_enumeration_order")
    try:
        return tuple(value for _, value in sorted(keyed, key=lambda pair: pair[0]))
    except TypeError as error:
        raise ContractError("source_natural_sort_comparison_domain") from error


def _validate_reduction(spec, admission, budget):
    if type(spec) is not ReductionSpec:
        raise ContractError("reduction_spec_type")
    if spec.method not in (None, "pca", "srp"):
        raise ContractError("source_reduction_method")
    if spec.method is not None:
        if type(spec.n_samples_estim) is not int or spec.n_samples_estim < 1:
            raise ContractError("positive_estimator_rows_required")
        if spec.n_components is not None and (type(spec.n_components) is not int or spec.n_components < 0):
            raise ContractError("nonnegative_integer_or_none_component_domain")
        if spec.max_dim_allowed is not None and (type(spec.max_dim_allowed) is not int or spec.max_dim_allowed < 0):
            raise ContractError("nonnegative_integer_or_none_threshold_domain")
    else:
        # Explicitly retaining even supplied ignored arguments is allowed, but
        # only primitive source parameter forms belong to this metadata profile.
        for value in (spec.n_samples_estim, spec.n_components, spec.max_dim_allowed):
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError("ignored_reduction_argument_metadata_domain")
    spec_sha = canonical_digest(spec, budget)
    if spec.branch == "literal_author_script":
        if spec != literal_script_pca() or admission is not None:
            raise ContractError("literal_script_is_exact_pca100_estim102_without_historical_admission")
    elif spec.branch == "explicit_run_spec":
        if type(admission) is not RunAdmission:
            raise ContractError("explicit_run_spec_admission_required_historical_parameters_unbound")
        _sha(admission.run_spec_sha256, "run_spec")
        _sha(admission.admission_record_sha256, "run_admission")
        if admission.run_spec_sha256 != spec_sha:
            raise ContractError("run_admission_spec_mismatch")
        if admission.origin not in ("prospective", "declared_historical_run_metadata"):
            raise ContractError("run_admission_origin")
    else:
        raise ContractError("source_branch_must_be_explicit")
    return spec_sha


def compile_brain_contract(split, support, *, budget):
    """Emit complete 10-subject/17-ROI preprocessing declarations, not RDMs."""
    _split(split)
    if type(support) is not BrainSupport or type(support.records) is not tuple:
        raise ContractError("brain_support_type")
    validate_stimulus_support(split, support.stimuli, budget)
    _sha(support.metadata_admission_sha256, "brain_metadata_admission")
    expected = {(subject, roi) for subject in SUBJECTS for roi in ROIS}
    seen = set()
    for record in support.records:
        if type(record) is not BrainRecord:
            raise ContractError("brain_record_type")
        key = (record.subject, record.roi)
        if key not in expected or key in seen:
            raise ContractError("brain_subject_roi_identity_or_duplicate")
        seen.add(key)
        _shape(record.shape)
        if len(record.shape) != 3 or record.shape[:2] != (split.stimuli, split.repetitions):
            raise ContractError("brain_complete_unaveraged_stimulus_repetition_axes")
        if record.stimulus_order_sha256 != support.stimuli.order_sha256:
            raise ContractError("brain_stimulus_order_declaration_mismatch")
        _sha(record.coordinate_admission_sha256, "brain_voxel_coordinate_admission")
    if seen != expected:
        raise ContractError("complete_10_subject_17_roi_support_required")
    metadata_sha = canonical_digest(support, budget)
    operations = (
        Operation("select_split_array", "author_reader.BMDReader.read_data", (("key", split.name + "_data_allvoxel"), ("count", 170))),
        Operation("mean_repetitions", "author_reader.BMDReader.read_data", (("axis", 1), ("input_axes", ("stimulus", "repetition", "voxel")), ("input_count_per_stimulus", split.repetitions))),
        Operation("brain_pearson_distance", "author_common.raw2rdm", (("dim", None), ("expression", "1 - np.corrcoef(raw)"), ("standardization_applied", False))),
        Operation("stack_subject_rdms_per_roi", "author_reader.BMDReader.read_data", (("expand_axis", 0), ("concatenate_axis", 0), ("subject_order", SUBJECTS), ("output_shape_per_roi", (10, split.stimuli, split.stimuli)))),
        Operation("retain_subject_axis", "author_reader.BMDReader.read_data", (("average_external", False),)),
    )
    return BrainContract(split, support.stimuli.ordered_ids, SUBJECTS, ROIS, metadata_sha, operations)


def compile_model_contract(split, support, reduction, *, budget, run_admission=None, estimation_witnesses=()):
    """Compile one model, retaining complete declared layer/stimulus support.

    The parent can stream these per-model contracts. No library constructor,
    feature file, array, payload hash, model graph or numerical fit is executed.
    """
    _split(split)
    if type(support) is not FeatureSupport or type(support.files) is not tuple:
        raise ContractError("feature_support_type")
    _string(support.model_id, "model")
    validate_stimulus_support(split, support.stimuli, budget)
    _sha(support.metadata_admission_sha256, "feature_metadata_admission")
    _string(support.root_path, "declared_root_path")
    if support.feature_format != "NPZ_SEPARATE" or "consolidated" in support.root_path:
        raise ContractError("only_declared_separate_npz_source_branch_supported")
    if type(support.expected_layer_order) is not tuple or not support.expected_layer_order:
        raise ContractError("complete_source_layer_axis_required")
    for layer in support.expected_layer_order:
        _string(layer, "source_layer")
    expected_layers = set(support.expected_layer_order)
    if len(expected_layers) != len(support.expected_layer_order):
        raise ContractError("duplicate_expected_layer")
    if len(support.files) != split.stimuli:
        raise ContractError("complete_separate_npz_file_count")
    filenames = []
    file_lookup = {}
    shapes_by_layer = {}
    for file in support.files:
        if type(file) is not FeatureFile:
            raise ContractError("feature_file_metadata_type")
        _string(file.basename, "feature_basename")
        if ("/" in file.basename or "\\" in file.basename or not file.basename.endswith(".npz")
                or "consolidated" in file.basename or file.basename in file_lookup):
            raise ContractError("extraneous_non_npz_or_ambiguous_feature_basename")
        if file.stimulus_id != file.basename[:-4]:
            raise ContractError("source_stimulus_identity_is_file_stem")
        if type(file.layers) is not tuple:
            raise ContractError("feature_layer_metadata_tuple")
        layers = {}
        for layer in file.layers:
            if type(layer) is not LayerShape:
                raise ContractError("layer_shape_type")
            _string(layer.layer, "feature_layer")
            if layer.layer in layers:
                raise ContractError("duplicate_npz_layer_key")
            _shape(layer.shape, scalar=True)
            layers[layer.layer] = layer.shape
            if layer.layer in shapes_by_layer and shapes_by_layer[layer.layer] != layer.shape:
                raise ContractError("unmodeled_cross_stimulus_shape_or_broadcast_domain")
            shapes_by_layer[layer.layer] = layer.shape
        if set(layers) != expected_layers:
            raise ContractError("every_file_requires_complete_exact_layer_support")
        filenames.append(file.basename)
        file_lookup[file.basename] = file
    ordered_filenames = _natural_order(filenames, "stimulus_filename")
    ordered_ids = tuple(file_lookup[name].stimulus_id for name in ordered_filenames)
    if ordered_ids != support.stimuli.ordered_ids:
        raise ContractError("natural_feature_order_not_admitted_brain_stimulus_order")
    first_keys = tuple(layer.layer for layer in file_lookup[ordered_filenames[0]].layers)
    execution_layers = _natural_order(first_keys, "layer_key")
    spec_sha = _validate_reduction(reduction, run_admission, budget)
    metadata_sha = canonical_digest(support, budget)
    if type(estimation_witnesses) is not tuple:
        raise ContractError("estimation_witness_tuple")
    witnesses = {}
    for witness in estimation_witnesses:
        if type(witness) is not EstimationWitness or witness.layer in witnesses:
            raise ContractError("estimation_witness_type_or_duplicate")
        witnesses[witness.layer] = witness
    if reduction.method:
        iterator_kwargs = (("dim_reduction", reduction.method), ("n_samples_estim", reduction.n_samples_estim),
                           ("n_components", reduction.n_components), ("max_dim_allowed", reduction.max_dim_allowed))
        components = reduction.n_components
    else:
        # RDMCreator's else branch calls FeatureIterator(feature_path), ignoring
        # ALL supplied reduction arguments. Do not forward guessed defaults.
        iterator_kwargs = ()
        components = None
    layers = []
    consumed = set()
    prefix_sha = None
    for name in execution_layers:
        original_shape = shapes_by_layer[name]
        squeezed = tuple(size for size in original_shape if size != 1) or (1,)
        width = prod(original_shape)
        reduced = bool(reduction.method and (not reduction.max_dim_allowed or width > reduction.max_dim_allowed))
        before = components
        constructor = None
        witness_sha = None
        operations = [Operation("sample_squeeze", "current_feature_iterator.NPZSeparateEngine.next", (("shape", squeezed), ("scalar_promoted_to_shape_one", not any(size != 1 for size in original_shape))))]
        if reduced:
            if reduction.n_samples_estim > split.stimuli:
                raise ContractError("source_uninitialized_estimator_rows_samples_less_than_n_samples_estim")
            if before:
                constructor_kwargs = (("n_components", before),)
                fit_call = "fit"
            else:
                constructor_kwargs = (("n_components", "mle"),) if reduction.method == "pca" else ()
                fit_call = "fit_transform"
                witness = witnesses.get(name)
                if witness is None:
                    raise ContractError("automatic_component_resolution_requires_bound_estimation_witness:" + name)
                if prefix_sha is None:
                    prefix_sha = canonical_digest(ordered_ids[:reduction.n_samples_estim], budget)
                if (witness.model_id != support.model_id or witness.run_spec_sha256 != spec_sha
                        or witness.input_metadata_sha256 != metadata_sha
                        or witness.estimation_prefix_sha256 != prefix_sha):
                    raise ContractError("estimation_witness_model_run_input_prefix_binding")
                if type(witness.resolved_components) is not int or witness.resolved_components < 1:
                    raise ContractError("positive_resolved_component_witness")
                _sha(witness.witness_record_sha256, "estimation_record")
                _sha(witness.admission_record_sha256, "estimation_admission")
                components = witness.resolved_components
                consumed.add(name)
                witness_sha = canonical_digest(witness, budget)
            constructor = Operation("PCA" if reduction.method == "pca" else "SparseRandomProjection",
                                    "current_dim_reduction.estimate_from_files", constructor_kwargs)
            operations.extend((
                Operation("allocate_estimator_rows", "current_dim_reduction.estimate_from_files", (("shape", (reduction.n_samples_estim,) + squeezed), ("dtype_keyword", "omitted"))),
                Operation("fill_estimator_prefix", "current_dim_reduction.estimate_from_files", (("natural_stimulus_prefix_length", reduction.n_samples_estim), ("layer", name), ("source_operation", "open_func(file)[key].squeeze()"))),
                Operation("reshape_estimator", "current_dim_reduction.estimate_from_files", (("shape", (reduction.n_samples_estim, -1)),)),
                Operation(fit_call, "current_dim_reduction.estimate_from_files", (("input_shape", (reduction.n_samples_estim, width)),)),
                Operation("carry_component_state", "current_feature_iterator.NPZSeparateEngine.next", (("components_before", before), ("components_after", components), ("state_lifetime", "this model engine across later layers"))),
                Operation("transform_every_stimulus", "current_feature_iterator.NPZSeparateEngine.next", (("stimulus_count", split.stimuli), ("input_reshape", (1, -1)), ("output_shape", (split.stimuli, components)), ("output_dtype_keyword", "omitted"))),
            ))
        else:
            operations.append(Operation("load_every_stimulus_without_reduction", "current_feature_iterator.NPZSeparateEngine.next", (("output_shape", (split.stimuli,) + squeezed), ("output_dtype_keyword", "omitted"))))
        operations.extend((
            Operation("torch_from_numpy_and_device", "current_rdm_creation.RDMCreator.create_rdms", (("device", "caller selected; not executed"),)),
            Operation("flatten_features", "current_rdm_creation.RDMCreator._create_rdm", (("start_dim", 1),)),
            Operation("model_pearson_distance", "current_rdm_creation.RDMCreator._create_rdm", (("distance", "pearson"), ("standardize_on_dim", None), ("chunk_size", None), ("native_distance_kernel", "not qualified here"))),
            Operation("emit_layer_rdm", "current_rdm_creation.RDMCreator.create_rdms", (("layer_name", name), ("stimulus_order_reference", support.stimuli.order_sha256), ("shape", (split.stimuli, split.stimuli)), ("save_format", "npz"))),
        ))
        layers.append(LayerContract(name, original_shape, squeezed, width, reduced, before, components,
                                    constructor, "all unlisted keywords omitted; no solver/seed/eps substitution", witness_sha, tuple(operations)))
    if set(witnesses) != consumed:
        raise ContractError("unused_or_nonautomatic_estimation_witness")
    return ModelContract(split, support.model_id, ordered_ids, support.expected_layer_order, execution_layers,
                         metadata_sha, reduction, spec_sha, run_admission, iterator_kwargs, tuple(layers))


def summarize_contract(contract, *, budget):
    """Small immutable parent linkage; caller may discard the per-layer body."""
    if type(contract) is ModelContract:
        return ContractSummary("model", canonical_digest(contract, budget), contract.split,
                               canonical_digest(contract.stimulus_order, budget), contract.model_id,
                               contract.source_axis_layer_order, contract.run_spec_sha256)
    if type(contract) is BrainContract:
        return ContractSummary("brain", canonical_digest(contract, budget), contract.split,
                               canonical_digest(contract.stimulus_order, budget), None, (), None)
    raise ContractError("compiled_contract_type")
