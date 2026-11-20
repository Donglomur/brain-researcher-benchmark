"""Focused real-validator controls for the one retained retinal source adoption.

This suite exercises the maintained retinal row helper and context validators.
It does not replace whole-registry coverage or publication's two complete binder
passes. All fixtures are public source metadata; no model or data payload runs.
Use Python 3.11 and -B. An explicit ARTIFACT_DIR is strict; ordinary discovery
uses a bounded owned temporary directory when it is absent. unittest's reporter
is the authoritative test count/result; artifacts are supplementary fixtures.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest


TASK = "PAPER-paper-method-002"
HOME = "benchmarks/paper/" + TASK
POLICY = HOME + "/policies/retinal-paired-correction-v1"
COMPONENT = HOME + "/implementations/retinal-paired-episode-v1"
SNAPSHOT = "docs/provenance/registrations/paper-pre-outcomes-v1.json"
SCOPE = "docs/provenance/paper-outcome-scope-decisions.v1.json"
SOURCE_INPUT_ROOT = Path(__file__).resolve().parents[1]
PRE_OUTCOMES_ROW_PACKET = None
CURRENT_ROW_PACKET = None
MAX_SOURCE_READ = 16 * 1024 * 1024
FRAMEWORK_READ_RESERVE = 2 * 1024 * 1024
MAX_FIXTURE_WRITE = 1024 * 1024
MAX_FILES = 32
SNAPSHOT_PIN = (2254453, "075806a9d1ab59c6d406c666849e80bb5e0c1495d8850ba469ad15205db7e8e6")
ROW_PACKET_PIN = (6728, "7e940b73ee839dc62d95d059ff6ee70277d2a304e7bfbfadddca91bc9e1fa69a")
CURRENT_PACKET_PIN = (8518, "9d72bd189e2820d316b247ec0ebfdbf5a928751c90e961f943068f8d54a92600")
SCOPE_PIN = (523962, "e71fe3e869e8f48ffcf18d8e685b86f30027e8eb1dde8ce676ac1948c1943aea")
PRE_OUTCOMES_TASK_PIN = (29018, "c1d4323aef117ba459d53704ea9fd647dbc47057df8603a44038ac5245accfd8")
PRE_IMPROVEMENT_TASK_PIN = (28093, "d8f437bfee21b13dca7844816bf8cb4b6793460de96ce0f3871c3fd818e52c89")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate metadata key")
            result[key] = value
        return result
    def constant(_value):
        raise ValueError("nonfinite metadata constant")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def source_stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def checked_external_output(path, source_roots):
    """No write occurs here; reject source aliases, descendants and ancestors."""
    require(type(path) in (str, Path) or isinstance(path, Path), "artifact path required")
    value = Path(path)
    require(value.is_absolute() and len(str(value)) <= 4096 and
            ".." not in value.parts and len(value.parts) <= 64, "bounded absolute artifact path required")
    resolved = value.resolve(strict=False)
    for source in source_roots:
        source = Path(source).resolve(strict=True)
        require(source.is_dir(), "source root is not a directory")
        require(resolved != source and resolved not in source.parents and source not in resolved.parents,
                "artifact/source overlap")
    current = Path(value.anchor)
    for part in value.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        require(not stat.S_ISLNK(info.st_mode), "artifact symlink component")
    require(value.parent.is_dir(), "artifact parent must already exist")
    return resolved


class BoundedSources:
    """Read only named regular metadata/source members, with stable-open checks."""
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.read_bytes = 0
        self.cache = {}

    def read(self, relative, pin=None):
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts, "relative named source required")
        return self.read_absolute(self.root / path, pin)

    def read_absolute(self, path, pin=None):
        path = Path(path)
        require(not path.is_symlink() and all(not parent.is_symlink() for parent in path.parents),
                "source aliases forbidden")
        if path in self.cache:
            body, old = self.cache[path]
            require(source_stamp(path.lstat()) == old, "cached source changed")
        else:
            before = path.lstat()
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                    "ordinary single-link source required")
            require(before.st_size <= 4 * 1024 * 1024 and
                    self.read_bytes + before.st_size <= MAX_SOURCE_READ, "bounded source reads exceeded")
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                require(source_stamp(os.fstat(descriptor)) == source_stamp(before), "source open changed")
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    body = stream.read(before.st_size + 1)
                require(len(body) == before.st_size and
                        source_stamp(os.fstat(descriptor)) == source_stamp(before) == source_stamp(path.lstat()),
                        "source changed during read")
            finally:
                os.close(descriptor)
            self.read_bytes += len(body)
            self.cache[path] = body, source_stamp(before)
        if pin is not None:
            require((len(body), hashlib.sha256(body).hexdigest()) == tuple(pin), "source pin mismatch")
        return body


class BoundedFixtures:
    """Only explicit files below a fresh disjoint output root may be written."""
    def __init__(self, root):
        self.root = root
        self.write_bytes = 0
        self.files = set()

    def write(self, relative, body):
        require(type(body) is bytes and len(body) <= 512 * 1024, "bounded fixture bytes required")
        rel = Path(relative)
        require(not rel.is_absolute() and ".." not in rel.parts and len(rel.parts) <= 12,
                "bounded relative fixture path required")
        path = self.root / rel
        require(self.root in path.resolve(strict=False).parents, "fixture escapes artifact root")
        require(self.write_bytes + len(body) <= MAX_FIXTURE_WRITE, "cumulative fixture writes exceeded")
        require(relative in self.files or len(self.files) < MAX_FILES, "fixture file count exceeded")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        for ancestor in (path.parent, *path.parent.parents):
            if ancestor == self.root:
                break
            require(not ancestor.is_symlink(), "fixture directory alias")
        if path.exists():
            require(stat.S_ISREG(path.lstat().st_mode) and path.lstat().st_nlink == 1,
                    "fixture is not an ordinary file")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
        self.write_bytes += len(body)
        self.files.add(relative)


def load_source(path, body, name):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "source module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def exact_row(rows):
    require(type(rows) is list, "registry rows required")
    selected = [row for row in rows if type(row) is dict and row.get("id") == TASK]
    require(len(selected) == 1, "exactly one retinal row required")
    return copy.deepcopy(selected[0])


class RetinalPairedAdoptionTests(unittest.TestCase):
    """Six focused methods for adoption and catalog display; no scientific execution."""

    @classmethod
    def setUpClass(cls):
        require(sys.version_info[:2] == (3, 11), "selected Python 3.11 required")
        require(sys.dont_write_bytecode, "disable bytecode writes with -B")
        root = Path(SOURCE_INPUT_ROOT).absolute()
        require(root.is_dir() and not root.is_symlink() and
                all(not parent.is_symlink() for parent in root.parents),
                "real trusted source input root required")
        cls.source_root = root
        cls.protected = tuple([root, Path(__file__).resolve().parent] +
                              [Path(path).resolve(strict=True).parent for path in
                               (PRE_OUTCOMES_ROW_PACKET, CURRENT_ROW_PACKET) if path is not None])
        artifact_value = os.environ.get("ARTIFACT_DIR")
        if artifact_value is None:
            # The public catalog does not set ARTIFACT_DIR. Create one owned
            # temporary parent, register cleanup immediately, then validate a
            # fresh child through the same source/output boundary below.
            base = Path(tempfile.gettempdir()).resolve(strict=True)
            require(all(source != base and source not in base.parents for source in cls.protected),
                    "temporary parent must be outside protected source roots")
            temporary = tempfile.TemporaryDirectory(prefix="retinal-adoption-", dir=base)
            cls.addClassCleanup(temporary.cleanup)
            artifact_value = str(Path(temporary.name).resolve(strict=True) / "artifacts")
        cls.output = checked_external_output(artifact_value, cls.protected)
        require(not cls.output.exists(), "ARTIFACT_DIR must be fresh")
        cls.output.mkdir(mode=0o700)
        cls.fixture_root = cls.output / "retinal-metadata-fixture"
        cls.fixture_root.mkdir(mode=0o700)
        cls.fixtures = BoundedFixtures(cls.fixture_root)
        cls.sources = BoundedSources(root)
        relative = "scripts/maintenance/bind_paper_outcomes.py"
        cls.binder = load_source(root / relative, cls.sources.read(relative),
                                 "_retinal_paired_adoption_control_binder")
        cls.binding = cls.binder.binding
        cls.adoption = cls.binding.retinal_paired_module()
        cls.fixed_bodies = {}
        pins = [cls.adoption.DESCRIPTOR_PIN]
        pins.extend(cls.adoption.ORIGINAL_PINS.values())
        pins.extend(cls.adoption.ACTIVE_PINS.values())
        pins.extend(cls.adoption.COMPONENT_PINS.values())
        for pin in pins:
            body = cls.sources.read(pin["path"], (pin["bytes"], pin["sha256"]))
            cls.fixed_bodies[pin["path"]] = body
        cls.scope_document = strict_json(cls.sources.read(SCOPE, SCOPE_PIN))
        for relative, pin in ((HOME + "/historical/task.pre-outcomes.v1.json", PRE_OUTCOMES_TASK_PIN),
                              (HOME + "/historical/task.pre-improvement.v1.json", PRE_IMPROVEMENT_TASK_PIN)):
            cls.fixed_bodies[relative] = cls.sources.read(relative, pin)
        require(sum(map(len, cls.fixed_bodies.values())) + 2 * 65536 < MAX_FIXTURE_WRITE,
                "fixture preparation leaves insufficient bounded mutation capacity")
        for relative, body in cls.fixed_bodies.items():
            cls.fixtures.write(relative, body)
        reader = cls.binder.checker.Reader(cls.fixture_root)
        read_pin = lambda pin, label: cls.binder.read_pinned(reader, pin, label)
        cls.handle = cls.adoption.authenticate(read_pin)
        cls.retained_task = cls.handle.retained_task
        cls.retained_task_body = cls.binding.encode(cls.retained_task)
        cls.fixtures.write(HOME + "/task.json", cls.retained_task_body)
        if PRE_OUTCOMES_ROW_PACKET is None:
            snapshot = strict_json(cls.sources.read(SNAPSHOT, SNAPSHOT_PIN))
            cls.previous_row = exact_row(snapshot["tasks"])
        else:
            packet = strict_json(cls.sources.read_absolute(PRE_OUTCOMES_ROW_PACKET, ROW_PACKET_PIN))
            require(packet["snapshot"]["sha256"] == SNAPSHOT_PIN[1] and
                    packet["snapshot"]["bytes"] == SNAPSHOT_PIN[0], "historical extraction authority changed")
            cls.previous_row = copy.deepcopy(packet["row"])
        if CURRENT_ROW_PACKET is None:
            current = strict_json(cls.sources.read("benchmarks/registry.json"))
            cls.retained_row = exact_row(current["tasks"])
        else:
            packet = strict_json(cls.sources.read_absolute(CURRENT_ROW_PACKET, CURRENT_PACKET_PIN))
            cls.retained_row = copy.deepcopy(packet["task_row"])
        require(cls.previous_row["id"] == cls.retained_row["id"] == TASK, "exact retained row identity required")
        # Public CI runs after publication. Undo only this exact selected view to
        # exercise initial adoption again; historical row/contract fields stay intact.
        field = cls.adoption.SELECTION_FIELD
        if field in cls.retained_row["paper_outcomes"]:
            require(cls.retained_row["paper_outcomes"][field] == cls.handle.descriptor_pin and
                    cls.retained_row["specification"] == cls.handle.current_task_pin,
                    "current adopted selector differs from fixed source")
            del cls.retained_row["paper_outcomes"][field]
            cls.retained_row["specification"] = cls.handle.retained_task_pin
        require(cls.retained_row["specification"] == cls.handle.retained_task_pin,
                "retained current row does not match embedded raw task")
        cls.scope_pin = {"path": SCOPE, "bytes": SCOPE_PIN[0], "sha256": SCOPE_PIN[1]}
        cls.maintained_read_bytes = reader.bytes_read

    @classmethod
    def tearDownClass(cls):
        # Ordinary unittest output is authoritative. This one bounded diagnostic
        # line documents costs without introducing another reporter protocol.
        print("Retinal adoption controls: source_read_bytes=%d maintained_read_bytes=%d "
              "framework_read_reserve_bytes=%d fixture_write_bytes=%d; "
              "row-scope only, scientific qualification remains false" %
              (cls.sources.read_bytes, cls.maintained_read_bytes, FRAMEWORK_READ_RESERVE,
               cls.fixtures.write_bytes), file=sys.stderr)

    def previous(self):
        previous = self.binding.PreviousRows(((TASK, copy.deepcopy(self.previous_row)),))
        previous.scope_decisions = self.binding.scope_decisions(copy.deepcopy(self.scope_document))
        previous.scope_pin = copy.deepcopy(self.scope_pin)
        return previous

    def planned(self, row=None, current=None, previous=None, *, adopt=True):
        reader = self.binder.checker.Reader(self.fixture_root)
        read_pin = lambda pin, label: self.binder.read_pinned(reader, pin, label)
        try:
            return self.binder.retinal_row_outputs(
                copy.deepcopy(self.retained_row if row is None else row),
                copy.deepcopy(self.retained_task if current is None else current),
                self.previous() if previous is None else previous, read_pin, adopt=adopt)
        finally:
            type(self).maintained_read_bytes += reader.bytes_read
            if type(self).maintained_read_bytes + self.sources.read_bytes + FRAMEWORK_READ_RESERVE > MAX_SOURCE_READ:
                # A budget fault must not masquerade as an expected ValueError
                # refusal in a negative contract test.
                raise RuntimeError("campaign named metadata read budget exceeded")

    def test_explicit_adoption_then_default_row_path_is_byte_stable(self):
        self.assertIsNone(self.planned(adopt=False))
        selected = self.planned()
        self.assertEqual(set(selected["outputs"]), {HOME + "/task.json"})
        self.assertEqual(selected["row"]["specification"], self.handle.current_task_pin)
        self.assertEqual(selected["row"]["paper_outcomes"][self.adoption.SELECTION_FIELD],
                         self.handle.descriptor_pin)
        for field in self.binding.PRESERVED_ROW_FIELDS:
            self.assertEqual(self.binding.encode(selected["row"].get(field)),
                             self.binding.encode(self.previous_row.get(field)), field)
        for relative, body in selected["outputs"].items():
            self.fixtures.write(relative, body)
        try:
            current_reader = self.binder.checker.Reader(self.fixture_root)
            current = self.binder.read_pinned(current_reader, selected["row"]["specification"],
                                              "Default-pass current retinal task")
            type(self).maintained_read_bytes += current_reader.bytes_read
            repeated = self.planned(selected["row"], current, adopt=False)
            self.assertEqual(repeated["outputs"], selected["outputs"])
            self.assertEqual(self.binding.encode(repeated["row"]), self.binding.encode(selected["row"]))
            for role, pin in self.adoption.ORIGINAL_PINS.items():
                body = (self.fixture_root / pin["path"]).read_bytes()
                type(self).maintained_read_bytes += len(body)
                self.assertEqual(body, self.fixed_bodies[pin["path"]], role)
            reader = self.binder.checker.Reader(self.fixture_root)
            self.binder.checker.paper_revision_members(reader, selected["context"]["previous_row"],
                                                       selected["context"]["previous_document"])
            type(self).maintained_read_bytes += reader.bytes_read
        finally:
            self.fixtures.write(HOME + "/task.json", self.retained_task_body)

    def test_wrong_task_descriptor_and_changed_contract_bytes_are_refused(self):
        wrong = copy.deepcopy(self.retained_row)
        wrong["id"] = "PAPER-not-the-retinal-task"
        with self.assertRaises(ValueError):
            self.planned(row=wrong)
        selected = self.planned()
        wrong = copy.deepcopy(selected["row"])
        wrong["paper_outcomes"][self.adoption.SELECTION_FIELD]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.planned(wrong, selected["task"], adopt=False)
        for path in (self.adoption.ADOPTION_PATH, self.adoption.ACTIVE_PINS["improvement"]["path"]):
            with self.subTest(changed_member=path):
                before = self.fixed_bodies[path]
                # Whitespace preserves decoded JSON, so acceptance would prove a
                # raw-identity check had been bypassed rather than a schema error.
                self.fixtures.write(path, before + b" ")
                try:
                    with self.assertRaises(ValueError):
                        self.planned()
                finally:
                    self.fixtures.write(path, before)

    def test_wrong_current_task_and_historical_row_mutations_are_refused(self):
        wrong = copy.deepcopy(self.retained_task)
        wrong["title"] = "generated wrong current task"
        with self.assertRaises(ValueError):
            self.planned(current=wrong)
        selected = self.planned()
        wrong = copy.deepcopy(selected["task"])
        wrong["retinal_paired_correction"]["scientific_status"] = "QUALIFIED"
        with self.assertRaises(ValueError):
            self.planned(selected["row"], wrong, adopt=False)
        for field, replacement in (("scientific_readiness", "improvement_ready"),
                                   ("submission_readiness", "ready"),
                                   ("title", "generated altered historical title")):
            with self.subTest(historical_field=field):
                previous = self.previous()
                previous[TASK][field] = replacement
                with self.assertRaises(ValueError):
                    self.planned(previous=previous)
        previous = self.previous()
        previous[TASK]["specification"]["sha256"] = "1" * 64
        with self.assertRaises(ValueError):
            self.planned(previous=previous)

    def test_active_contract_digests_bind_new_task_without_scientific_promotion(self):
        selected = self.planned()
        context = selected["context"]
        outcomes = context["outcomes"]
        reproduction, improvement = context["reproduction_contract"], context["improvement_contract"]
        maintained = self.binding.engine(reproduction)
        self.assertEqual(maintained.outcomes_validate(outcomes, reproduction, improvement), [])
        self.assertEqual(outcomes["contracts"]["reproduction"], maintained.contract_digest(reproduction))
        self.assertEqual(outcomes["contracts"]["improvement"], maintained.contract_digest(improvement))
        body = selected["outputs"][HOME + "/task.json"]
        self.assertEqual(outcomes["original_task_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(outcomes["original_task_sha256"], self.handle.current_task_pin["sha256"])
        self.assertEqual(context["retained_improvement_contract_pin"], self.adoption.ORIGINAL_PINS["improvement"])
        self.assertEqual(selected["row"]["scientific_readiness"], self.retained_row["scientific_readiness"])
        self.assertEqual(selected["row"]["submission_readiness"], "not_qualified_by_binding")
        self.assertEqual(selected["task"]["retinal_paired_correction"]["scientific_status"], "UNQUALIFIED")
        self.assertFalse(any(context["summary"]["paired_metadata_admitted"].values()))
        for cell in context["summary"]["cells"]:
            self.assertEqual(cell["scientific_outcome"], "unknown")
            self.assertIsNone(cell["receipt"])
        for pair in outcomes["pairing"].values():
            self.assertEqual(pair["status"], "unresolved")
            self.assertIsNone(pair["protocol"])

    def test_catalog_retinal_source_adoption_and_display(self):
        # The actual row helper authenticates historical/current source and runs
        # the unchanged context engines. This is not whole-registry validation.
        selected = self.planned()
        context = selected["context"]
        relative = "src/neurobench/catalog.py"
        catalog = load_source(self.source_root / relative, self.sources.read(relative),
                              "_retinal_paired_catalog_control")
        before_row = self.binding.encode(selected["row"])
        public = self.binding.public_summary(selected["row"], context)
        self.assertEqual(catalog.retinal_paired_source_ids(self.binding, {TASK: selected["row"]}), {TASK})
        self.assertEqual(catalog.retinal_paired_source_ids(self.binding, {TASK: self.retained_row}), set())
        wrong = copy.deepcopy(selected["row"])
        wrong["paper_outcomes"][self.adoption.SELECTION_FIELD]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            catalog.retinal_paired_source_ids(self.binding, {TASK: wrong})
        wrong = copy.deepcopy(selected["row"])
        wrong["id"] = "PAPER-not-the-retinal-task"
        with self.assertRaises(ValueError):
            catalog.retinal_paired_source_ids(self.binding, {wrong["id"]: wrong})
        self.assertEqual(public["reproduction_contract"], self.adoption.ACTIVE_PINS["reproduction"])
        self.assertEqual(public["outcomes"], self.adoption.ACTIVE_PINS["outcomes"])
        self.assertEqual(public["improvement_contract"], self.adoption.ACTIVE_PINS["improvement"])
        self.assertEqual(public["retained_improvement_contract"], self.adoption.ORIGINAL_PINS["improvement"])
        for field in ("reproduction_contract", "outcomes", "previous_specification"):
            self.assertEqual(selected["row"]["paper_outcomes"][field], self.retained_row["paper_outcomes"][field])
        self.assertEqual(self.binding.encode(selected["row"]), before_row)
        self.assertEqual(context["previous_row"], self.previous_row)
        self.assertEqual(context["retained_improvement_contract"], self.handle.original_documents["improvement"])
        bad_context = copy.deepcopy(context)
        bad_context["primary_policy_provenance"]["active_contracts"]["outcomes"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.binding.public_summary(selected["row"], bad_context)

        row = {"id": TASK, "specification": selected["row"]["specification"],
               "paper_outcomes": public, "registry": None, "runtime_manifest": None}
        source_catalog = {"registry": {"path": "benchmarks/registry.json"},
                          "recorded_evidence": {"reports": []}, "implementations": [],
                          "tasks": [row], "registry_chain": [], "shared_contracts": [],
                          "components": [], "unmapped_runtime_sources": []}
        links = set(catalog.source_links(source_catalog))
        expected_pins = [self.adoption.DESCRIPTOR_PIN, self.handle.current_task_pin]
        expected_pins.extend(self.adoption.ACTIVE_PINS.values())
        expected_pins.extend(self.adoption.ORIGINAL_PINS.values())
        expected_pins.extend(self.adoption.COMPONENT_PINS.values())
        self.assertTrue({pin["path"] for pin in expected_pins} <= links)
        section = catalog.render_retinal_paired_policy(row, HOME)
        for field, label in (("improvement", "Active within-cell improvement contract"),
                             ("reproduction", "Active historical-reproduction contract"),
                             ("outcomes", "Active unresolved outcome binding")):
            self.assertIn(catalog.markdown_link(label, self.adoption.ACTIVE_PINS[field]["path"], HOME), section)
        for field, label in (("improvement", "Retained historical improvement contract"),
                             ("reproduction", "Retained historical reproduction contract"),
                             ("outcomes", "Retained historical outcome binding")):
            self.assertIn(catalog.markdown_link(label, self.adoption.ORIGINAL_PINS[field]["path"], HOME), section)
        self.assertIn("UNQUALIFIED", section)
        self.assertIn("147 merged recording sites", section)
        self.assertIn("one biological cell, 20161028_1", section)
        self.assertIn("repeated stimulus sequences", section)
        self.assertIn("paired difference", section)
        self.assertIn("no participant result or admitted paired protocol", section)
        self.assertNotIn("35-bin panel", section)
        aggregate_row = dict(row, track="paper", paper_improvement={
            "disposition": context["retained_improvement_contract"]["disposition"]})
        aggregate = {"tasks": [aggregate_row],
                     "paper_improvement_counts": catalog.improvement_counts([aggregate_row]),
                     "paper_outcome_counts": catalog.paper_outcome_counts([aggregate_row])}
        count_text = catalog.paper_count_text(aggregate)
        self.assertIn("retinal source correction", count_text)
        self.assertNotIn("For the revised SMC task", count_text)
        self.assertIn("unknown and UNQUALIFIED", count_text)
        self.assertEqual(public["candidate_interface"]["paired_protocol"], None)
        self.assertIs(public["candidate_interface"]["execution_qualified"], False)
        self.assertIsNone(public["author_reproduction_routes"])
        self.assertEqual(public["scientific_outcomes"], {"reproduction": "unknown", "improvement": "unknown"})
        for cell in public["cells"]:
            self.assertEqual(cell["scientific_outcome"], "unknown")
            self.assertIsNone(cell["receipt"])
        self.assertLessEqual(self.fixtures.write_bytes, 512 * 1024)
        self.assertLessEqual(type(self).maintained_read_bytes + self.sources.read_bytes + FRAMEWORK_READ_RESERVE,
                             MAX_SOURCE_READ)

    def test_artifact_root_rejects_source_ancestors_descendants_and_aliases(self):
        source = self.source_root
        for forbidden in (source, source.parent, source / "generated-forbidden-output"):
            with self.subTest(path_kind=forbidden.name):
                with self.assertRaises(ValueError):
                    checked_external_output(forbidden, self.protected)
        alias = self.output / "temporary-source-alias"
        link_bytes = len(os.fsencode(source))
        require(link_bytes <= 4096 and self.fixtures.write_bytes + link_bytes <= MAX_FIXTURE_WRITE,
                "bounded generated alias write required")
        self.fixtures.write_bytes += link_bytes
        alias.symlink_to(source, target_is_directory=True)
        try:
            with self.assertRaises(ValueError):
                checked_external_output(alias / "generated-forbidden-output", self.protected)
        finally:
            alias.unlink()
        self.assertEqual(checked_external_output(self.output, self.protected), self.output)


def main():
    global SOURCE_INPUT_ROOT, PRE_OUTCOMES_ROW_PACKET, CURRENT_ROW_PACKET
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--source-input-root", type=Path, default=SOURCE_INPUT_ROOT)
    parser.add_argument("--pre-outcomes-row-packet", type=Path)
    parser.add_argument("--current-row-packet", type=Path)
    args, remaining = parser.parse_known_args()
    SOURCE_INPUT_ROOT = args.source_input_root
    PRE_OUTCOMES_ROW_PACKET = args.pre_outcomes_row_packet
    CURRENT_ROW_PACKET = args.current_row_packet
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)


if __name__ == "__main__":
    main()

