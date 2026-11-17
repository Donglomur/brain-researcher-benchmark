"""Protected paired uncertainty, never a change to the canonical trial weights.

The full entry requires the pinned NumPy version and all11 complete study panels.
No authentic grouping or numerical payload is accessed here on import.
"""
import math

import numpy as np

from .packets import require

DRAWS = 10000
SEED = 20261108
NUMPY_VERSION = "2.2.6"


def _bootstrap_kernel(z, codes, *, draws, seed):
    """Pure generic kernel for tiny invented checks; not a benchmark entry.

    Draw order is participant indices first, then shared identity indices, for
    every replicate. The same participant draw feeds conditional and crossed
    estimates; the same two draws feed every panel/comparison.
    """
    require(type(z) is np.ndarray and z.dtype.str == "<f8" and z.ndim == 3 and
            np.isfinite(z).all(), "Finite panels-by-people-by-trials Fisher z")
    k, people, trials = z.shape
    require(k >= 1 and people >= 1 and trials >= 1 and type(codes) is np.ndarray
            and codes.dtype.str == "<i8" and codes.shape == (people, trials),
            "Matching integer identity groups")
    groups = int(codes.max()) + 1
    require(groups >= 1 and set(codes.ravel().tolist()) == set(range(groups)),
            "Contiguous complete identity code support")
    require(type(draws) is int and 1 <= draws <= DRAWS and type(seed) is int and seed >= 0,
            "Bounded predeclared draw count and seed")
    means = z.mean(axis=2)
    counts = np.zeros((people, groups), dtype=np.int64)
    sums = np.zeros((k, people, groups), dtype=np.float64)
    for person in range(people):
        counts[person] = np.bincount(codes[person], minlength=groups)
        for panel in range(k):
            sums[panel, person] = np.bincount(codes[person], weights=z[panel, person], minlength=groups)
    conditional = np.empty((k, draws), dtype=np.float64)
    crossed = np.empty((k, draws), dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(seed))
    for draw in range(draws):
        selected_people = rng.integers(0, people, size=people, dtype=np.int64)
        selected_groups = rng.integers(0, groups, size=groups, dtype=np.int64)
        multiplicities = np.bincount(selected_groups, minlength=groups)
        denominator = counts @ multiplicities
        require(np.all(denominator[selected_people] > 0),
                "Undefined crossed draw: do not drop people or redraw silently")
        conditional[:, draw] = means[:, selected_people].mean(axis=1)
        person_values = (sums[:, selected_people, :] @ multiplicities) / denominator[selected_people]
        crossed[:, draw] = person_values.mean(axis=1)
    return conditional, crossed


def _point(z):
    """Use canonical compensated trial-then-person averaging for reported point."""
    return math.fsum(math.fsum(map(float, row)) / len(row) for row in z) / len(z)


def _interval(values):
    low, high = np.percentile(values, [2.5, 97.5], method="linear")
    return {"lower": float(low), "upper": float(high), "percentile_method": "linear"}


def paired_uncertainty(z_by_panel, group_codes, comparisons):
    """Full11-panel, 24-person, 120-trial, 70-identity protected estimator.

    z values must come from the unchanged canonical score_core on complete
    validated support. group_codes are owner-supplied protected identity labels;
    this module neither discovers them nor reads identity-key files. The owner
    must authorize grading and bind group ordering/provenance before calling.
    """
    require(np.__version__ == NUMPY_VERSION, "Pinned NumPy2.2.6 uncertainty environment required")
    require(type(z_by_panel) is dict and len(z_by_panel) == 11 and
            all(type(name) is str and name for name in z_by_panel), "All11 named study panels required")
    names = tuple(sorted(z_by_panel))
    for name in names:
        a = z_by_panel[name]
        require(type(a) is np.ndarray and a.dtype.str == "<f8" and a.shape == (24, 120)
                and np.isfinite(a).all(), "Exact complete24-by120 Fisher-z panel")
    require(type(group_codes) is np.ndarray and group_codes.dtype.str == "<i8" and
            group_codes.shape == (24, 120) and
            set(group_codes.ravel().tolist()) == set(range(70)), "Exactly70 shared identity codes")
    require(type(comparisons) in (list, tuple) and len(comparisons) > 0,
            "Predeclared paired comparisons required")
    require(all(type(pair) in (list, tuple) and len(pair) == 2 and
                all(type(name) is str and name in z_by_panel for name in pair)
                and pair[0] != pair[1] for pair in comparisons), "Valid ordered paired contrasts")
    require(len({tuple(pair) for pair in comparisons}) == len(comparisons), "No duplicate contrasts")
    z = np.stack([z_by_panel[name] for name in names])
    conditional, crossed = _bootstrap_kernel(z, group_codes, draws=DRAWS, seed=SEED)
    points = np.asarray([_point(panel) for panel in z], dtype=np.float64)
    panels = {name: {"primary_point": float(points[index]),
                     "participant_conditional": _interval(conditional[index]),
                     "crossed_identity_sensitivity": _interval(crossed[index])}
              for index, name in enumerate(names)}
    contrasts = []
    for left, right in comparisons:
        i, j = names.index(left), names.index(right)
        contrasts.append({"left": left, "right": right, "direction": "left_minus_right",
                          "point": float(points[i] - points[j]),
                          "participant_conditional": _interval(conditional[i] - conditional[j]),
                          "crossed_identity_sensitivity": _interval(crossed[i] - crossed[j])})
    return {"schema": "neural001_paired_uncertainty_v1", "draws": DRAWS,
            "seed": SEED, "rng": "NumPy2.2.6 PCG64", "percentile_method": "linear",
            "draw_order": "participant indices then shared identity indices per draw",
            "primary_weighting": "equal120trials/person then equal24people; unchanged",
            "panels": panels, "comparisons": contrasts,
            "interpretation": "Conditional participant intervals and crossed-identity sensitivity; not independent2880-case inference.",
            "multiplicity_adjusted": False, "scientific_significance_reward": None}
