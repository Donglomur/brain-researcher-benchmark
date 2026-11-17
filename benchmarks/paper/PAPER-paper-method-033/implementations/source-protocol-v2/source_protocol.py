"""MindBridge source calibration membership and operator-only reconstruction selection.

No models, source images, private targets, or training are loaded by this module.
The selection inputs must be produced by the source Clipper hidden-state path;
they are not the final CLIP features used for two-way identification in eval.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Mapping
import numpy as np

BUDGETS = (500, 1500, 4000)
CANDIDATE_COUNT = 8
SELECTION_SHAPE = (257, 768)
REQUIRED_EXTENSIONS = frozenset(('nsdgeneral.npy', 'jpg', 'coco73k.npy'))
SOURCE_EXTENSIONS = REQUIRED_EXTENSIONS | {'subj'}


class SourceProtocolError(ValueError):
    """Input cannot establish the requested source operation."""


def calibration_memberships(filenames: Iterable[str]) -> dict[int, tuple[str, ...]]:
    """Recover source prefix memberships from a complete extracted train inventory.

    src/data.py groups each basename at its FIRST period, sorts string sample keys,
    then slices [:length]. Shuffling changes order, not these memberships. This
    function checks all recognized keys have all three source payload extensions;
    it does not open them, authenticate the inventory, or assert original split IDs.
    Use the target-07 train inventory only, never a merged train/val/test inventory.
    """
    if isinstance(filenames, (str, bytes)):
        raise SourceProtocolError('filenames must be an inventory, not one string')
    samples: dict[str, set[str]] = {}
    seen = set()
    for filename in filenames:
        if not isinstance(filename, str) or not filename or '/' in filename or '\\' in filename:
            raise SourceProtocolError('inventory requires flat nonempty basenames')
        if filename in seen:
            raise SourceProtocolError('duplicate filename in inventory')
        seen.add(filename)
        if '.' not in filename:
            raise SourceProtocolError('source loader requires a period in every filename')
        key, extension = filename.split('.', 1)
        if extension not in SOURCE_EXTENSIONS:
            continue
        if not key:
            raise SourceProtocolError('empty sample identity')
        samples.setdefault(key, set()).add(extension)
    if any(not REQUIRED_EXTENSIONS <= extensions for extensions in samples.values()):
        raise SourceProtocolError('incomplete sample modalities in training inventory')
    ordered = sorted(samples)
    if len(ordered) < max(BUDGETS):
        raise SourceProtocolError('inventory cannot support all original calibration budgets')
    return {budget: tuple(ordered[:budget]) for budget in BUDGETS}


@dataclass(frozen=True)
class Selection:
    """First maximum cosine candidate; retain scores only in operator evidence."""
    index: int
    cosine_similarities: tuple[float, ...]


def _embedding(value, name: str, dtype=None) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != SELECTION_SHAPE or array.dtype not in (np.dtype('float32'), np.dtype('float64')):
        raise SourceProtocolError(name + ' must be float32/float64 with shape (257, 768)')
    if dtype is not None:
        array = array.astype(dtype, copy=False)
    if not np.isfinite(array).all():
        raise SourceProtocolError(name + ' contains nonfinite values')
    flat = array.reshape(-1)
    with np.errstate(over='ignore', invalid='ignore'):
        norm = np.linalg.norm(flat)
    if not np.isfinite(norm) or norm <= 0:
        raise SourceProtocolError(name + ' has undefined cosine norm')
    # Source first calls torch.nn.functional.normalize (default eps=1e-12).
    return flat / max(norm, 1e-12)


def select_best_of_eight(target_embedding, candidate_embeddings: Iterable[np.ndarray]) -> Selection:
    """Select one frozen reconstruction using source hidden-token cosine similarity.

    Stream the eight candidate embeddings in their frozen generation order. The
    target and candidates are Clipper('ViT-L/14', hidden_state=True, norm_embs=True)
    projected token outputs. Candidates are cast to target dtype as in utils.py.
    Equal maxima select the first index. Invalid embeddings fail closed instead of
    source nanargmax silently skipping invalid candidates. No model is invoked.

    Selection requires true target-derived features: execute only after all eight
    candidate images freeze, under operator ownership. This function is not an
    isolation service and does not authenticate when/where those images froze.
    """
    target = _embedding(target_embedding, 'target embedding')
    similarities = []
    for index, candidate_embedding in enumerate(candidate_embeddings):
        if index >= CANDIDATE_COUNT:
            raise SourceProtocolError('source reconstruction requires exactly eight candidates')
        candidate = _embedding(candidate_embedding, 'candidate embedding', target.dtype)
        # Source normalizes vectors, then batchwise_cosine_similarity divides by
        # their norms again. Keep that second normalization rather than using only
        # an inner product or Pearson correlation of these token vectors.
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            similarity = np.dot(target, candidate) / (np.linalg.norm(target) * np.linalg.norm(candidate))
        if not np.isfinite(similarity):
            raise SourceProtocolError('undefined candidate similarity')
        similarities.append(float(similarity))
    if len(similarities) != CANDIDATE_COUNT:
        raise SourceProtocolError('source reconstruction requires exactly eight candidates')
    return Selection(int(np.argmax(similarities)), tuple(similarities))


def apply_selection(selection: Selection, candidate_payloads: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Apply ONE selected image index to every operator-prepared metric payload.

    Each payload has candidate axis first, with length eight. Typical payloads are
    reconstruction images or source-extracted feature arrays. This routine does
    not compute metrics, verify feature provenance, or accept per-metric selection.
    """
    if (not isinstance(selection, Selection) or type(selection.index) is not int
            or not 0 <= selection.index < CANDIDATE_COUNT
            or len(selection.cosine_similarities) != CANDIDATE_COUNT
            or not np.isfinite(selection.cosine_similarities).all()
            or selection.index != int(np.argmax(selection.cosine_similarities))):
        raise SourceProtocolError('invalid common candidate selection')
    if not isinstance(candidate_payloads, Mapping) or not candidate_payloads:
        raise SourceProtocolError('candidate payload mapping is empty')
    selected = {}
    for name, value in candidate_payloads.items():
        payload = np.asarray(value)
        if not isinstance(name, str) or not name or payload.ndim < 1 or len(payload) != CANDIDATE_COUNT:
            raise SourceProtocolError('each named payload needs eight candidate rows')
        if payload.dtype.kind not in 'fiu' or not np.isfinite(payload).all():
            raise SourceProtocolError('payload must contain finite numerical values')
        selected[name] = payload[selection.index].copy()
    return selected
