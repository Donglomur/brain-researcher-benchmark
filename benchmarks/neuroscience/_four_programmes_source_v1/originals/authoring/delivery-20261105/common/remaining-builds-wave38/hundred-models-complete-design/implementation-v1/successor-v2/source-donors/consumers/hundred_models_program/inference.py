"""Pure complete-scope permutation statistics; no RSA, target I/O or native work.

Caller scores/null summaries and shared schedule are declarations. This source
consumer never authenticates original arrays or recovers the historical RNG.
"""
from dataclasses import dataclass
from statistics import median
import hashlib
import json
import math
import re

TASK_ID = 'PAPER-paper-method-replacement-016'
SOURCE_COMMIT = '5e802ae5e368a1a30940e6b175e47704a3061419'
PROTOCOL_SHA256 = '59a43129bda8f20c4de74f1022609d09c3d7b8f1db275cc6b7df05057c7e9d1c'
SUBJECTS = ('sub-01', 'sub-02', 'sub-03', 'sub-04', 'sub-05', 'sub-06', 'sub-07', 'sub-08', 'sub-09', 'sub-10')
STIMULI = ('vid1001', 'vid1002', 'vid1003', 'vid1004', 'vid1005', 'vid1006', 'vid1007', 'vid1008', 'vid1009', 'vid1010', 'vid1011', 'vid1012', 'vid1013', 'vid1014', 'vid1015', 'vid1016', 'vid1017', 'vid1018', 'vid1019', 'vid1020', 'vid1021', 'vid1022', 'vid1023', 'vid1024', 'vid1025', 'vid1026', 'vid1027', 'vid1028', 'vid1029', 'vid1030', 'vid1031', 'vid1032', 'vid1033', 'vid1034', 'vid1035', 'vid1036', 'vid1037', 'vid1038', 'vid1039', 'vid1040', 'vid1041', 'vid1042', 'vid1043', 'vid1044', 'vid1045', 'vid1046', 'vid1047', 'vid1048', 'vid1049', 'vid1050', 'vid1051', 'vid1052', 'vid1053', 'vid1054', 'vid1055', 'vid1056', 'vid1057', 'vid1058', 'vid1059', 'vid1060', 'vid1061', 'vid1062', 'vid1063', 'vid1064', 'vid1065', 'vid1066', 'vid1067', 'vid1068', 'vid1069', 'vid1070', 'vid1071', 'vid1072', 'vid1073', 'vid1074', 'vid1075', 'vid1076', 'vid1077', 'vid1078', 'vid1079', 'vid1080', 'vid1081', 'vid1082', 'vid1083', 'vid1084', 'vid1085', 'vid1086', 'vid1087', 'vid1088', 'vid1089', 'vid1090', 'vid1091', 'vid1092', 'vid1093', 'vid1094', 'vid1095', 'vid1096', 'vid1097', 'vid1098', 'vid1099', 'vid1100', 'vid1101', 'vid1102')
ROIS = ('V1', 'V2', 'V3v', 'V3d', 'hV4', 'OFA', 'LOC', 'FFA', 'PPA', 'V3ab', 'IPS0', 'IPS1', 'RSC', 'EBA', 'TOS', 'MT', 'STS')
MODELS = ('AlexNet', 'Densenet161', 'Densenet201', 'efficientnet_b3', 'efficientnet_b6', 'regnet_x_16gf', 'regnet_y_8gf', 'ResNet34', 'ResNet50', 'ResNet101', 'ResNet152', 'resnext50_32x4d', 'resnext101_32x8d', 'VGG11', 'VGG11_bn', 'VGG19', 'VGG19_bn', 'wide_resnet50_2', 'wide_resnet101_2', 'inception_v3', 'inception_v4', 'repvgg_a2', 'repvgg_b2', 'seresnet50', 'seresnext50_32x4d', 'xception41', 'xception71', 'cait_s24_224', 'cait_xxs24_224', 'convit_small', 'convit_base', 'deit_small_patch16_224', 'deit_base_patch16_224', 'swin_tiny_patch4_window7_224', 'swin_small_patch4_window7_224', 'swin_base_patch4_window7_224', 'twins_pcpvt_base', 'vit_small_patch16_224', 'vit_base_patch16_224', 'mvitv2_small_in1k', 'mvitv2_base_in1k', 'c2d_r50_nopool_mma', 'c2d_r101_nopool_mma', 'c2d_r50_pool8_mma', 'c2d_r50_pool16_mma', 'TSN_r50_8', 'TSN_r101_8', 'TSN_d161_3', 'TSN_mobones4_8', 'TSN_swin_8', 'timesformer_spaceOnly', 'ircsn_r152', 'ircsn_bnfrozen_r152_ig65m', 'ircsn_bnfrozen_r50_ig65m', 'ircsn_r152_ig65m', 'ipcsn_bnfrozen_r152_ig65m', 'ipcsn_r152', 'i3d_r50_mma', 'i3d_r50_dotprod', 'i3d_r50_embgauss', 'i3d_r50_gauss', 'i3d_r50_heavy', 'r2plus1d_r50_mma', 'slowfast_r50_mma', 'slowfast_r101_mma', 'slow_r50_mma', 'slow_r101', 'slow_r50_in1k', 'slow_r50_in1k_embgauss', 'tanet_r50', 'tpn_r50', 'tsm_r50', 'tsm_r50_dotprod', 'tsm_r50_gauss', 'tsm_r50_embgauss', 'tsm_r50_mobones4_16', 'x3d_s', 'x3d_m', 'MViT_v2_S', 'MViT_v2_B', 'video_swin_tiny', 'video_swin_small', 'video_swin_base', 'timesformer_divST', 'timesformer_jointST', 'uniformer_S', 'uniformer_B', 'uniformer_v2_B_16_CLIP_k400', 'uniformer_v2_B_16_CLIP_k710_k400', 'videomae_B', 'videomae_v2_S', 'videomae_v2_B', 'slow_r50_in1k_k710', 'video_swin_small_k710', 'uniformer_v2_B_16_CLIP_k710', 'MViT_v2_S_ssv2', 'MViT_v2_B_ssv2', 'tsm_r50_ssv2', 'TSN_r50_8_ssv2')
MODEL_TYPES = ('image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-in1k', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'image-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k400', 'video-k710', 'video-k710', 'video-k710', 'video-ssv2', 'video-ssv2', 'video-ssv2', 'image-ssv2')
ARCHITECTURES = ('CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'Transformers', 'Transformers', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'CNNs', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', 'Transformers', None, None, None, None, None, None, None)
TRAINING_GROUPS = (('Kinetics-400 (1)', ('slow_r50_in1k', 'video_swin_small', 'uniformer_v2_B_16_CLIP_k400')), ('Kinetics-710', ('slow_r50_in1k_k710', 'video_swin_small_k710', 'uniformer_v2_B_16_CLIP_k710')), ('Kinetics-400 (2)', ('MViT_v2_S', 'MViT_v2_B', 'TSN_r50_8', 'tsm_r50')), ('Sth-Sth-v2', ('MViT_v2_S_ssv2', 'MViT_v2_B_ssv2', 'tsm_r50_ssv2', 'TSN_r50_8_ssv2')))

N_PERMUTATIONS = 1000
SOURCE_COMPARISONS = ("source_default92_ModelType", "paper_Fig4_video41_ArchType",
                      "paper_Fig5_K4001_vs_K710", "paper_Fig5_K4002_vs_SSv2")
LITERAL_ARCH92_COMPARISON = "literal_generic_default92_ArchType_diagnostic"
LITERAL_FOUR_GROUP_COMPARISON = "literal_generic_training14_four_group_diagnostic"
PROSPECTIVE_COMPARISON = "prospective_full99_ModelType"
NULL_OPERATORS = ("source_rows_only", "prospective_congruent_stimulus_labels")
LAYER_RULES = ("source_observed_best_layer_conditional", "prospective_max_each_permutation")


class InferenceDomainError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InferenceDomainError(message)


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _rho(value):
    require(type(value) in (int, float) and math.isfinite(value) and -1 <= value <= 1,
            "complete_finite_signed_rho_domain_no_missing_or_clipping")


@dataclass(frozen=True)
class ScheduleBinding:
    null_operator: str
    permutation_digests: tuple[str, ...]
    schedule_sha256: str
    origin: str = "caller_supplied_shared_schedule_not_historical_recovery"


def bind_schedule(permutations, *, null_operator):
    """Validate exactly 1000 complete 102-video permutations, retaining hashes.

    This does not generate a schedule, transform an RDM, or prove null scores
    arose from the supplied permutations. Historical unseeded/cached provenance
    remains unknown. One permutation at a time is read; none is retained.
    """
    require(null_operator in NULL_OPERATORS, "explicit_source_or_prospective_null_operator")
    iterator = iter(permutations); digests = []
    for _ in range(N_PERMUTATIONS):
        try: p = next(iterator)
        except StopIteration: raise InferenceDomainError("all1000_permutations_required") from None
        require(type(p) is tuple and len(p) == 102 and all(type(i) is int for i in p)
                and set(p) == set(range(102)), "complete_102_stimulus_permutation")
        digests.append(canonical_digest(p))
    sentinel = object()
    require(next(iterator, sentinel) is sentinel, "no_extra_permutations")
    return ScheduleBinding(null_operator, tuple(digests), canonical_digest((null_operator, tuple(digests))))


def validate_schedule(schedule):
    require(type(schedule) is ScheduleBinding and schedule.null_operator in NULL_OPERATORS
            and type(schedule.permutation_digests) is tuple and len(schedule.permutation_digests) == 1000
            and all(_sha(d) for d in schedule.permutation_digests)
            and schedule.schedule_sha256 == canonical_digest((schedule.null_operator, schedule.permutation_digests))
            and schedule.origin == "caller_supplied_shared_schedule_not_historical_recovery",
            "complete_shared_schedule_binding_no_historical_claim")


@dataclass(frozen=True)
class Scope:
    # (model id, complete ordered retained layer names), no runtime inference.
    model_layers: tuple[tuple[str, tuple[str, ...]], ...]
    layer_catalog_sha256: str
    schedule: ScheduleBinding
    layer_null_rule: str
    comparisons: tuple[str, ...]
    subjects: tuple[str, ...]
    rois: tuple[str, ...]
    stimuli: tuple[str, ...]
    protocol_sha256: str


@dataclass(frozen=True)
class WorkLimits:
    max_total_layers: int
    max_null_summary_cells: int
    max_result_scalar_cells: int


@dataclass(frozen=True)
class ObservedLayer:
    layer: str
    subject_values: tuple[float, ...]


@dataclass(frozen=True)
class ObservedModel:
    model: str
    layers: tuple[ObservedLayer, ...]


@dataclass(frozen=True)
class ObservedROI:
    roi: str
    models: tuple[ObservedModel, ...]


@dataclass(frozen=True)
class NullLayerMean:
    layer: str
    mean: float
    subject_count: int


@dataclass(frozen=True)
class NullModelMeans:
    model: str
    layers: tuple[NullLayerMean, ...]


@dataclass(frozen=True)
class NullBatch:
    roi: str
    permutation_index: int
    permutation_sha256: str
    schedule_sha256: str
    null_operator: str
    subjects: tuple[str, ...]
    models: tuple[NullModelMeans, ...]
    summary_kind: str = "mean_of_all10_subject_signed_spearman"


@dataclass(frozen=True)
class ModelInference:
    model: str
    layer_names: tuple[str, ...]
    observed_layer_means: tuple[float, ...]
    layer_tail_counts: tuple[int, ...]
    selected_layer: str
    selected_observed_mean: float
    selected_null_tail_count: int
    selected_pvalue: float
    # Source selection is conditional on the observed layer, not familywise.
    layer_null_rule: str


@dataclass(frozen=True)
class GroupInference:
    label: str
    members: tuple[str, ...]
    observed_median: float
    tail_count: int
    pvalue: float


@dataclass(frozen=True)
class PairInference:
    group_1: str
    group_2: str
    observed_difference: float
    tail_count: int
    raw_pvalue: float
    factor: int
    source_scaled_pvalue: float


@dataclass(frozen=True)
class ComparisonInference:
    comparison: str
    excluded_models: tuple[str, ...]
    groups: tuple[GroupInference, ...]
    ordered_pairs: tuple[PairInference, ...]
    pairwise_factor: int
    roi_correction_factor: int = 1


@dataclass(frozen=True)
class ROIInference:
    roi: str
    models: tuple[ModelInference, ...]
    comparisons: tuple[ComparisonInference, ...]


@dataclass(frozen=True)
class InferenceResult:
    task_id: str
    rois: tuple[ROIInference, ...]
    layer_catalog_sha256: str
    schedule_sha256: str
    null_operator: str
    layer_null_rule: str
    permutations: int
    processed_null_batches: int
    processed_layer_summaries: int
    tail_convention: str = "abs(null)>=abs(observed);count/N;no_plus_one"
    shared_schedule_origin_verified: bool = False
    historical_schedule_recovered: bool = False
    native_arithmetic_parity_qualified: bool = False
    authentic_inputs_qualified: bool = False
    scientific_qualification: bool = False


def comparison_groups(name):
    """Exact source memberships; full99 completion is separate from contrasts."""
    if name == LITERAL_FOUR_GROUP_COMPARISON:
        return TRAINING_GROUPS
    if name == "paper_Fig5_K4001_vs_K710":
        return TRAINING_GROUPS[:2]
    if name == "paper_Fig5_K4002_vs_SSv2":
        return TRAINING_GROUPS[2:]
    if name == "paper_Fig4_video41_ArchType":
        indices = tuple(i for i in range(99) if MODEL_TYPES[i] == "video-k400")
        labels = tuple(dict.fromkeys(ARCHITECTURES[i] for i in indices))
        require(all(type(label) is str and label for label in labels), "no_invented_missing_annotation_group")
        return tuple((label, tuple(MODELS[i] for i in indices if ARCHITECTURES[i] == label)) for label in labels)
    if name in ("source_default92_ModelType", PROSPECTIVE_COMPARISON):
        count = 99 if name == PROSPECTIVE_COMPARISON else 92
        labels = MODEL_TYPES[:count]
    else:
        require(name == LITERAL_ARCH92_COMPARISON, "explicit_comparison_endpoint")
        count = 92; labels = ARCHITECTURES[:count]
    require(all(type(label) is str and label for label in labels), "no_invented_missing_annotation_group")
    order = tuple(dict.fromkeys(labels))
    return tuple((label, tuple(MODELS[i] for i in range(count) if labels[i] == label)) for label in order)


def source_pair_factor(labels):
    require(type(labels) is tuple and len(labels) == len(set(labels))
            and all(type(label) is str for label in labels), "complete_unique_group_labels")
    return 1 if "Kinetics-710" in labels else math.comb(len(labels), 2)


def legacy_tail_count(null_values, observed):
    """Small scalar oracle; run_inference uses the same comparison streaming."""
    _rho(observed)
    require(type(null_values) is tuple and len(null_values) > 0, "nonempty_declared_null_values")
    for value in null_values: _rho(value)
    count = sum(abs(value) >= abs(observed) for value in null_values)
    return count, count / len(null_values)


def validate_scope(scope, limits):
    require(type(scope) is Scope and type(limits) is WorkLimits, "explicit_full_scope_and_work_limits")
    require(scope.protocol_sha256 == PROTOCOL_SHA256 and scope.subjects == SUBJECTS
            and type(scope.subjects) is tuple and scope.rois == ROIS and type(scope.rois) is tuple
            and scope.stimuli == STIMULI and type(scope.stimuli) is tuple,
            "exact99_model_protocol10_subject17_ROI102_stimulus_scope")
    require(type(scope.model_layers) is tuple and len(scope.model_layers) == 99, "full99_model_layer_catalog")
    require(all(type(x) is tuple and len(x) == 2 for x in scope.model_layers)
            and tuple(x[0] for x in scope.model_layers) == MODELS, "exact_ordered99_model_identities")
    for _, layers in scope.model_layers:
        require(type(layers) is tuple and bool(layers) and len(layers) == len(set(layers))
                and all(type(layer) is str and bool(layer) for layer in layers), "complete_ordered_unique_retained_layers")
    require(scope.layer_catalog_sha256 == canonical_digest(scope.model_layers), "bound_declared_layer_catalog")
    require(scope.layer_null_rule in LAYER_RULES, "explicit_conditional_or_prospective_max_rule")
    extras = (LITERAL_ARCH92_COMPARISON, LITERAL_FOUR_GROUP_COMPARISON, PROSPECTIVE_COMPARISON)
    require(type(scope.comparisons) is tuple and scope.comparisons[:4] == SOURCE_COMPARISONS
            and scope.comparisons[4:] == tuple(name for name in extras if name in scope.comparisons[4:]),
            "all_four_paper_endpoints_optional_explicit_generic_source_or_prospective_diagnostics")
    validate_schedule(scope.schedule)
    require(all(type(v) is int and v >= 0 for v in (limits.max_total_layers, limits.max_null_summary_cells,
                                                  limits.max_result_scalar_cells)), "nonnegative_integer_complete_work_bounds")
    total_layers = sum(len(layers) for _, layers in scope.model_layers)
    group_cells = sum(4 * len(comparison_groups(name)) + 6 * len(comparison_groups(name)) * (len(comparison_groups(name))-1)
                      for name in scope.comparisons)
    # Counts/means/pvalues scalar upper bound. String metadata is caller-bound.
    result_cells = 17 * (2 * total_layers + 3 * 99 + group_cells)
    require(total_layers <= limits.max_total_layers and 17 * 1000 * total_layers <= limits.max_null_summary_cells
            and result_cells <= limits.max_result_scalar_cells, "whole_scope_capacity_required_no_truncation")
    return total_layers


def _observed(row, roi, scope):
    require(type(row) is ObservedROI and row.roi == roi and type(row.models) is tuple
            and len(row.models) == 99, "complete_observed_ROI_all99_models")
    means = []; chosen = []
    for model, (identity, layers) in zip(row.models, scope.model_layers):
        require(type(model) is ObservedModel and model.model == identity and type(model.layers) is tuple
                and len(model.layers) == len(layers), "complete_observed_model_all_layers")
        values = []
        for layer, name in zip(model.layers, layers):
            require(type(layer) is ObservedLayer and layer.layer == name
                    and type(layer.subject_values) is tuple and len(layer.subject_values) == 10,
                    "complete_observed_layer_all10_subjects")
            for value in layer.subject_values: _rho(value)
            values.append(math.fsum(layer.subject_values) / 10)
        means.append(tuple(values))
        # First source-order maximum, including ties and negative correlations.
        chosen.append(max(range(len(values)), key=values.__getitem__))
    return tuple(means), tuple(chosen)


def _next(iterator, message):
    try: return next(iterator)
    except StopIteration: raise InferenceDomainError(message) from None


def run_inference(scope, observed_rois, null_batches, *, limits):
    """Stream complete per-layer null means into conditional/source group tests.

    observed_rois: one complete99-model row for each17 ROI in protocol order.
    null_batches: ROI-major,1000 frames/ROI; each frame contains every model and
    retained layer, tagged with all10 subjects and the same indexed schedule.
    Means are validated summaries, not re-derived RDMs. Producer honesty and
    native arithmetic parity remain held. No full null tensor is retained.
    """
    total_layers = validate_scope(scope, limits)
    observed_iterator = iter(observed_rois); null_iterator = iter(null_batches)
    indices = {model: i for i, model in enumerate(MODELS)}
    comparisons = tuple((name, comparison_groups(name)) for name in scope.comparisons)
    result = []; processed = 0
    for roi in ROIS:
        row = _next(observed_iterator, "all17_observed_ROIs_required")
        means, chosen = _observed(row, roi, scope)
        observed_best = tuple(values[k] for values, k in zip(means, chosen))
        layer_counts = [[0] * len(layers) for _, layers in scope.model_layers]
        selected_counts = [0] * 99
        groups_work = []
        for name, groups in comparisons:
            member_indices = tuple(tuple(indices[m] for m in members) for _, members in groups)
            obs = tuple(median(observed_best[i] for i in members) for members in member_indices)
            pair_indices = tuple((i, j) for i in range(len(groups)) for j in range(len(groups)) if i != j)
            groups_work.append((name, groups, member_indices, obs, pair_indices, [0]*len(groups), [0]*len(pair_indices)))
        for permutation_index in range(1000):
            frame = _next(null_iterator, "all17x1000_null_batches_required")
            schedule = scope.schedule
            require(type(frame) is NullBatch and frame.roi == roi
                    and type(frame.permutation_index) is int and frame.permutation_index == permutation_index
                    and frame.permutation_sha256 == schedule.permutation_digests[permutation_index]
                    and frame.schedule_sha256 == schedule.schedule_sha256 and frame.null_operator == schedule.null_operator
                    and type(frame.subjects) is tuple and frame.subjects == SUBJECTS
                    and frame.summary_kind == "mean_of_all10_subject_signed_spearman"
                    and type(frame.models) is tuple and len(frame.models) == 99,
                    "complete_indexed_shared_permutation_summary_frame")
            selected = []
            for i, (model, (identity, layers)) in enumerate(zip(frame.models, scope.model_layers)):
                require(type(model) is NullModelMeans and model.model == identity and type(model.layers) is tuple
                        and len(model.layers) == len(layers), "complete_null_model_all_layers")
                values = []
                for k, (layer, name) in enumerate(zip(model.layers, layers)):
                    require(type(layer) is NullLayerMean and layer.layer == name
                            and type(layer.subject_count) is int and layer.subject_count == 10, "all10_subject_null_summary")
                    _rho(layer.mean); values.append(layer.mean)
                    layer_counts[i][k] += abs(layer.mean) >= abs(means[i][k])
                value = values[chosen[i]] if scope.layer_null_rule == LAYER_RULES[0] else max(values)
                selected.append(value)
                selected_counts[i] += abs(value) >= abs(observed_best[i])
            for _, _, members, obs, pairs, group_counts, pair_counts in groups_work:
                medians = tuple(median(selected[i] for i in member) for member in members)
                for i, (value, observed) in enumerate(zip(medians, obs)):
                    group_counts[i] += abs(value) >= abs(observed)
                for k, (i, j) in enumerate(pairs):
                    pair_counts[k] += abs(medians[i] - medians[j]) >= abs(obs[i] - obs[j])
            processed += 1
        models = tuple(ModelInference(identity, layers, means[i], tuple(layer_counts[i]), layers[chosen[i]],
                                      observed_best[i], selected_counts[i], selected_counts[i]/1000, scope.layer_null_rule)
                       for i, (identity, layers) in enumerate(scope.model_layers))
        group_results = []
        for name, groups, _, obs, pairs, group_counts, pair_counts in groups_work:
            factor = source_pair_factor(tuple(label for label, _ in groups))
            included = {m for _, members in groups for m in members}
            group_results.append(ComparisonInference(name, tuple(m for m in MODELS if m not in included),
                tuple(GroupInference(label, members, obs[i], group_counts[i], group_counts[i]/1000)
                      for i, (label, members) in enumerate(groups)),
                tuple(PairInference(groups[i][0], groups[j][0], obs[i]-obs[j], pair_counts[k], pair_counts[k]/1000,
                                    factor, pair_counts[k]/1000*factor) for k, (i, j) in enumerate(pairs)), factor))
        result.append(ROIInference(roi, models, tuple(group_results)))
    sentinel = object()
    require(next(observed_iterator, sentinel) is sentinel, "no_extra_observed_ROIs")
    require(next(null_iterator, sentinel) is sentinel, "no_extra_null_frames")
    return InferenceResult(TASK_ID, tuple(result), scope.layer_catalog_sha256, scope.schedule.schedule_sha256,
                           scope.schedule.null_operator, scope.layer_null_rule, 1000, processed,
                           processed * total_layers)

