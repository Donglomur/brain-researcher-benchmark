"""Inspect the installed Morse production source only; never import task code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

MANIFEST = {"path": "SOURCE_MANIFEST.json", "bytes": 6283,
            "sha256": "987410573a680c23a6e21157b96bc829c1480a5da8c0d8eb7620eee895e16daa"}
READ_LIMIT = 410043
SECONDS = 10
OUTPUT_LIMIT = 16384

def require(test, message):
    if not test:
        raise ValueError(message)


def decode(body):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, "duplicate source/configuration key")
            out[k] = v
        return out
    def bad(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


class Capture:
    def __init__(self, maximum, end):
        self.maximum, self.end, self.used = maximum, end, 0

    def read(self, root, pin):
        require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "source pin schema")
        require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 2**20, "ordinary source member bound")
        require(type(pin["sha256"]) is str and len(pin["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in pin["sha256"]), "source digest")
        root_value = root
        root, rel = Path(root), Path(pin["path"])
        require(type(root_value) is str and not root_value.startswith("//")
                and str(root) == root_value and ".." not in root.parts
                and root.is_absolute() and not rel.is_absolute() and str(rel) == pin["path"]
                and ".." not in rel.parts and "\\" not in pin["path"], "source path")
        path = root / rel
        for p in (path.parent, *path.parent.parents):
            require(stat.S_ISDIR(p.lstat().st_mode) and not p.is_symlink(), "ordinary source parents")
        require(time.monotonic() < self.end and self.used + pin["bytes"] + 1 <= self.maximum,
                "prospective source deadline/read grant")
        self.used += pin["bytes"] + 1
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"],
                "ordinary pinned source")
        fd, first, secondary, body = None, None, [], None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            opened = os.fstat(fd)
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            require(stamp(opened) == stamp(before), "source changed before open")
            pieces, total = [], 0
            while total <= pin["bytes"]:
                require(time.monotonic() < self.end, "source read deadline")
                part = os.read(fd, min(65536, pin["bytes"] + 1 - total))
                if not part:
                    break
                total += len(part)
                pieces.append(part)
            body = b"".join(pieces)
            require(stamp(opened) == stamp(os.fstat(fd)) == stamp(path.lstat())
                    and len(body) == pin["bytes"]
                    and hashlib.sha256(body).hexdigest() == pin["sha256"], "source capture differs")
        except BaseException as exc:
            first = exc
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as exc:
                    if first is None:
                        first = exc
                    else:
                        secondary.append(exc)
        if first is not None:
            first.morse_secondary_errors = tuple(getattr(first, "morse_secondary_errors", ())) + tuple(secondary)
            for later in secondary:
                first.add_note("Secondary source close failure: " + repr(later))
            raise first
        require(time.monotonic() < self.end, "source completion deadline")
        return body


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def namespace(root, expected):
    """List only this ten-file component; retain primary and close failures."""
    stream = os.scandir(root)
    first = None
    result = {}
    try:
        for entry in stream:
            require(len(result) < 32, "bounded component namespace")
            s = entry.stat(follow_symlinks=False)
            require(entry.name in expected and stat.S_ISREG(s.st_mode)
                    and s.st_nlink == 1 and stat.S_IMODE(s.st_mode) == 0o644,
                    "only exact ordinary component sources")
            result[entry.name] = stamp(s)
        require(set(result) == expected, "complete component namespace")
    except BaseException as error:
        first = error
    try:
        stream.close()
    except BaseException as later:
        if first is None:
            first = later
        else:
            first.morse_secondary_errors = tuple(getattr(first, "morse_secondary_errors", ())) + (later,)
            first.add_note("Secondary component listing close failure: " + repr(later))
    if first is not None:
        raise first
    return result


def main(argv=None):
    require(sys.version_info >= (3, 11), "Python 3.11 or newer required")
    arguments = sys.argv[1:] if argv is None else argv
    require(type(arguments) is list and arguments == ["--inspect"], "exact source-inspection argv")
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--inspect", required=True, action="store_true")
    parser.parse_args(arguments)
    here = Path(__file__).absolute().parent
    legacy = here.parent
    require(here.name == "production-wiring-v3" and legacy.name == "neural-002",
            "installed task-local source layout required")
    for root in (here, legacy):
        require(root.is_absolute() and not str(root).startswith("//") and ".." not in root.parts,
                "canonical installed source roots")
        for parent in (root, *root.parents):
            require(stat.S_ISDIR(parent.lstat().st_mode) and not parent.is_symlink(),
                    "ordinary installed source ancestry")
    script = Path(__file__).absolute()
    require(script.name == "inspect_source.py" and script.parent == here,
            "exact installed inspection script path")
    script_stat = script.lstat()
    require(stat.S_ISREG(script_stat.st_mode) and script_stat.st_nlink == 1
            and stat.S_IMODE(script_stat.st_mode) == 0o644, "ordinary installed inspector")
    interpreter = Path(sys.executable)
    require(interpreter.is_absolute() and str(interpreter) == sys.executable
            and not sys.executable.startswith("//") and ".." not in interpreter.parts
            and stat.S_ISREG(interpreter.stat().st_mode) and os.access(interpreter, os.X_OK),
            "actual absolute executable interpreter path")
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        # The initial interpreter/site startup was not isolated by this wrapper.
        # Replace this PID once before any selected source-body capture. The
        # external owner's original lifetime/streams continue across exec.
        os.execv(sys.executable, [sys.executable, "-I", "-S", "-B", str(script), "--inspect"])
        raise RuntimeError("same-PID isolated interpreter exec unexpectedly returned")
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,
            "actual isolated source-capture startup required")
    start_directory = stamp(here.lstat())
    require(stat.S_IMODE(here.lstat().st_mode) == 0o755, "exact installed directory mode")
    reader = Capture(READ_LIMIT, time.monotonic() + SECONDS)
    records = {}
    def take(root, pin):
        path = root / pin["path"]
        before = stamp(path.lstat())
        require(stat.S_IMODE(before[2]) == 0o644, "exact ordinary source permission")
        raw = reader.read(str(root), pin)
        require(before == stamp(path.lstat()), "captured source identity stable")
        records[str(path)] = before
        return raw
    manifest = decode(take(here, MANIFEST))
    require(set(manifest) == {"schema", "files", "legacy_files", "module_map", "scope"}
            and manifest["schema"] == "morse-production-source-v1", "exact source manifest schema")
    require(len(manifest["files"]) == 8 and len(manifest["legacy_files"]) == 24,
            "accepted eight local and24 legacy source members")
    expected = {r["path"] for r in manifest["files"]} | {"SOURCE_MANIFEST.json", "inspect_source.py"}
    require(len(expected) == 10 and all(Path(n).name == n for n in expected), "complete flat10 component")
    before_namespace = namespace(here, expected)
    bodies = {}
    for area, root, rows in (("local", here, manifest["files"]), ("legacy", legacy, manifest["legacy_files"])):
        for row in rows:
            key = area + ":" + row["path"]
            require(key not in bodies, "unique source member")
            take(root, row)
            bodies[key] = str(root / row["path"])
    require(type(manifest["module_map"]) is dict and manifest["module_map"], "closed task module mapping")
    for name, key in manifest["module_map"].items():
        require(name.isidentifier() and name not in sys.modules and key in bodies,
                "reserved source namespace already imported or missing")
    require(len(records) == 33 and len({(v[0], v[1]) for v in records.values()}) == 33,
            "33 distinct captured ordinary sources including manifest")
    require(all(stamp(Path(p).lstat()) == old for p, old in records.items()), "all source identities unchanged")
    require(namespace(here, expected) == before_namespace and stamp(here.lstat()) == start_directory,
            "component namespace unchanged")
    require(reader.used == READ_LIMIT and time.monotonic() < reader.end, "exact read grant and deadline")
    result = {"schema": "morse-installed-production-source-inspection-v1", "task_id": "NEURAL-002",
              "status": "source_only", "component_files": 10, "accepted_production_files": 9,
              "legacy_dependencies": 24, "captured_nonmanifest_sources": len(bodies),
              "source_read_reserved": reader.used, "source_manifest": MANIFEST, "scope": manifest["scope"],
              "task_modules_imported": False, "scientific_inputs_opened": False,
              "native_execution_performed": False, "scientific_execution": False,
              "scientific_qualification": False, "benchmark_count_delta": 0,
              "wrapper_authenticity": "trusted installation/commit; not self-certified"}
    raw = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(raw) <= OUTPUT_LIMIT, "bounded source inspection result")
    count = sys.stdout.buffer.write(raw)
    require(type(count) is int and count == len(raw), "complete source inspection terminal write")
    sys.stdout.buffer.flush()
    require(time.monotonic() < reader.end, "source inspection terminal deadline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
