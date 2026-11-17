"""BANC Python partition-input preparation; no eigensolver or scientific fit.

Reuses the reviewed wave8 selector and follows pinned upstream lines 292-306.
The numeric profile is portable NumPy 2.2.6 / SciPy 1.15.3, not a recovered
historical paper environment. Real graph bodies are not opened by this module.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
from types import ModuleType

import numpy as np
import scipy
from scipy.sparse import coo_matrix, csc_matrix


GRAPH_PREPARE_SHA256 = "a1b52f23b8a7ddcb72506090a7780be995c70f23b615a38d2145335610568616"
GRAPH_PREPARE_SOURCE = (Path(__file__).resolve().parents[2] /
                        "remaining-builds-wave8/paper_b-work/graph_prepare.py")
NUMPY_VERSION = "2.2.6"
SCIPY_VERSION = "1.15.3"


def _load_reviewed_selector():
    # Compile the exact bytes checked here, rather than reopening the path in
    # an import loader. Only this already-reviewed local source is imported.
    source = GRAPH_PREPARE_SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != GRAPH_PREPARE_SHA256:
        raise RuntimeError("Reviewed graph_prepare source pin changed")
    name = "banc_graph_prepare_" + GRAPH_PREPARE_SHA256
    if name in sys.modules:
        module = sys.modules[name]
        if getattr(module, "__reviewed_source_sha256__", None) != GRAPH_PREPARE_SHA256:
            raise RuntimeError("Conflicting selector module identity")
        return module
    module = ModuleType(name)
    module.__file__ = str(GRAPH_PREPARE_SOURCE)
    sys.modules[name] = module
    try:
        exec(compile(source, str(GRAPH_PREPARE_SOURCE), "exec"), module.__dict__)
        module.__reviewed_source_sha256__ = GRAPH_PREPARE_SHA256
    except BaseException:
        del sys.modules[name]
        raise
    return module


graph_prepare = _load_reviewed_selector()
MetadataRow = graph_prepare.MetadataRow
EdgeRow = graph_prepare.EdgeRow
DeclaredInputBinding = graph_prepare.DeclaredInputBinding
ContractError = graph_prepare.ContractError


@dataclass(frozen=True, slots=True)
class NumericalProfile:
    source_weight_cast_profile: str
    producer_branch: str = "python"
    numpy_version: str = NUMPY_VERSION
    scipy_version: str = SCIPY_VERSION
    dtype: str = "float32"
    historical_runtime_qualified: bool = False


@dataclass(frozen=True, slots=True)
class PartitionInput:
    """Complete ordered graph trace and numerical input for a future solver.

    Sparse matrices are caller-owned mutable objects, not sealed artifacts.
    Numerical construction alone does not authorize or qualify solver use.
    """
    graph: graph_prepare.PreparedGraph
    affinity: object
    column_sums: np.ndarray
    numerical_profile: NumericalProfile


def prepare_partition_input(metadata: tuple[MetadataRow, ...], edges: tuple[EdgeRow, ...],
                            binding: DeclaredInputBinding, *,
                            source_weight_cast_profile: str,
                            min_connection_strength: int = 1) -> PartitionInput:
    """Produce the source float32 symmetric affinity for all retained nodes.

    All supplied rows pass through the pinned selector; a preassembled or
    caller-forged PreparedGraph is not accepted as an alternative input route.
    IDs remain lexical strings and pre neurons are rows/post neurons columns.
    The returned column sums include the source zero-to-one replacement.
    A 0x0 result is valid empty support, not a successful spectral fit.

    Required source_weight_cast_profile is a caller declaration about the
    upstream aggregate vector: numpy_int64 means an int64 ndarray;
    object_python_int means an object ndarray containing only plain Python int
    scalars. These casts can differ above 2**53. Dtype alone is insufficient
    for object arrays; mixed/NumPy-scalar object profiles remain unsupported.
    This function cannot authenticate the declaration from normalized rows.
    """
    if np.__version__ != NUMPY_VERSION or scipy.__version__ != SCIPY_VERSION:
        raise ContractError("Unsupported numerical profile; version changes require separate review")
    if (type(source_weight_cast_profile) is not str
            or source_weight_cast_profile not in ("numpy_int64", "object_python_int")):
        raise ContractError("Declare a supported aggregate dtype AND scalar representation")
    graph = graph_prepare.prepare_graph(
        metadata, edges, binding, min_connection_strength=min_connection_strength)
    neuron_ids = graph.neuron_ids
    id_map = {identity: index for index, identity in enumerate(neuron_ids)}
    n = len(neuron_ids)
    row_idx = np.asarray([id_map[pair.pre] for pair in graph.pair_weights], dtype=np.int64)
    col_idx = np.asarray([id_map[pair.post] for pair in graph.pair_weights], dtype=np.int64)

    # Preserve the source's integer-sum -> float32 cast and sparse operation
    # order. In particular do not divide the integer weights in float64 first.
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            weight_dtype = np.int64 if source_weight_cast_profile == "numpy_int64" else object
            weights = np.asarray([pair.weight for pair in graph.pair_weights],
                                 dtype=weight_dtype).astype(np.float32)
            adj = coo_matrix((weights, (row_idx, col_idx)), shape=(n, n))
            adj_csc = csc_matrix(adj)
            col_sums = np.array(adj_csc.sum(axis=0)).flatten()
            col_sums[col_sums == 0] = 1
            adj_norm = adj_csc.multiply(1.0 / col_sums)
            adj_sym = 0.5 * (adj_norm + adj_norm.T)
            adj_sym = adj_sym.astype(np.float32)
    except FloatingPointError as error:
        raise ContractError("Nonfinite affinity arithmetic; no partition input produced") from error
    if (col_sums.dtype != np.dtype("float32") or adj_sym.dtype != np.dtype("float32")
            or not np.all(np.isfinite(col_sums)) or not np.all(np.isfinite(adj_sym.data))):
        raise ContractError("Unsupported or nonfinite affinity arithmetic")
    return PartitionInput(graph, adj_sym, col_sums, NumericalProfile(source_weight_cast_profile))
