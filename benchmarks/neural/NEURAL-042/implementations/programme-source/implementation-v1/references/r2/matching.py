"""Independent optimum checks; declared SciPy primitive selects the normative tie."""
import math
from .budget import require


def maximum_cardinality(valid, budget):
    n = len(valid)
    m = len(valid[0]) if n else 0
    require(all(len(row) == m for row in valid), "bipartite_shape", budget)
    budget.reserve("elements", n * m + n + 3 * m)
    budget.reserve("work_units", max(1, n * n * m))
    matched = [-1] * m

    def augment(i, seen):
        for j in range(m):
            if valid[i][j] and not seen[j]:
                seen[j] = True
                if matched[j] < 0 or augment(matched[j], seen):
                    matched[j] = i
                    return True
        return False

    with budget.live(32 * (n + 3 * m + 1)):
        count = 0
        for i in range(n):
            budget.tick()
            count += int(augment(i, [False] * m))
        return count


def minimum_assignment(matrix, budget):
    """Rectangular Hungarian primal/dual construction, independent of SciPy."""
    n0 = len(matrix)
    m0 = len(matrix[0]) if n0 else 0
    require(n0 > 0 and m0 > 0 and all(len(row) == m0 for row in matrix),
            "assignment_shape", budget)
    require(all(type(v) in (int, float) and math.isfinite(v)
                for row in matrix for v in row), "assignment_finite", budget)
    transposed = n0 > m0
    n, m = (m0, n0) if transposed else (n0, m0)
    with budget.numeric(n * m + 8 * (n + m + 2), 4 * n * n * m,
                        48 * n * m + 128 * (n + m + 2)):
        a = [[float(matrix[j][i]) for j in range(n0)] for i in range(m0)] if transposed else matrix
        u, v = [0.0] * (n + 1), [0.0] * (m + 1)
        p, way = [0] * (m + 1), [0] * (m + 1)
        for i in range(1, n + 1):
            budget.tick()
            p[0] = i
            j0 = 0
            minv, used = [math.inf] * (m + 1), [False] * (m + 1)
            while True:
                used[j0] = True
                i0 = p[j0]
                delta, j1 = math.inf, 0
                for j in range(1, m + 1):
                    if not used[j]:
                        cur = float(a[i0 - 1][j - 1]) - u[i0] - v[j]
                        if cur < minv[j]:
                            minv[j], way[j] = cur, j0
                        if minv[j] < delta:
                            delta, j1 = minv[j], j
                require(math.isfinite(delta), "assignment_augmenting_path", budget)
                for j in range(m + 1):
                    if used[j]:
                        u[p[j]] += delta
                        v[j] -= delta
                    else:
                        minv[j] -= delta
                j0 = j1
                if p[j0] == 0:
                    break
            while True:
                j1 = way[j0]
                p[j0] = p[j1]
                j0 = j1
                if j0 == 0:
                    break
        pairs = [(p[j] - 1, j - 1) for j in range(1, m + 1) if p[j] > 0]
        primal = math.fsum(float(a[i][j]) for i, j in pairs)
        dual = math.fsum(u[1:]) + math.fsum(v[1:])
        scale = max(1.0, max(abs(float(z)) for row in a for z in row), abs(primal))
        tolerance = 64 * math.ulp(scale) * (n + m + 1)
        minimum_reduced = min(float(a[i][j]) - u[i + 1] - v[j + 1]
                              for i in range(n) for j in range(m))
        maximum_assigned_slack = max(abs(float(a[i][j]) - u[i + 1] - v[j + 1])
                                     for i, j in pairs)
        require(len(pairs) == n and abs(primal - dual) <= tolerance
                and minimum_reduced >= -tolerance
                and maximum_assigned_slack <= tolerance
                and max(v[1:]) <= tolerance,
                "independent_primal_dual_certificate", budget)
        original = sorted((j, i) if transposed else (i, j) for i, j in pairs)
        budget.tick()
        return original, {"primal": primal, "dual": dual, "tolerance": tolerance,
                          "minimum_reduced_cost": minimum_reduced,
                          "maximum_assigned_slack": maximum_assigned_slack,
                          "transposed": transposed,
                          "algorithm": "independent_rectangular_Hungarian"}


def verified_tie_assignment(costs, valid, budget):
    """Independent cardinality/optimum; SciPy tie recipe is a shared primitive."""
    np = __import__("numpy")
    import scipy
    require(scipy.__version__ == "1.15.3", "qualified_SciPy_1_15_3_required", budget)
    from scipy.optimize import linear_sum_assignment
    n, m = costs.shape
    with budget.numeric(5 * n * m + 4 * (n + m), 5 * min(n, m) ** 2 * max(n, m),
                        112 * n * m + 128 * (n + m + 1)):
        matrix = [[float(costs[i, j]) for j in range(m)] for i in range(n)]
        allowed = [[bool(valid[i, j]) for j in range(m)] for i in range(n)]
        maximum = maximum_cardinality(allowed, budget)
        independent, certificate = minimum_assignment(matrix, budget)
        independent_valid = sum(allowed[i][j] for i, j in independent)
        require(independent_valid == maximum, "independent_maximum_cardinality", budget)
        budget.tick()
        rows, cols = linear_sum_assignment(costs)
        budget.tick()
        chosen = [(int(i), int(j)) for i, j in zip(rows, cols)]
        require(len(chosen) == min(n, m)
                and len({i for i, _ in chosen}) == len(chosen)
                and len({j for _, j in chosen}) == len(chosen),
                "normative_assignment_integrity", budget)
        chosen_cost = math.fsum(matrix[i][j] for i, j in chosen)
        selected = [(i, j) for i, j in chosen if allowed[i][j]]
        require(len(selected) == maximum
                and abs(chosen_cost - certificate["primal"]) <= certificate["tolerance"],
                "normative_tie_optimum_verification", budget)
        certificate.update(maximum_cardinality=maximum,
                           chosen_penalized_cost=chosen_cost,
                           selected_cost=math.fsum(matrix[i][j] for i, j in selected),
                           tie_recipe="sorted IDs / SciPy 1.15.3 linear_sum_assignment",
                           independent_tie_algorithm_claimed=False)
        return selected, certificate


def select_pairs(channel, nuisance, design, contrast, part, budget):
    import numpy as np
    n = len(channel["ids"])
    if contrast == "load3_minus_load1_correct":
        side_a = [i for i in range(n) if channel["loads"][i] == 3 and channel["correct"][i] == 1]
        side_b = [i for i in range(n) if channel["loads"][i] == 1 and channel["correct"][i] == 1]
    else:
        load = 1 if part == 0 else 3
        side_a = [i for i in range(n) if channel["loads"][i] == load and channel["correct"][i] == 1]
        side_b = [i for i in range(n) if channel["loads"][i] == load and channel["correct"][i] == 0]
    aa, bb, evidence = [], [], []
    budget.reserve("elements", 32 * (n + 1))
    for block in range(4):
        for probe in range(2):
            a = sorted((i for i in side_a if channel["order"][i] // 35 == block
                        and channel["probe"][i] == probe), key=lambda i: channel["ids"][i])
            b = sorted((i for i in side_b if channel["order"][i] // 35 == block
                        and channel["probe"][i] == probe), key=lambda i: channel["ids"][i])
            size_a, size_b = len(a), len(b)
            row = {"stratum": [block, probe], "n_a": size_a, "n_b": size_b,
                   "population_sd": None, "selected_pairs": [], "selected_cost": None,
                   "optimum": None, "recipe": design}
            if a and b:
                if design == "count_only":
                    picked = list(zip(range(min(size_a, size_b)), range(min(size_a, size_b))))
                else:
                    require(design == "nuisance_matched" and nuisance is not None,
                            "matching_design", budget)
                    with budget.numeric(64 * size_a * size_b + 64 * (size_a + size_b),
                                        40 * size_a * size_b,
                                        512 * size_a * size_b + 512 * (size_a + size_b)):
                        combined = nuisance[a + b]
                        sd = np.std(combined, axis=0, ddof=0)
                        differences = nuisance[a, None, :] - nuisance[None, b, :]
                        denominator = np.where(sd == 0, 1.0, sd)
                        standardized = differences / denominator[None, None, :]
                        valid = np.all(np.abs(standardized) <= 0.5, axis=2)
                        if np.any(sd == 0):
                            valid &= np.all(differences[:, :, sd == 0] == 0, axis=2)
                        distance = np.sum(standardized ** 2, axis=2)
                        penalty = 4.0 * (min(size_a, size_b) + 1)
                        costs = np.where(valid, distance, penalty)
                        require(np.isfinite(costs).all(), "matching_finite", budget)
                        picked, certificate = verified_tie_assignment(costs, valid, budget)
                        row["population_sd"] = [float(x) for x in sd]
                        row["selected_cost"] = float(certificate["selected_cost"])
                        row["optimum"] = certificate
                for i, j in picked:
                    aa.append(a[i])
                    bb.append(b[j])
                    row["selected_pairs"].append([channel["ids"][a[i]], channel["ids"][b[j]]])
            row["selected_count"] = len(row["selected_pairs"])
            evidence.append(row)
            budget.tick()
    return aa, bb, evidence

