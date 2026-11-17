"""Gated original-release MAT extraction, never an authenticated source fixture.

The installed source is disabled.  A separately installed operator authority must
approve the exact admission AND mapping digests before any original path is used.
Candidates receive returned packets, never this object or its authority.  Python
object privacy is not process isolation; the runtime owns that separate boundary.

Only MATLAB v5 (including compressed v5/v7 files) is implemented by SciPy loadmat.
MATLAB v7.3/HDF5, structs, sparse and opaque MATLAB objects fail explicitly.  No
field name, trial availability, clock conversion, axis, or support is inferred.
An independently authenticated schema supplies every top-level field and every
cell leaf. Parser memory limits require the separately qualified process envelope;
logical decoded-byte checks alone are not a hard resident-memory bound.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import io
import json
import math
import os
from pathlib import PurePosixPath
import stat
import warnings

from .basis import basis as _basis


class SourceError(ValueError):
    pass


class BackendUnavailable(SourceError):
    pass


def _need(ok, message):
    if not ok:
        raise SourceError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _sha(value):
    _need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
          "Exact authenticated SHA-256 required")


def _exact(value, keys, name):
    _need(type(value) is dict and set(value) == set(keys), "Exact " + name + " fields required")


@dataclass(frozen=True)
class Limits:
    """Future independently approved logical ceilings, not a RAM guarantee."""
    source_read_bytes: int
    member_bytes: int
    decoded_bytes: int
    metadata_bytes: int
    schema_nodes: int

    def validate(self):
        _need(all(type(v) is int and v > 0 for v in vars(self).values()),
              "Explicit positive independently approved source limits required")


def _state(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _path_parts(value):
    _need(type(value) is str and value and "\\" not in value and "\0" not in value,
          "Literal POSIX relative member required")
    p = PurePosixPath(value)
    _need(not p.is_absolute() and str(p) == value and all(x not in (".", "..") for x in p.parts),
          "Unsafe/noncanonical member path")
    return p.parts


class _OwnedRelease:
    """Exact allowlisted directory tree and held no-follow regular descriptors.

    Generic low-level primitive used by tiny invented tests. Only OriginalMatSource
    can turn its snapshots into original programme projections after authority.
    Unknown members are rejected by names alone, without opening their bodies.
    """
    def __init__(self, root, identities, limits):
        self.files, self.dirs, self.edges, self.census, self.read_bytes = {}, [], [], [], 0
        self.identities, self.limits = identities, limits
        try:
            limits.validate()
            _need(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"),
                  "No-follow descriptor platform required")
            _need(type(root) is str and root.startswith("/") and "\0" not in root,
                  "Literal absolute release root required")
            _need(str(PurePosixPath(root)) == root and ".." not in PurePosixPath(root).parts,
                  "Canonical absolute root required")
            tree = {}
            for member, facts in identities.items():
                parts = _path_parts(member)
                _exact(facts, {"bytes", "sha256"}, "source identity")
                _need(type(facts["bytes"]) is int and 0 < facts["bytes"] <= limits.member_bytes,
                      "Member size exceeds independently approved limit")
                _sha(facts["sha256"])
                node = tree
                for part in parts[:-1]:
                    _need(part not in node or type(node[part]) is dict, "File/directory collision")
                    node = node.setdefault(part, {})
                _need(parts[-1] not in node, "Duplicate member path")
                node[parts[-1]] = member
            _need(sum(x["bytes"] for x in identities.values()) <= limits.source_read_bytes,
                  "Complete release exceeds approved logical read budget")
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            fd = os.open("/", flags)
            self.dirs.append(fd)
            for part in PurePosixPath(root).parts[1:]:
                child = os.open(part, flags, dir_fd=fd)
                self.dirs.append(child)
                self.edges.append((fd, part, child, _state(os.fstat(child))))
                fd = child
            self._walk(fd, tree)
            self.verify()
        except BaseException:
            self.close()
            raise

    def _walk(self, parent, tree):
        self.census.append((parent, set(tree)))
        _need(set(os.listdir(parent)) == set(tree), "Release membership differs; unknown member was not opened")
        for name, child in sorted(tree.items()):
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if type(child) is dict:
                _need(stat.S_ISDIR(before.st_mode), "Non-directory or symlink member")
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                self.dirs.append(fd)
                _need(_state(before) == _state(os.fstat(fd)), "Directory changed during owned open")
                self.edges.append((parent, name, fd, _state(before)))
                self._walk(fd, child)
            else:
                _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                      "Source member must be an unlinked-to-other-paths regular file")
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=parent)
                after = os.fstat(fd)
                self.files[child] = (fd, parent, name, _state(after))
                _need(_state(before) == _state(after) and after.st_size == self.identities[child]["bytes"],
                      "Source member changed or has wrong original size")

    def verify(self):
        for fd, names in self.census:
            _need(set(os.listdir(fd)) == names, "Owned release membership changed")
        for parent, name, fd, expected in self.edges:
            # Directory metadata can change for unrelated siblings in ancestor
            # directories. The owned inode/type, not ancestor mtime, is binding.
            a = os.stat(name, dir_fd=parent, follow_symlinks=False)
            b = os.fstat(fd)
            _need((a.st_dev, a.st_ino, a.st_mode) == (b.st_dev, b.st_ino, b.st_mode) == expected[:3],
                  "Owned source directory was replaced")
        for fd, parent, name, expected in self.files.values():
            _need(_state(os.fstat(fd)) == expected == _state(os.stat(name, dir_fd=parent, follow_symlinks=False)),
                  "Owned source file changed or was replaced")

    def snapshot(self, member):
        _need(member in self.files, "Only exact admitted original members may be read")
        self.verify()
        fd, _, _, expected = self.files[member]
        size = self.identities[member]["bytes"]
        _need(self.read_bytes + size <= self.limits.source_read_bytes, "Cumulative source reads exceed approved limit")
        os.lseek(fd, 0, os.SEEK_SET)
        chunks, remaining = [], size
        while remaining:
            data = os.read(fd, min(remaining, 1024 * 1024))
            self.read_bytes += len(data)
            _need(data, "Unexpected source EOF")
            chunks.append(data)
            remaining -= len(data)
        # fstat and SHA bind the exact immutable buffer parsed below; no parser
        # reopens the path or reads from a mutable original descriptor.
        raw = b"".join(chunks)
        self.verify()
        _need(hashlib.sha256(raw).hexdigest() == self.identities[member]["sha256"],
              "Original source content authentication failed")
        return raw

    def close(self):
        for fd, *_ in self.files.values():
            os.close(fd)
        self.files.clear()
        for fd in reversed(self.dirs):
            os.close(fd)
        self.dirs.clear()


class _MeteredBuffer(io.BytesIO):
    def __init__(self, raw, maximum):
        super().__init__(raw)
        self.logical_reads, self.maximum = 0, maximum

    def read(self, size=-1):
        requested = len(self.getbuffer()) - self.tell() if size < 0 else size
        _need(self.logical_reads + requested <= self.maximum, "MAT parser logical-read limit exceeded")
        result = super().read(size)
        self.logical_reads += len(result)
        return result


def _schema_cost(node, remaining):
    """Require every leaf shape/dtype before parser invocation; no guessed axes."""
    _need(remaining[0] > 0, "Authenticated schema-node ceiling exceeded")
    remaining[0] -= 1
    _need(type(node) is dict and node.get("kind") in ("numeric", "char", "cell"),
          "Unsupported MAT node; explicit numeric/char/cell schema required")
    shape = node.get("shape")
    _need(type(shape) is list and len(shape) >= 2 and all(type(x) is int and x >= 0 for x in shape),
          "Exact unsqueezed MATLAB shape required")
    count = math.prod(shape)
    if node["kind"] == "cell":
        _exact(node, {"kind", "shape", "children"}, "cell schema")
        _need(type(node["children"]) is list and len(node["children"]) == count,
              "Every cell leaf must have an authenticated schema, in MATLAB column-major order")
        return count * 8 + sum(_schema_cost(x, remaining) for x in node["children"])
    import numpy as np
    _exact(node, {"kind", "shape", "dtype"}, "leaf schema")
    try:
        dtype = np.dtype(node["dtype"])
    except (TypeError, ValueError) as exc:
        raise SourceError("Invalid authenticated dtype") from exc
    _need(dtype.str == node["dtype"] and dtype.kind in ("biuf" if node["kind"] == "numeric" else "U"),
          "Only explicit real numeric or Unicode character dtype is supported")
    return count * dtype.itemsize


def _validate_node(value, node):
    import numpy as np
    _need(type(value) is np.ndarray and list(value.shape) == node["shape"], "Observed MAT field shape differs from independent schema")
    if node["kind"] == "cell":
        _need(value.dtype == np.dtype(object), "Observed field is not an admitted cell array")
        for child, spec in zip(value.ravel(order="F"), node["children"]):
            _validate_node(child, spec)
    else:
        _need(value.dtype.str == node["dtype"], "Observed MAT dtype differs from independent schema")
    return value


def _member_schema(schema, limits):
    """Complete pre-I/O schema/resource validation; metadata is independently approved."""
    _exact(schema, {"format", "fields", "decoded_bytes", "mapping_receipt", "parser_read_bytes"}, "MAT schema")
    _sha(schema["mapping_receipt"])
    _need(schema["format"] == "mat5", "MAT v7.3/HDF5 and unknown MAT versions are unsupported; no fallback guessing")
    _need(type(schema["fields"]) is dict and schema["fields"] and all(type(k) is str and k and not k.startswith("__") for k in schema["fields"]),
          "All observed top-level MAT fields required")
    count = [limits.schema_nodes]
    decoded = sum(_schema_cost(n, count) for n in schema["fields"].values())
    _need(type(schema["decoded_bytes"]) is int and decoded == schema["decoded_bytes"] <= limits.decoded_bytes,
          "Authenticated complete decoded-byte bound differs or exceeds limit")
    _need(type(schema["parser_read_bytes"]) is int and 0 < schema["parser_read_bytes"] <= limits.source_read_bytes * 16,
          "Explicit finite parser-read bound required")
    return decoded


def _load_mat(raw, schema, limits):
    """Concrete parser, no caller-supplied array-producing callback."""
    _member_schema(schema, limits)
    _need(len(raw) >= 128 and raw[:19] == b"MATLAB 5.0 MAT-file"[:19]
          and raw[126:128] in (b"IM", b"MI"), "MAT version/header does not match admitted v5 format")
    try:
        from scipy.io import loadmat
    except ImportError as exc:
        raise BackendUnavailable("SciPy loadmat is not installed; original MAT source remains unavailable") from exc
    stream = _MeteredBuffer(raw, schema["parser_read_bytes"])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fields = loadmat(stream, appendmat=False, byte_order=None, mat_dtype=False,
                             squeeze_me=False, chars_as_strings=False, struct_as_record=True,
                             verify_compressed_data_integrity=True, simplify_cells=False)
    except Exception as exc:
        failure = exc if isinstance(exc, SourceError) else SourceError("Explicit SciPy v5 parsing failed; no format conversion or fallback")
        failure.parser_logical_read_bytes = stream.logical_reads
        raise failure from (None if failure is exc else exc)
    try:
        observed = {k: v for k, v in fields.items() if k not in ("__header__", "__version__", "__globals__")}
        _need(set(observed) == set(schema["fields"]), "Observed top-level fields differ from authenticated roster")
        for field, spec in schema["fields"].items():
            _validate_node(observed[field], spec)
    except Exception as exc:
        exc.parser_logical_read_bytes = stream.logical_reads
        raise
    return observed, stream.logical_reads


def _freeze(value):
    import numpy as np
    out = np.array(value, copy=True, order="C")
    out.flags.writeable = False
    return out


def _public_copy(value):
    import numpy as np
    if type(value) is np.ndarray:
        if value.dtype == np.dtype(object):
            out = np.empty(value.shape, dtype=object)
            for i in np.ndindex(value.shape):
                out[i] = _public_copy(value[i])
            out.flags.writeable = False
            return out
        return _freeze(value)
    if type(value) is dict:
        return {k: _public_copy(v) for k, v in value.items()}
    if type(value) in (tuple, list):
        return type(value)(_public_copy(v) for v in value)
    return copy.deepcopy(value)


def _real64(value):
    """No lossy source-coordinate/rate conversion is admitted implicitly."""
    import numpy as np
    _need(value.dtype.kind in "fiu" and value.dtype.itemsize <= 8,
          "Only source-real values representable by the float64 contract are supported")
    if value.dtype.kind in "iu":
        _need(np.all(value >= -(2**53)) and np.all(value <= 2**53),
              "Integer source values exceed exact float64 identity range")
    return value.astype(np.float64)


def _matrix(fields, mapping, name):
    import numpy as np
    _exact(mapping, {"field", "axes", "rows", "columns"}, name + " mapping")
    _need(mapping["field"] in fields and mapping["axes"] in ([0, 1], [1, 0]), "Explicit admitted matrix field/axis mapping required")
    raw = fields[mapping["field"]]
    _need(type(raw) is np.ndarray and raw.ndim == 2 and raw.dtype.kind in "fiu", "Real source matrix required")
    a = raw.transpose(mapping["axes"])
    _need(mapping["rows"] == list(range(a.shape[0])) and mapping["columns"] == list(range(a.shape[1])),
          "Full original matrix row/column order required; slicing/reordering forbidden")
    return _freeze(_real64(a))


def _case_projection(case, header, mapping, response_fields, feature_fields, stimulus_set):
    """Source arithmetic only: raw features, source PSTH, ordinary means/support."""
    import numpy as np
    _exact(mapping, {"features", "psth", "clock", "row_ids", "index_manifest", "support", "trial_fields", "mapping_receipt"}, "case mapping")
    _sha(mapping["mapping_receipt"])
    features = _matrix(feature_fields, mapping["features"], "feature")
    _need(features.shape == (header["source_rows"], 20), "Complete native feature rows and twenty raw coordinates required")
    p = mapping["psth"]
    _exact(p, {"field", "cell_shape", "cell_order", "matrix_axes", "source_rows"}, "PSTH mapping")
    _need(p["field"] in response_fields and p["matrix_axes"] in ([0, 1], [1, 0]), "Explicit cell-matrix PSTH mapping required")
    cells = response_fields[p["field"]]
    ncell, nrow, nt = len(header["cell_ids"]), header["source_rows"], len(header["times_ms"])
    _need(type(cells) is np.ndarray and cells.dtype == np.dtype(object) and list(cells.shape) == p["cell_shape"]
          and cells.size == ncell and p["cell_order"] == list(range(ncell))
          and p["source_rows"] == list(range(nrow)), "Every original cell and source row must be retained in admitted order")
    matrices = []
    for leaf in cells.ravel(order="F"):
        _need(type(leaf) is np.ndarray and leaf.ndim == 2 and leaf.dtype.kind in "fiu", "Admitted numeric PSTH cell leaf required")
        matrix = leaf.transpose(p["matrix_axes"])
        _need(matrix.shape == (nrow, nt), "PSTH cell loses original row/time support")
        matrices.append(matrix)
    psth = _freeze(_real64(np.stack(matrices, axis=1)))
    clock = mapping["clock"]
    _exact(clock, {"field", "shape", "native_unit", "scale_to_ms", "offset_ms", "receipt"}, "clock mapping")
    _sha(clock["receipt"])
    _need(clock["receipt"] == header["clock_units_receipt"] and clock["native_unit"] == "ms"
          and type(clock["scale_to_ms"]) in (int, float) and clock["scale_to_ms"] == 1
          and type(clock["offset_ms"]) in (int, float) and clock["offset_ms"] == 0,
          "Original numeric-ms identity must be independently confirmed; README/driver conflict unresolved, conversion forbidden")
    _need(clock["field"] in response_fields, "Admitted clock field missing")
    raw_clock = response_fields[clock["field"]]
    _need(type(raw_clock) is np.ndarray and raw_clock.dtype.kind in "fiu" and list(raw_clock.shape) == clock["shape"]
          and raw_clock.ndim == 2 and 1 in raw_clock.shape and raw_clock.size == nt, "Exact source clock vector shape required")
    times = _freeze(_real64(raw_clock.ravel(order="F")) * clock["scale_to_ms"])
    _need(np.array_equal(times, np.asarray(header["times_ms"])), "Original physical clock differs from independently admitted clock")
    _basis("units").require_hz(header["response_units"])
    _need(mapping["trial_fields"] == header["trial_fields"] and all(x in response_fields for x in mapping["trial_fields"]),
          "Optional trial availability must match independent observed fields; no trial substitution")
    ids = mapping["row_ids"]
    _need(type(ids) is list and len(ids) == len(set(ids)) == nrow and all(type(x) is str and x for x in ids),
          "All native rows, including ancillary RMS rows, need unique opaque public row IDs")
    support = mapping["support"]
    _exact(support, {"rule", "receipt"}, "source support")
    _sha(support["receipt"])
    _need(support["rule"] == "source_response_not_nan_after_ordinary_mean", "Explicit source NaN row-deletion support required")
    reproduction = _basis("reproduction")
    index = mapping["index_manifest"]
    _exact(index, {"unfamiliar", "familiar", "matched", "ancillary", "subsets", "role_qualification_sha256",
                   "sampling_qualification_sha256", "sampling_procedure"}, "native index manifest")
    native_index = reproduction.IndexManifest(**{k: tuple(tuple(y) for y in v) if k == "subsets" else tuple(v)
                                                if k in ("unfamiliar", "familiar", "matched", "ancillary") else v for k, v in index.items()})
    native_index = reproduction.validate_index_manifest(native_index, stimulus_set, nrow)
    values = {"features": features, "psth": psth, "times": times, "row_ids": tuple(ids), "index_manifest": native_index}
    for mode, label, bins_key in (("static", "static", "static_bins"), ("time_course", "time", "time_bins")):
        plan = reproduction.build_windows(times, mode)
        _need([list(b) for b in plan.indices] == header[bins_key], "Source window membership changed")
        with np.errstate(invalid="ignore", over="ignore"):
            means = np.stack([np.mean(psth[:, :, list(b)], axis=2) for b in plan.indices], axis=2)
        if mode == "static":
            means = means[:, :, 0]
        values[label] = _freeze(means)
        # NaN support matches source analysis_STA. Infinity must not silently be
        # dropped; the prediction interface refuses finite-support violations.
        values[label + "_support"] = _freeze(~np.isnan(means))
    return values


class OriginalMatSource:
    """Trusted operator-only source; projections require scoped capabilities."""
    def __init__(self):
        raise SourceError("Use the gated OriginalMatSource.open constructor")

    @classmethod
    def open(cls, root, contract, admission, mapping, *, authority, capability, limits):
        # Intentionally before root conversion/stat/open, parser imports or schema
        # examination: a caller's None/JSON flag never creates source authority.
        _need(capability is not None and authority is not None, "Independent future operator source capability required before source access")
        _need(callable(getattr(authority, "require_source", None)), "Installed source authority verifier required")
        ad, md = _digest(admission), _digest(mapping)
        _need(authority.require_source(capability, "source_open", admission_digest=ad, mapping_digest=md,
                                       context=None, configuration=None, row_ids=(), seal=None) is True,
              "Operator rejected source-open capability")
        contract, admission, mapping = copy.deepcopy(contract), copy.deepcopy(admission), copy.deepcopy(mapping)
        _need(_digest(admission) == ad and _digest(mapping) == md, "Approved source metadata changed during authorization")
        _need(type(limits) is Limits, "Source-owned explicit Limits required")
        limits.validate()
        _need(len(json.dumps({"contract": contract, "admission": admission, "mapping": mapping}).encode()) <= limits.metadata_bytes,
              "Authenticated complete source metadata exceeds approved bound")
        proof = _basis("admission").validate_admission(admission, contract)
        _need(proof["admission_digest"] == ad, "Admission digest changed")
        _exact(mapping, {"schema", "admission_digest", "members", "cases", "ancillary", "independent_mapping_receipt"}, "source mapping")
        _need(mapping["schema"] == "paper020_authenticated_mat_mapping_v1" and mapping["admission_digest"] == ad,
              "Exact independent source mapping/admission join required")
        _sha(mapping["independent_mapping_receipt"])
        roles = {x["member"]: x for x in contract["source_roles"]}
        _need(set(mapping["members"]) == set(roles) and set(mapping["cases"]) == set(admission["cases"]),
              "Complete thirty MAT roles and fourteen case mappings required")
        ancillary = {k for k, v in roles.items() if v["role"] in ("ancillary_screening_response", "screening_labels")}
        _need(set(mapping["ancillary"]) == ancillary, "All thirteen screening responses and screening labels require explicit full projections")
        for member, description in mapping["ancillary"].items():
            _exact(description, {"role", "all_fields", "row_ids", "row_field", "row_axis", "cell_field", "receipt"}, "ancillary mapping")
            _sha(description["receipt"])
            _need(description["role"] == roles[member]["role"]
                  and description["all_fields"] == admission["members"][member]["observed_fields"],
                  "Ancillary role and complete field roster must be independently admitted")
        declared, parser_ceiling = 0, 0
        for member, schema in mapping["members"].items():
            _need(set(schema.get("fields", {})) == set(admission["members"][member]["observed_fields"]),
                  "Parser schema differs from independently authenticated actual field roster")
            _need(type(schema.get("decoded_bytes")) is int and schema["decoded_bytes"] > 0,
                  "Explicit decoded-byte budget required for every MAT member")
            declared += _member_schema(schema, limits)
            parser_ceiling += schema["parser_read_bytes"]
        _need(parser_ceiling <= limits.source_read_bytes * 16, "Complete parser logical-read ceiling exceeds approved envelope")
        projection_bytes = 0
        for header in admission["cases"].values():
            rows, cells = header["source_rows"], len(header["cell_ids"])
            times, windows = len(header["times_ms"]), len(header["time_bins"])
            projection_bytes += 8 * (rows * (20 + cells * times) + times) + 9 * rows * cells * (windows + 1)
        _need(declared + projection_bytes <= limits.decoded_bytes,
              "Complete raw plus prepared thirty-member/fourteen-case universe exceeds independent logical array ceiling")
        self = object.__new__(cls)
        self._authority, self._ad, self._md = authority, ad, md
        self._admission, self._mapping, self._contract = copy.deepcopy(admission), copy.deepcopy(mapping), copy.deepcopy(contract)
        self._cases, self._members = {}, {}
        self._closed = False
        self._audit = {"original_files": 43, "mat_members": 30, "source_read_bytes": 0,
                       "parser_logical_read_bytes": 0, "declared_decoded_bytes": declared, "prepared_projection_bytes": projection_bytes,
                       "scientific_qualification_claim": False}
        owned = None
        try:
            owned = _OwnedRelease(root, self._admission["source_files"], limits)
            for member in sorted(admission["source_files"]):
                raw = owned.snapshot(member)
                if member in roles:
                    parsed, read_bytes = _load_mat(raw, self._mapping["members"][member], limits)
                    self._members[member] = parsed
                    self._audit["parser_logical_read_bytes"] += read_bytes
            owned.verify()
            self._audit["source_read_bytes"] = owned.read_bytes
            for configuration in self._contract["configurations"]:
                name = configuration["configuration"]
                self._cases[name] = _case_projection(name, self._admission["cases"][name], self._mapping["cases"][name],
                    self._members[configuration["data_member"]], self._members[configuration["feature_member"]], configuration["stimulus_set"])
            self._join_rows()
            self._validate_ancillary()
        except BaseException as exc:
            self._audit["source_read_bytes"] = 0 if owned is None else owned.read_bytes
            self._audit["parser_logical_read_bytes"] += getattr(exc, "parser_logical_read_bytes", 0)
            self._audit["failed"] = True
            self._audit["failure_type"] = type(exc).__name__
            exc.source_audit = dict(self._audit)
            self.close()
            raise
        finally:
            if owned is not None:
                owned.close()
        return self

    def _join_rows(self):
        self._rows = {x["row_id"]: dict(x) for x in self._admission["rows"]}
        all_native_ids = []
        for case, values in self._cases.items():
            all_native_ids.extend(values["row_ids"])
            rows = [x for x in self._admission["rows"] if x["configuration"] == case]
            for row in rows:
                _need(values["row_ids"][row["source_row"]] == row["row_id"], "Opaque row ID/source-index join changed")
        _need(len(set(all_native_ids)) == len(all_native_ids), "Native IDs must be globally unique across complete configurations")

    def _validate_ancillary(self):
        import numpy as np
        for member, m in self._mapping["ancillary"].items():
            fields = self._members[member]
            _need(set(m["all_fields"]) == set(fields) and m["row_field"] in fields,
                  "Every ancillary field must survive original parsing")
            ids = m["row_ids"]
            _need(type(ids) is list and ids and len(set(ids)) == len(ids) and all(type(x) is str and x for x in ids),
                  "Every ancillary source row needs an independently admitted opaque ID")
            _need(type(m["row_axis"]) is int and m["row_axis"] >= 0, "Ancillary row axis must be explicit")
            if m["cell_field"] is None:
                leaves = [fields[m["row_field"]]]
            else:
                _need(m["cell_field"] == m["row_field"] and fields[m["cell_field"]].dtype == np.dtype(object),
                      "Ancillary PSTH cell mapping required")
                leaves = fields[m["cell_field"]].ravel(order="F")
            _need(len(leaves) > 0 and all(m["row_axis"] < leaf.ndim and leaf.shape[m["row_axis"]] == len(ids) for leaf in leaves),
                  "Ancillary projection drops or invents original rows")

    def _authorize(self, capability, action, *, context=None, configuration=None, row_ids=(), seal=None):
        _need(not self._closed and capability is not None, "Live operator source and scoped capability required")
        _need(self._authority.require_source(capability, action, admission_digest=self._ad, mapping_digest=self._md,
              context=context, configuration=configuration, row_ids=tuple(row_ids), seal=seal) is True,
              "Operator rejected source projection capability")

    def _indices(self, case, row_ids):
        _need(type(row_ids) in (list, tuple) and row_ids and len(row_ids) == len(set(row_ids)), "Nonempty unique exact requested row IDs required")
        _need(case in self._cases and all(r in self._rows and self._rows[r]["configuration"] == case for r in row_ids),
              "Requested rows lack the full admitted source-index join")
        return [self._rows[r]["source_row"] for r in row_ids]

    def native_packet(self, phase, *, context, capability):
        case = phase["configuration"]
        self._authorize(capability, "native", context=context, configuration=case)
        _need(case in self._cases, "Unknown original native configuration")
        values, header = self._cases[case], self._admission["cases"][case]
        original = next(x for x in self._contract["configurations"] if x["configuration"] == case)
        return {"features": _freeze(values["features"]), "psth": _freeze(values["psth"]), "times": _freeze(values["times"]),
                "arguments": {"configuration": case, "stimulus_set": original["stimulus_set"], "cell_ids": list(header["cell_ids"]),
                "feature_ids": list(header["feature_ids"]), "feature_groups": list(header["feature_groups"]),
                "row_ids": list(values["row_ids"]), "index_manifest": values["index_manifest"],
                "mode": phase["mode"], "family": phase["family"], "method": phase["method"]}}

    def training_rows(self, context, kind, case, row_ids, *, capability):
        _need(kind in ("features", "static", "time", "static_support", "time_support"), "Unknown training projection kind")
        self._authorize(capability, "training", context=context, configuration=case, row_ids=row_ids)
        indices = self._indices(case, row_ids)
        result = self._cases[case][kind][indices]
        self._finite_supported(case, indices, kind)
        return _freeze(result)

    def query_features(self, context, case, row_ids, seal, *, capability):
        self._authorize(capability, "query_features", context=context, configuration=case, row_ids=row_ids, seal=seal)
        indices = self._indices(case, row_ids)
        self._finite_supported(case, indices, "features")
        return _freeze(self._cases[case]["features"][indices])

    def _finite_supported(self, case, indices, kind):
        import numpy as np
        base = kind.removesuffix("_support")
        values = self._cases[case][base][indices]
        support = np.ones(values.shape, dtype=bool) if base == "features" else self._cases[case][base + "_support"][indices]
        _need(np.isfinite(values[support]).all(), "Source-supported nonfinite values cannot be repaired, masked or used for improvement")

    def protected_targets(self, *, capability):
        self._authorize(capability, "protected_targets")
        import numpy as np
        splits, programme = _basis("splits"), _basis("programme")
        rows = self._admission["rows"]
        assignment = splits.make_outer_assignment(rows)
        result = {}
        for regime in programme.REGIMES:
            for fold in range(6):
                view = splits.fold_view(rows, assignment, fold, regime)
                for case in self._cases:
                    query = [r for r in view["queries"] if r["configuration"] == case]
                    ids = [r["row_id"] for r in query]
                    indices = self._indices(case, ids)
                    entry = {"row_ids": ids, "familiarity": _freeze(np.asarray([r["stratum"] == "familiar" for r in query], dtype=np.int64)),
                             "repeat_role": _freeze(np.asarray([r["repeat_role"] for r in query], dtype=str)),
                             "response_units": copy.deepcopy(self._admission["cases"][case]["response_units"])}
                    for kind in ("time", "static", "time_support", "static_support"):
                        self._finite_supported(case, indices, kind)
                        entry[kind] = _freeze(self._cases[case][kind][indices])
                    result[(regime, fold, case)] = entry
        return result

    def ancillary_packet(self, member, *, capability):
        self._authorize(capability, "ancillary")
        _need(member in self._mapping["ancillary"], "Only admitted ancillary member projections allowed")
        return {"member": member, "metadata": copy.deepcopy(self._mapping["ancillary"][member]),
                "fields": _public_copy(self._members[member])}

    def audit(self, *, capability):
        self._authorize(capability, "source_audit")
        return {**self._audit, "admission_digest": self._ad, "mapping_digest": self._md}

    def close(self):
        self._closed = True
        self._cases.clear()
        self._members.clear()
