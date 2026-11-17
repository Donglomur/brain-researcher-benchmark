"""Protected full-output decoding after both original participant owners close.

The caller supplies genuine original captures and resource ownership. Numerical
agreement remains a diagnostic; no tolerance or figure metric is invented here.
"""
import io
import os
import re
import zipfile

from .artifacts import collect
from .core import Custody, Refusal, read_exact
from .full_outputs import inspect_result, validate_metadata


def need(value, why):
    if not value:
        raise Refusal(why)


def names(root_fd, limit):
    need(type(limit) is int and limit > 0, "explicit namespace member limit")
    values = []
    with os.scandir(root_fd) as entries:
        for entry in entries:
            need(len(values) < limit and entry.is_file(follow_symlinks=False), "closed ordinary output namespace")
            values.append(entry.name)
    return tuple(values)


def capture_metadata(root_fd, result_pin, budget, custody, *, member_bytes, total_bytes, file_count, fixed_seed):
    """Read exactly the terminal + group +33 original coverage metadata bodies."""
    need(type(member_bytes) is int and type(total_bytes) is int and 0 < member_bytes <= total_bytes,
         "positive prospectively selected complete output ceilings")
    need(type(result_pin) is dict and set(result_pin) == {"name", "bytes", "sha256"} and
         result_pin["name"] == "RESULT_MANIFEST.json" and type(result_pin["bytes"]) is int and
         0 < result_pin["bytes"] <= member_bytes and type(result_pin["sha256"]) is str and
         re.fullmatch("[0-9a-f]{64}", result_pin["sha256"]), "bounded terminal pin before first read")
    raw, _ = read_exact(root_fd, result_pin["name"], result_pin["bytes"], result_pin["sha256"], budget, custody)
    preliminary = inspect_result(raw, result_pin, member_bytes=member_bytes, total_bytes=total_bytes)
    metadata = {}
    for row in preliminary["metadata_requests"]:
        metadata[row["name"]], _ = read_exact(root_fd, row["name"], row["bytes"], row["sha256"], budget, custody)
    admitted = validate_metadata(raw, result_pin, metadata["GROUP_INDEX.json"],
        {n: b for n, b in metadata.items() if n.startswith("coverage_")}, member_bytes=member_bytes,
        total_bytes=total_bytes, actual_names=names(root_fd, file_count))
    need(admitted["fixed_seed"] == fixed_seed, "preselected original group seed")
    return admitted


def _npz(root_fd, row, budget, custody, *, member_bytes):
    import numpy as np
    raw, capture = read_exact(root_fd, row["name"], row["bytes"], row["sha256"], budget, custody)
    local = Custody(custody)
    stream, directory, arrays = io.BytesIO(raw), None, None
    result = None
    with local.attempt("full scientific payload decoding"):
        try:
            directory = zipfile.ZipFile(stream)
            entries = directory.infolist()
            expected = row["npz_members"]
            need(len(entries) == len(expected) and {x.filename for x in entries} == set(expected) and
                 all(not x.is_dir() and not (x.flag_bits & 1) for x in entries) and
                 sum(x.file_size for x in entries) <= member_bytes, "exact bounded full scientific NPZ members")
            stream.seek(0)
            arrays = np.load(stream, allow_pickle=False)
            result = {name[:-4]: arrays[name[:-4]] for name in expected}
            for value in result.values():
                need(value.dtype.kind in "fibu" and np.isfinite(value).all(), "finite nonobject scientific arrays")
        except BaseException as error:
            if local.first is None:
                local.catch("full NPZ body", error)
        finally:
            if arrays is not None:
                local.close("full NPZ arrays", arrays.close)
            if directory is not None:
                local.close("full NPZ directory", directory.close)
            local.close("full NPZ stream", stream.close)
        local.raise_first()
    return result, capture


def decode_full(root_fd, admitted, budget, custody, *, member_bytes, endpoint):
    """All payloads are captured/decoded, while old endpoint rules govern products."""
    import numpy as np
    requests = admitted["capture_requests"]
    products = [{k: row[k] for k in ("key", "name", "bytes", "sha256")}
                for row in requests if row["kind"] == "participant_npz"]
    # Only the explicitly preselected original product endpoint is assessed.
    # All available full-study products still pass original decoding below.
    from .products import ProductKey, endpoint_products
    selected = endpoint_products(endpoint)
    selected_rows = [row for row in products if ProductKey(*row["key"]) in selected]
    primary, axes, captures = collect(root_fd, selected_rows, budget, custody,
                                      member_bytes=member_bytes, endpoint=endpoint)
    need(axes is not None and len(axes[0]) == len(axes[1]) == 141,
         "full corrected141-time-axis programme")
    extra_products = [row for row in products if ProductKey(*row["key"]) not in selected]
    from .artifacts import load_product
    for row in extra_products:
        key, value, current, captured = load_product(root_fd, row, budget, custody, member_bytes=member_bytes)
        need(all(np.array_equal(a, b) for a, b in zip(axes, current)), "full programme extra-product axes")
        captures[key] = captured
    groups, figures = {}, {}
    shape = (len(axes[0]), len(axes[1]))
    for row in requests:
        kind = row["kind"]
        if kind == "participant_npz":
            continue
        if kind == "figure_pdf":
            raw, captured = read_exact(root_fd, row["name"], row["bytes"], row["sha256"], budget, custody)
            need(raw.startswith(b"%PDF-"), "actual captured PDF body")
            figures[row["figure"]] = {"name": row["name"], "bytes": len(raw), "sha256": captured.sha256,
                                       "rendered_or_scientifically_validated": False}
            continue
        values, captured = _npz(root_fd, row, budget, custody, member_bytes=member_bytes)
        need(all(np.array_equal(values[n], axis) for n, axis in zip(("train_times", "test_times"), axes)),
             "full group actual time axes")
        if kind == "group_comparison_npz":
            need(values["subject_values"].shape == (33, *shape), "all33 group subject matrices")
            if "t" in values:
                need(values["t"].shape == shape and values["cluster_masks"].dtype.kind == "b" and
                     values["cluster_masks"].ndim == 3 and values["cluster_masks"].shape[1:] == shape and
                     values["cluster_p"].shape == (len(values["cluster_masks"]),) and
                     np.logical_and(values["cluster_p"] >= 0, values["cluster_p"] <= 1).all() and
                     values["null_max"].ndim == 1 and 0 < len(values["null_max"]) <= 10000,
                     "literal complete cluster-output axes")
            else:
                need((values["subject_values"] == 0).all(), "source-defined structural identity output")
            identity = (kind, row["comparison"])
        elif kind == "BF10_npz":
            need(values["BF10"].shape == shape and (values["BF10"] > 0).all(), "full finite positive BF10 map")
            identity = (kind, row["comparison"])
        else:
            need(kind == "averaged_confusion_npz" and values["value"].shape == (*shape, 4, 4) and
                 np.logical_and(values["value"] >= 0, values["value"] <= 1).all() and
                 np.allclose(values["value"].sum(axis=-1), 1, atol=1e-10, rtol=0),
                 "original averaged random OOF confusion")
            identity = (kind, "group_oof_confusion")
        groups[identity] = values
    return {"products": primary, "axes": axes, "groups": groups, "figures": figures,
            "metadata": admitted, "captures": captures, "qualified_reward": None}


def literal_group_differences(candidate, reference, *, absolute_tolerance):
    """Enumerate supplied-array differences; this does not select a new reward."""
    import numpy as np
    need(type(absolute_tolerance) in (int, float) and np.isfinite(absolute_tolerance) and
         absolute_tolerance >= 0, "external preselected group diagnostic tolerance")
    rows = []
    for identity in sorted(set(candidate["groups"]) | set(reference["groups"])):
        if identity not in candidate["groups"] or identity not in reference["groups"]:
            rows.append({"identity": identity, "status": "different_available_output_disposition"})
            continue
        left, right = candidate["groups"][identity], reference["groups"][identity]
        need(set(left) == set(right), "literal group-array family")
        for name in sorted(left):
            a, b = left[name], right[name]
            if a.shape != b.shape:
                rows.append({"identity": identity, "array": name, "status": "shape_difference",
                             "candidate_shape": tuple(a.shape), "reference_shape": tuple(b.shape)})
            elif a.dtype.kind == "b" or name in ("train_times", "test_times"):
                rows.append({"identity": identity, "array": name, "exact_equal": bool(np.array_equal(a, b))})
            else:
                delta = float(np.max(np.abs(a.astype(float) - b.astype(float)))) if a.size else 0.0
                need(np.isfinite(delta), "finite representable group diagnostic difference")
                rows.append({"identity": identity, "array": name, "maximum_absolute_error": delta,
                             "within_supplied_tolerance": delta <= absolute_tolerance})
    return {"diagnostic_only": True, "qualified_reward": None, "arrays": rows,
            "group_tolerance_supplied": absolute_tolerance,
            "figure_identity_only": [{"figure": key, "exact_bytes_equal":
                candidate["figures"][key]["sha256"] == reference["figures"][key]["sha256"],
                "scientific_figure_agreement": "not assessed"} for key in candidate["figures"]],
            "candidate_dispositions": candidate["metadata"]["comparison_dispositions"],
            "reference_dispositions": reference["metadata"]["comparison_dispositions"]}
