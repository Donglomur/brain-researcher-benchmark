"""Pure bounded packet operations. No filesystem, target or provider access on import.

The owner controls authentic input admission and process isolation. Read-only NumPy
copies prevent accidental alias mutation; they are not an adversarial sandbox.
"""
import ast
import io
import math
import re
import stat
import zipfile

import numpy as np

from . import score_core

CAP = 1048576
MAX_TRAIN_ROWS = 250000
MAX_QUERY_ROWS = 61440
PERSONS = tuple(f"sub-{i:02d}" for i in range(1, 25))
ARMS = ("neural", "within_query_half_shift", "no_neural")


def require(ok, why):
    if not ok:
        raise ValueError(why)


def _integer(value):
    return type(value) is int


def opaque_id(value):
    """Syntax only. Semantic opacity/private permutation requires owner evidence."""
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", value),
            "Bounded ASCII opaque-ID syntax")
    require(not value.startswith("sub-") and "sentence" not in value.lower(),
            "Canonical participant/source-order IDs are not public aliases")
    return value


def _readonly(a):
    out = np.array(a, copy=True, order="C")
    out.flags.writeable = False
    return out


def _finite_vector(a, length):
    require(type(a) is np.ndarray and a.dtype.str == "<f8" and
            a.shape == (length,) and a.flags.c_contiguous and
            np.isfinite(a).all(), "Exact finite float64 vector")
    return a


def validate_subject(subject):
    require(type(subject) is dict and set(subject) ==
            {"id", "query_ids", "query_offsets", "query_samples"},
            "Exact trusted subject descriptor")
    require(subject["id"] in PERSONS, "Canonical operator-side person")
    ids, offsets, n = (subject[k] for k in
                       ("query_ids", "query_offsets", "query_samples"))
    require(type(ids) is list and len(ids) == 120 and
            all(type(x) is str for x in ids) and len(set(ids)) == 120,
            "Exactly120 unique query IDs")
    for ident in ids:
        opaque_id(ident)
    require(_integer(n) and 480 <= n <= MAX_QUERY_ROWS,
            "Full query support within provisional cap; never crop")
    require(type(offsets) is list and len(offsets) == 121 and
            all(_integer(x) for x in offsets) and offsets[0] == 0 and
            offsets[-1] == n and all(b - a >= 4 for a, b in zip(offsets, offsets[1:])),
            "Exact120 complete interval boundaries")
    return subject


def validate_study_manifest(subjects):
    require(type(subjects) in (list, tuple) and len(subjects) == 24,
            "All24 people required")
    for subject in subjects:
        validate_subject(subject)
    require({s["id"] for s in subjects} == set(PERSONS),
            "Exactly all24 canonical people, no duplicates")
    return {s["id"]: s for s in subjects}


def _header(raw):
    require(raw[:8] == b"\x93NUMPY\x01\x00" and len(raw) >= 10, "NPY1 header")
    size = int.from_bytes(raw[8:10], "little")
    require(0 < size <= 4096 and len(raw) >= 10 + size, "Bounded complete NPY header")
    node = ast.parse(raw[10:10 + size].decode("latin1").strip(), mode="eval").body
    require(isinstance(node, ast.Dict), "Literal header dictionary")
    keys = [ast.literal_eval(key) for key in node.keys]
    require(len(keys) == len(set(keys)), "No duplicate NPY header keys")
    return ast.literal_eval(node), 10 + size


def _arrays(body, spec):
    require(type(body) is bytes and 0 < len(body) <= CAP, "Bounded NPZ bytes")
    result = {}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = archive.infolist()
        require(len(rows) == len(spec) and len({r.filename for r in rows}) == len(rows)
                and {r.filename for r in rows} == {k + ".npy" for k in spec},
                "Exact unique NPZ members")
        require(sum(r.file_size for r in rows) <= CAP, "Bounded uncompressed extent")
        for row in rows:
            require(row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    and not row.flag_bits & 1 and
                    stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG),
                    "Ordinary nonencrypted NPY member")
            raw = archive.read(row)
            header, start = _header(raw)
            name = row.filename[:-4]
            dtype, shape = spec[name]
            require(header == {"descr": dtype, "fortran_order": False, "shape": shape},
                    "Exact dtype, shape and C order")
            require(len(raw) == start + math.prod(shape) * np.dtype(dtype).itemsize,
                    "Exact NPY extent; no appended values")
            result[name] = np.frombuffer(raw, dtype=np.dtype(dtype), offset=start).reshape(shape).copy()
    return result


def validate_person_submission(body, subject):
    validate_subject(subject)
    n = subject["query_samples"]
    arrays = _arrays(body, {"prediction": ("<f8", (n,)),
                            "interval_ids": ("<U32", (120,)),
                            "offsets": ("<i8", (121,))})
    require(arrays["interval_ids"].tolist() == subject["query_ids"] and
            arrays["offsets"].tolist() == subject["query_offsets"],
            "Exact supplied IDs, order and support")
    return _readonly(_finite_vector(arrays["prediction"], n))


def validate_all_submissions(bodies, subjects):
    roster = validate_study_manifest(subjects)
    require(type(bodies) is dict and set(bodies) == set(PERSONS),
            "All24 candidate files required before target access")
    return {person: validate_person_submission(bodies[person], roster[person])
            for person in PERSONS}


def validate_predictions(predictions, subjects):
    """No target callback; validates all24 arrays from trusted NPZ admission."""
    roster = validate_study_manifest(subjects)
    require(type(predictions) is dict and set(predictions) == set(PERSONS),
            "All24 complete predictions required")
    for person in PERSONS:
        _finite_vector(predictions[person], roster[person]["query_samples"])
    return predictions


def grade_validated(predictions, subjects, target_loader):
    """Trusted primitive: revalidate entire panel before the first target call.

    Parent must first validate *all11* panels, and enforce protected grading
    authority. This function cannot certify that a caller is privileged.
    """
    validate_predictions(predictions, subjects)
    roster = validate_study_manifest(subjects)
    require(callable(target_loader), "Late target-loader callback")
    targets = {}
    for person in PERSONS:
        targets[person] = _finite_vector(target_loader(person), roster[person]["query_samples"])
    return score_core.score_people(predictions, targets,
                                   {p: roster[p]["query_offsets"] for p in PERSONS},
                                   {p: roster[p]["query_ids"] for p in PERSONS})


def grade_complete(bodies, subjects, target_loader):
    return grade_validated(validate_all_submissions(bodies, subjects), subjects, target_loader)


def assemble_person(predictions_by_id, subject):
    """Trusted inverse-presentation assembly from opaque IDs, without key access."""
    validate_subject(subject)
    require(type(predictions_by_id) is dict and
            set(predictions_by_id) == set(subject["query_ids"]), "Every current prediction once")
    pieces = []
    for ident, start, stop in zip(subject["query_ids"], subject["query_offsets"], subject["query_offsets"][1:]):
        pieces.append(_finite_vector(predictions_by_id[ident], stop - start))
    arrays = {"prediction": np.concatenate(pieces).astype("<f8", copy=False),
              "interval_ids": np.asarray(subject["query_ids"], dtype="<U32"),
              "offsets": np.asarray(subject["query_offsets"], dtype="<i8")}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, array in arrays.items():
            stream = io.BytesIO()
            np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
            archive.writestr(name + ".npy", stream.getvalue())
    body = output.getvalue()
    validate_person_submission(body, subject)
    return body


def validate_channels(labels, kinds):
    labels, kinds = tuple(labels), tuple(kinds)
    require(len(labels) == len(kinds) == 306 and len(set(labels)) == 306,
            "All306 distinct sensors")
    require(all(type(x) is str and re.fullmatch(r"MEG[0-9]{4}", x) for x in labels),
            "MEG sensor labels only")
    require(kinds.count("mag") == 102 and kinds.count("grad") == 204 and
            all(kind == ("mag" if label.endswith("1") else "grad") and
                label[-1] in "123" for label, kind in zip(labels, kinds)),
            "Exact102mag/204grad kinds and source sensor suffixes")
    return labels, kinds


def _half_roll(meg):
    """Pure generic algebra kernel; production make_query_view requires306 sensors."""
    require(type(meg) is np.ndarray and meg.ndim == 2 and len(meg) >= 4,
            "One nonempty complete interval")
    return np.roll(meg, len(meg) // 2, axis=0)


def make_query_view(id, meg, channel_labels, channel_kinds, arm, *, length=None):
    """Create exactly one owned view. Call once; references must not roll again."""
    opaque_id(id)
    require(arm in ARMS, "Declared arm")
    if meg is None:
        require(arm == "no_neural" and _integer(length), "Only no-neural may use length alone")
        n = length
    else:
        require(type(meg) is np.ndarray and meg.dtype.str == "<f8" and
                meg.ndim == 2 and meg.shape[1] == 306 and np.isfinite(meg).all(),
                "One finite float64 samples-by306 interval")
        n = len(meg)
        require(length is None or length == n, "Declared current length agrees")
    require(4 <= n <= MAX_QUERY_ROWS, "Complete current interval within provisional cap")
    result = {"id": id, "length": n, "arm": arm, "fs_hz": 64}
    if arm == "no_neural":
        return result
    labels, kinds = validate_channels(channel_labels, channel_kinds)
    result.update(meg=_readonly(_half_roll(meg) if arm == "within_query_half_shift" else meg),
                  channel_labels=labels, channel_kinds=kinds)
    return result


def validate_training_view(view, expected_run_ids):
    require(type(view) is dict and set(view) == {"meg", "envelope", "offsets", "interval_ids",
            "run_ids", "channel_labels", "channel_kinds", "fs_hz"}, "Exact training view fields")
    require(view["fs_hz"] == 64, "Canonical sampling frequency")
    meg, env, offsets, ids, runs = (view[k] for k in
                                  ("meg", "envelope", "offsets", "interval_ids", "run_ids"))
    require(type(meg) is np.ndarray and meg.dtype.str == "<f8" and meg.ndim == 2 and
            meg.shape[1] == 306 and 4 <= len(meg) <= MAX_TRAIN_ROWS and np.isfinite(meg).all(),
            "Complete finite training MEG; cap is not crop authority")
    _finite_vector(env, len(meg))
    require(type(offsets) is np.ndarray and offsets.dtype.str == "<i8" and offsets.ndim == 1
            and len(offsets) >= 3 and offsets[0] == 0 and offsets[-1] == len(meg)
            and np.all(np.diff(offsets) >= 4), "Complete separate training epochs")
    count = len(offsets) - 1
    for value in (ids, runs):
        require(type(value) is np.ndarray and value.dtype.str == "<U32" and value.shape == (count,),
                "Exact epoch/run ID arrays")
        for ident in value.tolist():
            opaque_id(ident)
    require(len(set(ids.tolist())) == count, "Distinct training epochs")
    require(type(expected_run_ids) in (tuple, list) and len(expected_run_ids) in (2, 4)
            and len(set(expected_run_ids)) == len(expected_run_ids)
            and set(runs.tolist()) == set(expected_run_ids), "All declared source runs contribute")
    validate_channels(view["channel_labels"], view["channel_kinds"])
    return view


def no_neural_training_view(training, expected_run_ids):
    validate_training_view(training, expected_run_ids)
    return {key: _readonly(training[key]) if type(training[key]) is np.ndarray else training[key]
            for key in ("envelope", "offsets", "interval_ids", "run_ids", "fs_hz")}
