"""Reports replayed only from accepted spectral coordinates/certified GPA.

No expected apex, correlation, gain or outcome is stored. Canonical source
support controls availability; accepted coordinate values control endpoints.
"""
from __future__ import annotations

import itertools
import math
import numpy as np

import gradient_math as m


def pearson(x, y):
    x, y = m.centered(x), m.centered(y)
    nx, ny = m.norm(x), m.norm(y)
    if nx == 0 or ny == 0: return None
    result = math.fsum(float(a) * float(b) for a, b in zip(x / nx, y / ny))
    m.require(math.isfinite(result) and abs(result) <= 1 + 1e-12, "invalid Pearson arithmetic")
    return min(1., max(-1., result))


def embedding_status(basis, gradient):
    if basis is None:
        return "inactive_parcel", "embedding_undefined", "embedding_undefined"
    if gradient is None:
        return "multiscale_singular", "embedding_undefined", "embedding_undefined"
    principal = ("principal_degenerate" if not basis["principal_identifiable"] else
                 "constant_coordinate" if m.norm(m.centered(gradient[:, 0])) == 0 else "ok")
    span = "ok" if basis["retained_boundary_identifiable"] else "retained_boundary_degenerate"
    return "ok", principal, span


def variance_columns(values):
    values = m.real(values, "variance columns", 2)
    m.require(len(values) > 0, "nonempty variance support")
    variance = np.var(values, axis=0, ddof=0, dtype=np.float64)
    variance[np.all(values == values[0], axis=0)] = 0.
    return variance


def network_summary(gradient, basis, networks, network_order, *, align_mean=False,
                    reference_principal="ok", n_components=10):
    p, k = len(networks), len(basis["eigenvalues"]) if basis is not None else n_components
    display = np.full((p, k), np.nan); signs = np.zeros(k, dtype=np.int64)
    valid = np.zeros(k, dtype=bool)
    summary = dict(status="source_incomplete", apex_network=None, bottom_network=None,
                   between_within=None, between_within_status="source_incomplete",
                   principal_gap=None, retained_boundary_gap=None)
    if basis is not None:
        summary.update(principal_gap=basis["principal_gap"], retained_boundary_gap=basis["retained_boundary_gap"])
    if gradient is None:
        status = "alignment_undefined" if align_mean else "source_incomplete" if basis is None else "multiscale_singular"
        summary.update(status=status, between_within_status=status)
        return summary, display, signs, valid, {name: [None] * k for name in network_order}
    gradient = m.real(gradient, "report coordinates", 2)
    m.require(gradient.shape == (p, k), "report coordinate shape")
    masks = [np.asarray(networks) == name for name in network_order]
    m.require(all(mask.any() for mask in masks), "all declared networks required")
    means = np.stack([np.mean(gradient[mask], axis=0, dtype=np.float64) for mask in masks])
    default, visual = network_order.index("Default"), network_order.index("Vis")
    signs[:] = 1
    for column in (range(k) if align_mean else (0,)):
        if means[default, column] < means[visual, column]: signs[column] = -1
    oriented = gradient * signs
    means *= signs
    principal = embedding_status(basis, gradient)[1]
    if align_mean:
        principal = reference_principal if reference_principal != "ok" else (
            "constant_coordinate" if m.norm(m.centered(gradient[:, 0])) == 0 else "ok")
    summary["status"] = principal
    display[:] = oriented; valid[:] = True
    if principal != "ok":
        display[:, 0] = np.nan; signs[0] = 0; valid[0] = False
    else:
        summary.update(apex_network=network_order[int(np.argmax(means[:, 0]))],
                       bottom_network=network_order[int(np.argmin(means[:, 0]))])
    if basis["spectral_eigenvalues"][1] - basis["spectral_eigenvalues"][2] <= m.GAP_ATOL:
        summary["between_within_status"] = "plane_degenerate"
    else:
        between = float(np.sum(variance_columns(means[:, :2])))
        within = float(np.mean([np.sum(variance_columns(oriented[mask, :2])) for mask in masks]))
        m.require(math.isfinite(between) and math.isfinite(within) and between >= 0 and within >= 0, "invalid B/W arithmetic")
        summary["between_within_status"] = "ok" if within > 0 else "zero_within"
        summary["between_within"] = between / within if within > 0 else None
    values = {name: [float(means[i, c]) if valid[c] else None for c in range(k)] for i, name in enumerate(network_order)}
    return summary, display, signs, valid, values


def derive(reference, gradients, gpa):
    """Compose complete public quantities after spectral/GPA validation."""
    arrays, method = reference["arrays"], reference["method"]
    people = arrays["participant_ids"].tolist(); n = len(people)
    configs = method["configurations"]; names = [row["id"] for row in configs]
    networks = reference["networks"]; network_order = method["source"]["networks"]
    bases = reference["source_bases"]
    m.require(len(bases) == len(gradients) == n + len(configs), "complete embedding family")
    statuses = [embedding_status(basis, gradient) for basis, gradient in zip(bases, gradients)]
    k = next((len(b["eigenvalues"]) for b in bases if b is not None), int(method["diffusion"]["n_components"]))
    p = len(networks)
    aligned = np.full((n, p, k), np.nan) if gpa is None else gpa["aligned"]
    pairs = list(itertools.combinations(range(n), 2))
    pair_values = np.full((len(pairs), 2), np.nan)
    pair_valid = np.zeros((len(pairs), 2), bool)
    for row, (left, right) in enumerate(pairs):
        if statuses[left][1] == statuses[right][1] == "ok":
            value = pearson(gradients[left][:, 0], gradients[right][:, 0])
            if value is not None: pair_values[row, 0] = value; pair_valid[row, 0] = True
        if gpa is not None and statuses[n][1] == "ok":
            value = pearson(aligned[left, :, 0], aligned[right, :, 0])
            if value is not None: pair_values[row, 1] = value; pair_valid[row, 1] = True
    per_subject = []
    for person, participant in enumerate(people):
        indices = [i for i, pair in enumerate(pairs) if person in pair]
        counts = pair_valid[indices].sum(axis=0)
        values = [float(np.mean(pair_values[indices, arm])) if counts[arm] == n - 1 else None for arm in range(2)]
        basis = bases[person]
        per_subject.append(dict(participant_id=participant, embedding_status=statuses[person][0],
                                principal_status=statuses[person][1], retained_span_status=statuses[person][2],
                                unaligned_signed=values[0], aligned_signed=values[1], n_partners_expected=n - 1,
                                unaligned_n_defined=int(counts[0]), aligned_n_defined=int(counts[1]),
                                nuisance_rank=reference["nuisance_ranks"][participant],
                                raw_principal_gap=None if basis is None else basis["principal_gap"],
                                retained_boundary_gap=None if basis is None else basis["retained_boundary_gap"]))
    quantity_ids = names + ["aligned_mean"]
    display, signs, valid, config_rows, summaries = [], [], [], [], []
    for index, name in enumerate(quantity_ids):
        is_aligned = index == len(configs)
        source_index = n if is_aligned else n + index
        gradient = None if is_aligned and gpa is None else np.mean(aligned, axis=0) if is_aligned else gradients[source_index]
        summary, coords, direction, mask, means = network_summary(gradient, bases[source_index], networks, network_order,
                                                                 align_mean=is_aligned, reference_principal=statuses[n][1],
                                                                 n_components=k)
        if is_aligned:
            expected = n; defined = n if gpa is not None else 0
            row = dict(quantity=name, n_subjects_expected=expected, n_subjects_defined=defined, **summary)
        else:
            membership = arrays["configuration_membership"][index]
            expected = int(membership.sum())
            arm = int(configs[index]["bandpass"])
            defined = int(np.all(arrays["person_parcel_active"][membership, arm], axis=1).sum())
            row = dict(config=name, subject_ids=[person for person, keep in zip(people, membership) if keep],
                       bandpass=configs[index]["bandpass"], embedding_status=statuses[source_index][0],
                       principal_status=statuses[source_index][1], retained_span_status=statuses[source_index][2],
                       **{key: value for key, value in summary.items() if key != "status"})
        summaries.append(row)
        for network in network_order:
            config_rows.append(dict(quantity=name, network=network, n_subjects_expected=expected, n_subjects_defined=defined,
                                    n_parcels=int(np.sum(networks == network)), **summary,
                                    **{f"mean_g{c + 1}": value for c, value in enumerate(means[network])}))
        display.append(coords); signs.append(direction); valid.append(mask)
    aggregates = []
    for arm in range(2):
        count = int(pair_valid[:, arm].sum())
        aggregates.append(dict(value=float(np.mean(pair_values[:, arm])) if count == len(pairs) else None,
                               status="ok" if count == len(pairs) else "incomplete_support", n_expected=len(pairs), n_defined=count))
    apexes = [row["apex_network"] for row in summaries[:-1]]
    complete = all(value is not None for value in apexes)
    iterations = 0 if gpa is None else gpa["n_iterations"]
    termination = "undefined" if gpa is None else "converged" if iterations < m.GPA_MAX_ITER or (
        len(gpa["distances"]) >= 2 and abs(gpa["distances"][-1] - gpa["distances"][-2]) < m.GPA_STOP_TOL) else "iteration_cap"
    results = dict(schema_version="gradient-results-v2", status="ok", n_subjects=n, n_parcels=p, n_components=k,
                   n_frames=len(arrays["frame_indices"]), unaligned_signed=aggregates[0], aligned_signed=aggregates[1],
                   configuration_summaries=summaries[:-1], aligned_mean_summary=summaries[-1],
                   principal_gradient_identity_robust=(len(set(apexes)) == 1) if complete else None,
                   robustness_status="ok" if complete else "incomplete_configuration_support",
                   apex_networks_observed=[name for name in network_order if name in apexes],
                   gpa=dict(status="alignment_undefined" if gpa is None else "ok", n_iterations=iterations, termination=termination))
    derived = dict(aligned_gradients=aligned, quantity_ids=np.asarray(quantity_ids), display_coordinates=np.stack(display),
                   display_signs=np.stack(signs), display_valid=np.stack(valid),
                   pair_participant_ids=np.asarray([[people[l], people[r]] for l, r in pairs]),
                   signed_pair_consistency=pair_values, pair_consistency_valid=pair_valid)
    return dict(arrays=derived, configurations=config_rows, per_subject=per_subject, results=results)
