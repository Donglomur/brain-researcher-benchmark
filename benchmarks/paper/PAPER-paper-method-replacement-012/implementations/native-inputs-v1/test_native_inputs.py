"""Independent generated NuCLR input controls; no authentic array/model run."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import dependencies
import native

GENERATED_FILE_BYTES = 0


def save_bytes(path, body):
    global GENERATED_FILE_BYTES
    if GENERATED_FILE_BYTES + len(body) > 4 * 1024 * 1024:
        raise AssertionError("generated fixture allocation would be exceeded")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    GENERATED_FILE_BYTES += len(body)


def save_npy(path, values):
    import numpy as np
    buffer = io.BytesIO()
    np.save(buffer, values, allow_pickle=False)
    save_bytes(path, buffer.getvalue())


def file_asset(root, path):
    raw = Path(path).read_bytes()
    relative = Path(path).relative_to(root).as_posix()
    return {"relative_path": relative, "source_member": relative.removeprefix("native/"),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def invented_session(root, sid, definition, *, dtype="<f4", unique_values=None):
    """Small invented arrays at original names; never authentic source bytes."""
    import numpy as np
    count = definition["neurons"]
    folder = Path(root) / "native" / definition["source_directory"]
    source = dependencies.load_dependencies()
    vocabulary = ["EC"] + sorted(source.splits.LABELS["11class"]) + ["IN", "Lamp5-invented"]
    labels = [vocabulary[i % len(vocabulary)] for i in range(count)]
    save_bytes(folder / "neuron.ttype.txt", ("\n".join(labels) + "\n").encode())
    positions = np.arange(count, dtype="<f8")
    for field, offset in (("depth", 100), ("plane", 0), ("rfCenter_Xvis", 200), ("rfCenter_Yvis", 300)):
        values = positions + offset
        if field == "rfCenter_Xvis":
            values[0] = np.nan
        save_npy(folder / ("neuron." + field + ".npy"), values.reshape(-1, 1))
    save_npy(folder / "neuron.stackPosCorrected.npy", np.column_stack((positions + 400, positions + 500)))
    if unique_values is None:
        unique_values = positions.copy()
        unique_values[1] = np.nan
    save_npy(folder / "neuron.UniqueID.npy", unique_values)
    rows = []
    for index, label in enumerate(labels):
        ei = label if label in ("EC", "IN") else "IN"
        subclass = "unknown" if label in ("EC", "IN") else label.split("-")[0]
        rows.append({"id": f"{sid}_u{index}", "session_id": sid,
                     "subject_id": sid.split("_")[0].upper(), "ttype": label,
                     "ei_class": ei, "subclass": subclass,
                     "depth": str(index + 100), "plane": str(index), "rf_center_xvis": "",
                     "rf_center_yvis": str(index + 300), "stackPos_x": str(index + 400),
                     "stackPos_y": str(index + 500)})
    for number, experiment in enumerate(definition["experiments"]):
        values = np.asarray([[1 + number * 100 + frame * 10 + col for col in range(count)]
                             for frame in range(4)], dtype=dtype)
        # Alternate storage order to catch readers that silently assume C order.
        if number % 2:
            values = np.asfortranarray(values)
        save_npy(folder / experiment / "frame.neuralActivity.npy", values)
        save_npy(folder / experiment / "frame.times.npy", np.asarray([0.0, 0.25, 0.5, 0.75], dtype="<f8"))
    return rows


def generated_projections(neurons):
    """Invented projection boundary; archive tokens do not authenticate fixtures."""
    source = dependencies.load_dependencies()
    # Nonlexical order deliberately differs from native and author metadata order.
    ordered = sorted(neurons, key=lambda r: (r["source_neuron_index"] % 11, r["id"]), reverse=True)
    result = []
    for level in source.splits.LABELS:
        if level == "ei":
            selected = ordered
            label_map = {r["id"]: r["ei_class"] for r in selected}
        elif level == "subclass":
            selected = [r for r in ordered if r["source_neuron_index"] < 14 and r["subclass"] in source.splits.LABELS[level]]
            label_map = {r["id"]: r["subclass"] for r in selected}
        else:
            selected = [r for r in ordered if r["source_neuron_index"] < 14 and r["ttype"] in source.splits.LABELS[level]]
            label_map = {r["id"]: r["ttype"] for r in selected}
        ids = list(label_map)
        by_id = {r["id"]: r for r in selected}
        for panel, suffix in source.splits.PANEL_SUFFIX.items():
            splits = []
            if panel == "transductive":
                test = [u for u in ids if by_id[u]["session_id"] not in source.splits.DEV_SESSIONS
                        and by_id[u]["source_neuron_index"] % 4 == 0]
                test_set = set(test)
                val = [u for u in ids if u not in test_set and by_id[u]["source_neuron_index"] % 4 == 1]
                used = test_set | set(val)
                splits.append({"id": "source-0", "test": test, "val": val,
                               "train": [u for u in ids if u not in used]})
            else:
                held_subjects = ["sb028"] if panel == "inductive_zero_shot" else ["sb025", "sb026", "sb028", "sb030"]
                for outer, held in enumerate(held_subjects):
                    train = [u for u in ids if by_id[u]["subject_id"] != held]
                    test = [u for u in ids if by_id[u]["subject_id"] == held
                            and by_id[u]["session_id"] not in source.splits.DEV_SESSIONS]
                    excluded = {u: "Generated original-development-session exclusion"
                                for u in ids if by_id[u]["subject_id"] == held
                                and by_id[u]["session_id"] in source.splits.DEV_SESSIONS}
                    cv = []
                    for subject in ("sb025", "sb026", "sb028", "sb030"):
                        if subject == held:
                            continue
                        fit = [u for u in train if by_id[u]["subject_id"] != subject]
                        validation = [u for u in train if by_id[u]["subject_id"] == subject]
                        if level == "ei" and panel == "inductive_zero_shot":
                            fit += [u for u in ids if by_id[u]["subject_id"] == "sb028"]
                        cv.append({"train": fit, "val": validation})
                    splits.append({"id": f"source-{outer}", "train": train, "test": test,
                                   "train_cv": cv, "excluded": excluded})
            member = f"splits/bugeon/{level}_{suffix}.pkl"
            result.append({"schema": "nuclr_bugeon_source_projection_v2",
                           "source_commit": source.splits.SOURCE_COMMIT,
                           "source_archive_sha256": source.splits.ARCHIVE_SHA256,
                           "source_member": member,
                           "source_member_sha256": hashlib.sha256(("GENERATED:" + member).encode()).hexdigest(),
                           "label_level": level, "panel": panel, "source_label_column": "label",
                           "label_map": dict(label_map),
                           "metadata": [{k: row[k] for k in ("id", "session_id", "subject_id", "source_neuron_index")}
                                        for row in selected], "splits": splits})
    return result


class DependencyControls(unittest.TestCase):
    def test_authenticated_validator_is_reused_without_reopening_source(self):
        before = list(sys.path)
        source = dependencies.load_dependencies()
        self.assertEqual(sys.path, before)
        self.assertEqual(len(source.pins), 3)
        self.assertEqual(source.splits.SOURCE_COMMIT, source.evaluator.SOURCE_COMMIT)
        self.assertEqual(source.splits._evaluator(), source.evaluator)
        with patch.object(source.splits.importlib.util, "spec_from_file_location",
                          side_effect=AssertionError("reopened unauthenticated evaluator")):
            self.assertIs(source.splits._evaluator(), source.evaluator)

    def test_dependency_file_requires_exact_bytes_and_bounded_extent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            body = b"generated = True\n"
            save_bytes(path, body)
            sha = hashlib.sha256(body).hexdigest()
            self.assertEqual(dependencies.read_file(path, len(body), sha), body)
            with self.assertRaises(dependencies.SourceError):
                dependencies.read_file(path, len(body) - 1, sha)
            with self.assertRaises(dependencies.SourceError):
                dependencies.read_file(path, len(body), "0" * 64)

    def test_dependency_file_rejects_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            save_bytes(path, b"pass\n")
            symbolic = Path(directory) / "symbolic.py"
            symbolic.symlink_to(path)
            with self.assertRaises((dependencies.SourceError, OSError)):
                dependencies.read_file(symbolic, 32)
            symbolic.unlink()
            os.link(path, symbolic)
            with self.assertRaises(dependencies.SourceError):
                dependencies.read_file(path, 32)


class NativeArrayControls(unittest.TestCase):
    def test_c_and_fortran_storage_preserve_exact_rows_columns_and_dtype(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            for order in ("C", "F"):
                values = np.array([[101, 102, 103], [201, 202, 203]], dtype="<f8", order=order)
                path = Path(directory) / (order + ".npy")
                save_npy(path, values)
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                with native.NativeArray(path, sha256=sha) as array:
                    self.assertEqual(array.values.tolist(), [[101, 102, 103], [201, 202, 203]])
                    self.assertEqual(array.header["fortran_order"], order == "F")
                    self.assertEqual(array.header["dtype"], "<f8")
                self.assertIsNone(array.values)
                with self.assertRaises(ValueError):
                    array.check()

    def test_wrong_digest_and_changed_open_source_are_refused(self):
        import numpy as np
        global GENERATED_FILE_BYTES
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "values.npy"
            save_npy(path, np.array([[1, 2], [3, 4]], dtype="<f4"))
            with self.assertRaises(ValueError):
                native.NativeArray(path, sha256="0" * 64)
            with native.NativeArray(path) as array:
                with path.open("r+b") as handle:
                    handle.seek(-1, os.SEEK_END)
                    handle.write(b"\x7f")
                    GENERATED_FILE_BYTES += 1
                with self.assertRaises(ValueError):
                    array.check()

    def test_object_big_endian_ragged_extent_and_huge_shape_refuse_before_mmap(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.npy"
            headers = [
                {"descr": "|O", "fortran_order": False, "shape": (2,)},
                {"descr": ">f8", "fortran_order": False, "shape": (2,)},
                {"descr": "<f8", "fortran_order": False, "shape": (10**20, 2)},
                {"descr": "<f8", "fortran_order": False, "shape": (2, 2, 2)},
                {"descr": "<f8", "fortran_order": False, "shape": (True,)},
            ]
            for header in headers:
                body = io.BytesIO()
                np.lib.format.write_array_header_1_0(body, header)
                save_bytes(path, body.getvalue() + b"not-an-array")
                with self.subTest(header=header), patch.object(np, "memmap", side_effect=AssertionError("mapped invalid NPY")):
                    with self.assertRaises(ValueError):
                        native.NativeArray(path)
            save_npy(path, np.array([1, 2], dtype="<f8"))
            save_bytes(path, path.read_bytes() + b"trailing")
            with self.assertRaises(ValueError):
                native.NativeArray(path)

    def test_native_array_refuses_symbolic_and_multiple_links(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "values.npy"
            alias = Path(directory) / "alias.npy"
            save_npy(path, np.array([1, 2], dtype="<f4"))
            alias.symlink_to(path)
            with self.assertRaises((ValueError, OSError)):
                native.NativeArray(alias)
            alias.unlink()
            os.link(path, alias)
            with self.assertRaises(ValueError):
                native.NativeArray(path)


class ArchiveControls(unittest.TestCase):
    def invented_archive(self, folder):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("one/input.txt", b"generated numerical input")
            archive.writestr("two.txt", b"second")
        body = buffer.getvalue()
        path = Path(folder) / "source.zip"
        save_bytes(path, body)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [{"name": item.filename, "bytes": item.file_size, "compressed": item.compress_size,
                        "crc32": f"{item.CRC:08x}", "method": item.compress_type} for item in archive.infolist()]
        spec = {"bytes": len(body), "publisher_md5": hashlib.md5(body, usedforsecurity=False).hexdigest(),
                "members": members}
        return path, spec, hashlib.sha256(body).hexdigest()

    def test_exact_archive_and_new_private_extraction_preserve_bytes(self):
        global GENERATED_FILE_BYTES
        with tempfile.TemporaryDirectory() as folder:
            path, spec, sha = self.invented_archive(folder)
            with native.SourceZip(path, spec, sha256=sha) as archive:
                body = archive.read("one/input.txt", 100)
                self.assertEqual(body, b"generated numerical input")
                output = Path(folder) / "owner" / "input.txt"
                receipt = archive.extract_new("one/input.txt", output, spec["members"][0])
                GENERATED_FILE_BYTES += len(body)
                self.assertEqual(output.read_bytes(), body)
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
                self.assertEqual(receipt["sha256"], hashlib.sha256(body).hexdigest())
                with self.assertRaises(ValueError):
                    archive.extract_new("one/input.txt", output, spec["members"][0])
                with self.assertRaises(ValueError):
                    archive.read("one/input.txt", 1)
            with self.assertRaises(ValueError):
                archive.check()

    def test_changed_archive_identity_order_and_member_extent_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path, spec, sha = self.invented_archive(folder)
            for changed in (dict(spec, bytes=spec["bytes"] + 1), dict(spec, publisher_md5="0" * 32),
                            dict(spec, members=list(reversed(spec["members"])))):
                with self.assertRaises(ValueError):
                    native.SourceZip(path, changed, sha256=sha)
            with self.assertRaises(ValueError):
                native.SourceZip(path, spec, sha256="0" * 64)

    def test_source_member_paths_cannot_escape(self):
        for name in ("/absolute", "../parent", "one/../parent", "one//x", "one/./x", "back\\slash", "null\x00"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                native.safe_name(name)


class SessionRefusalControls(unittest.TestCase):
    def definition(self):
        return {"neurons": 3, "source_directory": "SB025/2019-10-04", "experiments": ["Blank/01", "Natural Scenes/01"]}

    def test_integer_unique_ids_above_float_exact_range_remain_distinct(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            definition = self.definition()
            author = invented_session(folder, "sb025_20191004", definition,
                                       unique_values=np.array([2**53, 2**53 + 1, 0], dtype="<u8"))
            rows, _ = native.session_neurons("sb025_20191004", definition, folder, author)
            self.assertEqual([r["source_unique_id"] for r in rows], [2**53, 2**53 + 1, 0])
            self.assertNotEqual(rows[0]["repeated_cell_id"], rows[1]["repeated_cell_id"])

    def test_invalid_float_unique_ids_are_refused_without_missingness_repair(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            definition = self.definition()
            author = invented_session(folder, "sb025_20191004", definition)
            path = Path(folder) / "native" / definition["source_directory"] / "neuron.UniqueID.npy"
            for value in (-1, 1.5, float("inf"), float(2**53 + 2)):
                save_npy(path, np.array([value, 1, 2], dtype="<f8"))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    native.session_neurons("sb025_20191004", definition, folder, author)

    def test_duplicate_missing_and_conflicting_author_rows_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            definition = self.definition()
            author = invented_session(folder, "sb025_20191004", definition)
            for changed in (author[:-1], author + [dict(author[0])],
                            [dict(author[0], ttype="wrong")] + author[1:]):
                with self.assertRaises(ValueError):
                    native.session_neurons("sb025_20191004", definition, folder, changed)

    def test_bad_clocks_activity_shape_and_zero_normalization_refuse(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            definition = self.definition()
            invented_session(folder, "sb025_20191004", definition)
            path = Path(folder) / "native" / definition["source_directory"] / definition["experiments"][0]
            clock = path / "frame.times.npy"
            for values in ([0.0, 1, float("nan"), 3], [0.0, 2, 1, 3], [0.0, 1, 2]):
                save_npy(clock, np.array(values, dtype="<f8"))
                with self.assertRaises(ValueError):
                    native.inspect_session("sb025_20191004", definition, folder)
            save_npy(clock, np.array([0, 0.25, 0.5, 0.75], dtype="<f8"))
            activity = path / "frame.neuralActivity.npy"
            for values in (np.full((4, 3), np.nan, dtype="<f4"), np.ones((4, 2), dtype="<f4")):
                save_npy(activity, values)
                with self.assertRaises(ValueError):
                    native.inspect_session("sb025_20191004", definition, folder)
            for experiment in definition["experiments"]:
                save_npy(Path(folder) / "native" / definition["source_directory"] / experiment / "frame.neuralActivity.npy",
                         np.zeros((4, 3), dtype="<f4"))
            with self.assertRaises(ValueError):
                native.inspect_session("sb025_20191004", definition, folder)

    def test_source_offsets_report_nearby_blocks_and_refuse_overlaps_without_repair(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            definition = self.definition()
            invented_session(folder, "sb025_20191004", definition)
            clock = Path(folder) / "native" / definition["source_directory"] / definition["experiments"][0] / "frame.times.npy"
            save_npy(clock, np.array([0, 1000, 2000, 3500], dtype="<f8"))
            session = native.inspect_session("sb025_20191004", definition, folder)
            self.assertEqual(session["potential_cross_experiment_240s_pairs"][0]["boundary_distance_seconds"], 100.0)
            self.assertEqual(session["experiments"][1]["source_offset_seconds"], 3600)
            save_npy(clock, np.array([0, 1000, 2000, 4000], dtype="<f8"))
            with self.assertRaises(ValueError):
                native.inspect_session("sb025_20191004", definition, folder)

    def test_float64_normalization_and_complete_block_permutation_preserve_denominator(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            definition = self.definition()
            invented_session(folder, "sb025_20191004", definition, dtype="<f8")
            first = native.inspect_session("sb025_20191004", definition, folder)
            second = native.inspect_session("sb025_20191004", dict(definition, experiments=list(reversed(definition["experiments"]))), folder)
            self.assertEqual(first["normalization"], second["normalization"])
            self.assertNotEqual(first["experiments"][0]["experiment_id"], second["experiments"][0]["experiment_id"])
            assets = {}
            for experiment in definition["experiments"]:
                for name in ("frame.neuralActivity.npy", "frame.times.npy"):
                    asset = file_asset(folder, Path(folder) / "native" / definition["source_directory"] / experiment / name)
                    assets[asset["source_member"]] = asset
            block = native.read_prepared_block(folder, first, definition["experiments"][0], assets, 0, 4)
            self.assertEqual(block["activity"].dtype, np.dtype("<f8"))
            self.assertAlmostEqual(float(block["activity"][0, 0]), 1 / first["normalization"]["percentile"])


class PrivateBoundaryControls(unittest.TestCase):
    def test_owner_json_refuses_duplicate_nonfinite_and_noncanonical_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
                save_bytes(path, body)
                with self.assertRaises(ValueError):
                    native.read_json(path)

    def test_private_output_is_new_mode_0600_and_never_follows_alias(self):
        global GENERATED_FILE_BYTES
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            previous = os.umask(0)
            try:
                native.write_new(path, {"generated": True})
            finally:
                os.umask(previous)
            GENERATED_FILE_BYTES += path.stat().st_size
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            before = path.read_bytes()
            with self.assertRaises((ValueError, OSError)):
                native.write_new(path, {"changed": True})
            self.assertEqual(path.read_bytes(), before)
            alias = Path(folder) / "alias.json"
            victim = Path(folder) / "absent.json"
            alias.symlink_to(victim)
            with self.assertRaises((ValueError, OSError)):
                native.write_new(alias, {"changed": True})
            self.assertFalse(victim.exists())


class CompleteNativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from copy import deepcopy
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.source = dependencies.load_dependencies()
        cls.definition = native.profile()
        cls.author = []
        for sid, definition in cls.definition["sessions"].items():
            cls.author.extend(invented_session(cls.root, sid, definition))
        cls.author.reverse()  # The CSV's order must not be treated as column order.
        cls.sessions, cls.neurons = [], []
        for sid, definition in cls.definition["sessions"].items():
            cells, headers = native.session_neurons(sid, definition, cls.root, cls.author)
            session = native.inspect_session(sid, definition, cls.root)
            session["neuron_headers"] = headers
            cls.sessions.append(session)
            cls.neurons.extend(cells)
        cls.assets = {row["name"]: file_asset(cls.root, cls.root / "native" / row["name"])
                      for row in cls.definition["required_members"]}
        cls.projections = generated_projections(cls.neurons)
        cls.joined = native.join_projections(cls.sessions, cls.neurons, cls.projections)
        cls.by_id = {row["id"]: row for row in cls.neurons}
        cls.generated_profile = deepcopy(cls.definition)
        for row in cls.generated_profile["required_members"]:
            row["bytes"] = cls.assets[row["name"]]["bytes"]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_every_original_session_experiment_column_and_metadata_relation_is_preserved(self):
        self.assertEqual(len(self.sessions), 17)
        self.assertEqual(sum(len(s["experiments"]) for s in self.sessions), 69)
        self.assertEqual(len(self.neurons), 10153)
        self.assertEqual(len(self.assets), 257)
        self.assertEqual({s["session_id"] for s in self.sessions}, self.source.evaluator.SOURCE_SESSIONS)
        for session in self.sessions:
            definition = self.definition["sessions"][session["session_id"]]
            self.assertEqual(session["neurons"], definition["neurons"])
            self.assertEqual([b["experiment_id"] for b in session["experiments"]], definition["experiments"])
            self.assertEqual(session["frames"], 4 * len(definition["experiments"]))
            self.assertEqual(session["signal_units"], "deconvolved_calcium_arbitrary_units")
            self.assertFalse(session["plane_offset_times_applied"])
            self.assertFalse(session["historical_experiment_order_verified"])
            for number, block in enumerate(session["experiments"]):
                self.assertEqual((block["row_start"], block["row_stop"]), (4 * number, 4 * (number + 1)))
                self.assertEqual(block["source_offset_seconds"], number * 3600)
                self.assertEqual(block["shifted_last_second"], number * 3600 + 0.75)
        first = self.by_id["sb025_20191004_u0"]
        self.assertEqual(first["source_unique_id"], 0)
        self.assertEqual(first["repeated_cell_id"], "sb025:UniqueID:0")
        self.assertEqual(self.by_id["sb025_20191007_u0"]["repeated_cell_id"], first["repeated_cell_id"])
        self.assertNotEqual(self.by_id["sb026_20191011_u0"]["repeated_cell_id"], first["repeated_cell_id"])
        self.assertIsNone(self.by_id["sb025_20191004_u1"]["repeated_cell_id"])
        self.assertEqual(self.by_id["sb025_20191004_u1"]["source_unique_id_missing"], "NaN_unmatched")
        self.assertEqual(first["native_numeric_metadata"]["rfCenter_Xvis"], {"kind": "NaN"})
        self.assertEqual(first["native_numeric_metadata"]["depth"], {"kind": "finite", "value": 100.0})
        self.assertIn("not_asserted", first["author_numeric_metadata_join"])
        self.assertEqual(first["author_metadata"]["depth"], "100")

    def test_global_percentile_and_lazy_block_preserve_source_values_clock_and_scalar_dtype(self):
        import numpy as np
        session = self.sessions[0]
        count = session["neurons"]
        values = sorted(1 + exp * 100 + frame * 10 + col
                        for exp in range(len(session["experiments"]))
                        for frame in range(4) for col in range(count))
        position = 0.99 * (len(values) - 1)
        lo, hi = math.floor(position), math.ceil(position)
        expected_percentile = values[lo] + (position - lo) * (values[hi] - values[lo])
        self.assertAlmostEqual(session["normalization"]["percentile"], expected_percentile, places=10)
        for number in (0, len(session["experiments"]) - 1):
            experiment = session["experiments"][number]["experiment_id"]
            raw = native.read_prepared_block(self.root, session, experiment, self.assets, 1, 4, normalized=False)
            self.assertEqual(raw["activity"].tolist(), [[1 + number * 100 + frame * 10 + col
                                                       for col in range(count)] for frame in (1, 2, 3)])
            self.assertEqual(raw["timestamps"].tolist(), [number * 3600 + x for x in (0.25, 0.5, 0.75)])
            normalized = native.read_prepared_block(self.root, session, experiment, self.assets, 1, 4)
            expected = raw["activity"].astype("<f8") / expected_percentile
            # Machine-rounding bound for the declared output dtype, not a
            # scientific equivalence tolerance or comparison threshold.
            np.testing.assert_allclose(normalized["activity"], expected,
                                       rtol=4 * np.finfo(normalized["activity"].dtype).eps, atol=0)
            self.assertEqual(normalized["activity"].dtype.str, session["normalization"]["normalized_dtype"])
            self.assertNotIn("labels", normalized)
            self.assertNotIn("metadata", normalized)
            raw["activity"][0, 0] = -999  # Returned data cannot mutate the mmap.
            again = native.read_prepared_block(self.root, session, experiment, self.assets, 1, 2, normalized=False)
            self.assertEqual(again["activity"][0, 0], 11 + number * 100)

    def test_source_frame_and_asset_bounds_are_strict(self):
        session = self.sessions[0]
        experiment = session["experiments"][0]["experiment_id"]
        for start, stop in ((-1, 1), (1, 1), (3, 2), (0, 5), (True, 3), (0, 1.0)):
            with self.subTest(start=start, stop=stop), self.assertRaises(ValueError):
                native.read_prepared_block(self.root, session, experiment, self.assets, start, stop)
        with self.assertRaises(ValueError):
            native.read_prepared_block(self.root, session, "unknown/00", self.assets, 0, 1)
        selected = session["experiments"][0]["source_directory"] + "/frame.neuralActivity.npy"
        changed = dict(self.assets)
        changed[selected] = dict(changed[selected], sha256="0" * 64)
        with self.assertRaises(ValueError):
            native.read_prepared_block(self.root, session, experiment, changed, 0, 1)

    def test_all_nine_joins_preserve_author_order_splits_and_invalid_ninth_record(self):
        self.assertEqual(len(self.joined), 9)
        for joined, projection in zip(self.joined, self.projections):
            self.assertEqual(joined["ordered_ids"], list(projection["label_map"]))
            self.assertEqual(joined["projection"]["splits"], projection["splits"])
            self.assertEqual([r["id"] for r in joined["metadata"]], list(projection["label_map"]))
            self.assertEqual(joined["ordered_native_addresses"], [
                {"session_id": self.by_id[u]["session_id"], "column": self.by_id[u]["source_neuron_index"]}
                for u in joined["ordered_ids"]])
            self.assertEqual(joined["required_readout_class_balance"], "resample")
            self.assertEqual(joined["transductive_source_route_unresolved"], projection["panel"] == "transductive")
        invalid = [j for j in self.joined if not j["topology_audit"]["matches_registered_topology"]]
        self.assertEqual(len(invalid), 1)
        self.assertEqual((invalid[0]["projection"]["label_level"], invalid[0]["projection"]["panel"]),
                         ("ei", "inductive_zero_shot"))
        for fold in invalid[0]["topology_audit"]["folds"][0]["cv"]:
            self.assertEqual(fold["train_test_overlap"], 3049)
            self.assertEqual(fold["cv_ids_outside_outer_train"], 3846)

    def test_incomplete_or_conflicting_native_and_projection_joins_are_refused(self):
        for sessions, neurons, projections in (
            (self.sessions[:-1], self.neurons, self.projections),
            (self.sessions, self.neurons[:-1], self.projections),
            (self.sessions, self.neurons, self.projections[:-1]),
            (self.sessions, self.neurons, self.projections[:-1] + [self.projections[0]]),
            (self.sessions, self.neurons[:-1] + [self.neurons[0]], self.projections),
        ):
            with self.assertRaises(ValueError):
                native.join_projections(sessions, neurons, projections)
        changed = list(self.projections)
        changed[0] = dict(changed[0], source_archive_sha256="0" * 64)
        with self.assertRaises(ValueError):
            native.join_projections(self.sessions, self.neurons, changed)
        changed[0] = dict(self.projections[0])
        changed[0]["metadata"] = list(changed[0]["metadata"])
        changed[0]["metadata"][0] = dict(changed[0]["metadata"][0], source_neuron_index=999999)
        with self.assertRaises(ValueError):
            native.join_projections(self.sessions, self.neurons, changed)

    def checkpoint(self, joined):
        return [{"id": "generated-no-model", "epoch": 0, "ids": list(joined["ordered_ids"]),
                 "embeddings": [[float(i % 7), 1.0] for i in range(len(joined["ordered_ids"]))]}]

    def test_readout_handoff_preserves_resample_exposure_and_transductive_route_hold(self):
        for level, panel in (("subclass", "inductive_zero_shot"), ("ei", "transductive")):
            joined = next(j for j in self.joined if (j["projection"]["label_level"], j["projection"]["panel"]) == (level, panel))
            training = self.source.evaluator.SOURCE_SESSIONS
            if panel == "inductive_zero_shot":
                training = training - self.source.evaluator.SB028_SESSIONS
            # Packet formation only; authentic_candidate is the existing API's
            # declaration, not authentication of these generated checkpoints.
            with patch.object(self.source.evaluator, "evaluate", side_effect=AssertionError("readout fitting forbidden")):
                packet = native.readout_packet(joined, self.checkpoint(joined), "population_context", sorted(training), "1" * 64)
            self.assertEqual(packet["class_balance"], "resample")
            self.assertEqual(packet["splits"], joined["projection"]["splits"])
            self.assertFalse(packet["provenance"]["historical_experiment_order_verified"])
            self.assertEqual(packet["provenance"]["transductive_source_route_unresolved"], panel == "transductive")
            self.assertEqual(set(packet["representation_training_sessions"]), training)

    def test_invalid_panel_wrong_checkpoint_order_and_exposure_leakage_refuse_handoff(self):
        bad = next(j for j in self.joined if j["projection"]["label_level"] == "ei"
                   and j["projection"]["panel"] == "inductive_zero_shot")
        training = sorted(self.source.evaluator.SOURCE_SESSIONS - self.source.evaluator.SB028_SESSIONS)
        with self.assertRaisesRegex(ValueError, "CV crosses"):
            native.readout_packet(bad, self.checkpoint(bad), "population_context", training, "1" * 64)
        good = next(j for j in self.joined if j["projection"]["label_level"] == "subclass"
                    and j["projection"]["panel"] == "inductive_zero_shot")
        checkpoint = self.checkpoint(good)
        checkpoint[0]["ids"].reverse()
        with self.assertRaises(ValueError):
            native.readout_packet(good, checkpoint, "population_context", training, "1" * 64)
        with self.assertRaises(ValueError):
            native.readout_packet(good, self.checkpoint(good), "population_context",
                                  sorted(self.source.evaluator.SOURCE_SESSIONS), "1" * 64)

    def test_completed_reader_binds_full_manifest_and_restores_native_addresses(self):
        # Replace only private JSON/profile admission with generated boundary
        # objects to avoid writing large artificial receipts. Native reads are
        # real, exact-hash generated files. This is NOT authentic source custody.
        manifest = {"schema": native.SCHEMA, "source_profile_sha256": native.PROFILE_SHA256,
                    "order_adoption_sha256": native.ORDER_ADOPTION_SHA256,
                    "split_archive_sha256": self.source.splits.ARCHIVE_SHA256,
                    "metadata_archive_sha256": self.definition["metadata_archive"]["sha256"],
                    "dependencies": self.source.pins, "order_policy": native.ORDER_POLICY,
                    "sessions": self.sessions, "neurons": self.neurons, "assets": list(self.assets.values())}
        completion = {"schema": "nuclr-native-preparation-complete-v1", "manifest_sha256": native.digest(manifest),
                      "joined_panels_sha256": native.digest(self.joined), "scientific_qualification": False}
        documents = {"native-manifest.json": manifest, "joined-panels.json": self.joined, "COMPLETE.json": completion}
        def generated_json(path, *_):
            return documents[Path(path).name]
        with patch.object(native, "read_json", generated_json), patch.object(native, "profile", return_value=self.generated_profile):
            reader = native.NativeInputs(self.root)
            ids = ["sb025_20191004_u10", "sb025_20191004_u2", "sb028_20191107_u0"]
            self.assertEqual(reader.native_addresses(ids), [("sb025_20191004", 10), ("sb025_20191004", 2), ("sb028_20191107", 0)])
            result = reader.read_block(self.sessions[0]["session_id"], self.sessions[0]["experiments"][0]["experiment_id"], 0, 1, normalized=False)
            self.assertEqual(result["activity"][0, 10], 11)
            with self.assertRaises(ValueError):
                reader.native_addresses(ids + ids[:1])
            documents["COMPLETE.json"] = dict(completion, manifest_sha256="0" * 64)
            with self.assertRaises(ValueError):
                native.NativeInputs(self.root)


def tearDownModule():
    print(json.dumps({"generated_fixture_file_bytes": GENERATED_FILE_BYTES,
                      "allocation_bytes": 4 * 1024 * 1024, "authentic_arrays_or_model_execution": False}))


if __name__ == "__main__":
    unittest.main()
if __name__ == "__main__":
    unittest.main()
