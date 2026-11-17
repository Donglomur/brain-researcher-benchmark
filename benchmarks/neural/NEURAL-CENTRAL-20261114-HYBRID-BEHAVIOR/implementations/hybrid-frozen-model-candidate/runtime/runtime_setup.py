"""Offline fresh-venv orchestration and complete installed-file identity checks.

Only stdlib is imported. This file performs no work at module import and has no
CLI. The parent owns the immutable plan, I/O meter, stage receipts and process
group. It must not call this source before independent selection.
"""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import zipfile
from email.parser import BytesParser


def need(ok, message):
    if not ok:
        raise ValueError(message)


def packed(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _ordinary_tree(root):
    need(root.is_absolute() and ".." not in root.parts, "absolute owned root")
    need(not any(p.is_symlink() for p in (root, *root.parents)), "no linked root ancestor")


def validate_installed(venv, expected, base_spec, limits, read_file, write_file):
    """Hash every regular venv file; validate all distribution RECORD entries.

    Only exactly named contained Python executable aliases may be symlinks. A
    RECORD entry may use ../ to reach venv/bin, but may never escape the venv.
    Hashless entries are accepted only for that distribution's RECORD itself.
    """
    venv = Path(venv)
    _ordinary_tree(venv)
    cap = limits["installed_bytes"]
    expected = {normalized(k): v for k, v in expected.items()}
    need(len(expected) == 12, "exact twelve-package runtime required")
    files, aliases, total = {}, {}, 0
    for directory, dirs, names in os.walk(venv, followlinks=False):
        dirs.sort()
        names.sort()
        for name in dirs:
            need(not (Path(directory) / name).is_symlink(), "no venv directory symlinks")
        for name in names:
            path = Path(directory) / name
            rel = path.relative_to(venv).as_posix()
            s = path.lstat()
            if stat.S_ISLNK(s.st_mode):
                target = os.readlink(path)
                need(rel in {"bin/python", "bin/python3"}, "unapproved venv symlink")
                need(target in {"python3.11", "python3"} and not (rel == "bin/python3" and target == "python3"),
                     "alias must point to a declared contained Python executable")
                resolved = path.resolve(strict=True)
                need(resolved == venv / "bin/python3.11" and not resolved.is_symlink(), "alias must end at canonical copied Python")
                aliases[str(path)] = {"literal_target": target, "resolved_target": str(resolved)}
                continue
            need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "ordinary unlinked venv files only")
            total += s.st_size
            need(total <= cap, "complete installed size cap")
            body = read_file(path, cap)
            files[rel] = {"path": rel, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    need("bin/python3.11" in files, "canonical copied venv Python missing")
    for name in ("bin/python3.11", "bin/python3", "bin/python"):
        if name in files:
            need(files[name]["bytes"] == base_spec["bytes"] and files[name]["sha256"] == base_spec["sha256"],
                 "venv executable differs from selected base")
    site_rel = "lib/python3.11/site-packages"
    site = venv / site_rel
    need(site.is_dir(), "expected CPython3.11 site-packages")
    dist_dirs = sorted(p for p in site.iterdir() if p.name.endswith(".dist-info"))
    need(len(dist_dirs) == 12, "unexpected installed distribution count")
    claimed, versions, records = {}, {}, []
    for dist in dist_dirs:
        need(dist.is_dir() and not dist.is_symlink(), "ordinary dist-info directory")
        metadata = BytesParser().parsebytes(read_file(dist / "METADATA", 4 * 1024 * 1024))
        names, vs = metadata.get_all("Name", []), metadata.get_all("Version", [])
        need(len(names) == len(vs) == 1, "unique package Name and Version required")
        name, version = normalized(names[0]), vs[0]
        need(name in expected and name not in versions and version == expected[name], "unexpected package name/version")
        versions[name] = version
        record_path = dist / "RECORD"
        record_rel = record_path.relative_to(venv).as_posix()
        entries = list(csv.reader(io.StringIO(read_file(record_path, 8 * 1024 * 1024).decode("utf-8"))))
        need(len(entries) <= 100000, "bounded complete RECORD entry count")
        saw_self = False
        for entry in entries:
            need(len(entry) == 3, "RECORD row must have three fields")
            member, digest, size = entry
            pp = PurePosixPath(member)
            need(member and not pp.is_absolute() and "\\" not in member, "relative POSIX RECORD member")
            path = Path(os.path.abspath(site / Path(*pp.parts)))
            need(path.is_relative_to(venv), "RECORD member escaped fresh venv")
            rel = path.relative_to(venv).as_posix()
            need(rel in files and rel not in claimed, "missing or multiply claimed RECORD member")
            claimed[rel] = name
            if rel == record_rel:
                need(not digest and not size, "RECORD self-entry must be unhashed")
                saw_self = True
                continue
            need(digest.startswith("sha256=") and size.isdecimal(), "every installed payload needs SHA256/size")
            actual = files[rel]
            encoded = base64.urlsafe_b64encode(bytes.fromhex(actual["sha256"])).rstrip(b"=").decode()
            need(digest == "sha256=" + encoded and int(size) == actual["bytes"], "installed RECORD hash/size mismatch")
        need(saw_self, "RECORD must contain exact self-entry")
        records.append({"package": name, "version": version, "record": record_rel,
                        "entries": len(entries), "record_sha256": files[record_rel]["sha256"]})
    need(versions == expected, "whole installed package set mismatch")
    scaffold = sorted(set(files) - set(claimed))
    allowed_scaffold = {"pyvenv.cfg", "bin/python3.11", "bin/python3", "bin/python",
                        "bin/activate", "bin/activate.csh", "bin/activate.fish", "bin/Activate.ps1"}
    need(set(scaffold) <= allowed_scaffold, "unexpected non-RECORD installed file")
    cfg = read_file(venv / "pyvenv.cfg", 16384).decode("utf-8")
    settings = {}
    for line in cfg.splitlines():
        if "=" in line:
            k, v = (x.strip() for x in line.split("=", 1))
            need(k not in settings, "duplicate venv configuration key")
            settings[k] = v
    need(settings.get("include-system-site-packages") == "false", "global site packages forbidden")
    need(settings.get("version") == "3.11.6", "exact base Python version required")
    inventory = b"".join((json.dumps(files[k], sort_keys=True, separators=(",", ":")) + "\n").encode()
                         for k in sorted(files))
    need(len(inventory) <= 16 * 1024 * 1024, "whole runtime inventory bound")
    receipt = write_file(venv.parent / "RUNTIME_FILES.jsonl", inventory, category="runtime")
    return {"schema": "hybrid-full-installed-runtime-identity-v1", "status": "COMPLETE",
            "file_count": len(files), "installed_regular_bytes": total,
            "file_inventory": {"path": str(venv.parent / "RUNTIME_FILES.jsonl"), **receipt},
            "packages": versions, "records": records, "scaffold": scaffold,
            "approved_aliases": aliases, "pyvenv_config": settings,
            "scientific_imports_performed": False,
            "scope": "All retained venv files hashed and installed RECORDs checked before scientific imports.",
            "shared_runtime_limitation": "Base stdlib, OpenSSL, dynamic loader and OS are shared; executable pin plus venv inventory is not hermeticity."}


def prepare_runtime(plan, lock, root, source_root, wheelhouse, deadline,
                    run_stage, read_file, write_file):
    root, source_root, wheelhouse = Path(root), Path(source_root), Path(wheelhouse)
    for path in (root, source_root, wheelhouse):
        _ordinary_tree(path)
    need(time.monotonic() < deadline, "original runtime deadline")
    need(lock.get("files") == plan.get("bootstrap"), "exact bootstrap lock/plan agreement")
    specs = plan["wheels"] + lock["files"]
    need(len(specs) == 12 and len({s["name"] for s in specs}) == 12, "exact twelve distinct wheel files")
    expected = {normalized(s["package"]): s["version"] for s in specs}
    need(len(expected) == 12, "exact twelve distinct packages")
    need({p.name for p in wheelhouse.iterdir()} == {s["name"] for s in specs}, "wheelhouse exact extent")
    declared_expanded = 0
    for s in specs:
        need(Path(s["name"]).name == s["name"] and s["name"].endswith(".whl"), "plain pinned wheel filename")
        b = read_file(wheelhouse / s["name"], s["bytes"])
        need(len(b) == s["bytes"] and hashlib.sha256(b).hexdigest() == s["sha256"], "staged whole wheel identity")
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            entries = z.infolist()
            need(len(entries) <= 100000 and len({e.filename for e in entries}) == len(entries), "complete wheel member bounds/uniqueness")
            for entry in entries:
                name = PurePosixPath(entry.filename)
                need(not name.is_absolute() and ".." not in name.parts and "\\" not in entry.filename,
                     "ordinary contained wheel member")
                need(not entry.flag_bits & 1 and not stat.S_ISLNK(entry.external_attr >> 16), "unencrypted non-symlink wheel member")
                declared_expanded += entry.file_size
                need(declared_expanded <= plan["limits"]["installed_bytes"], "complete declared wheel expansion bound")
    base = plan["base_runtime"]
    b = read_file(Path(base["path"]), base["bytes"])
    need(len(b) == base["bytes"] and hashlib.sha256(b).hexdigest() == base["sha256"], "base executable identity")
    venv = root / "venv"
    need(not venv.exists() and not venv.is_symlink(), "fresh venv path required; no reuse")
    requirements = "".join(s["package"] + "==" + s["version"] + " --hash=sha256:" + s["sha256"] + "\n"
                           for s in specs).encode()
    req_path = root / "runtime-requirements.txt"
    write_file(req_path, requirements)
    env = {"PATH": "/usr/bin:/bin", "TMPDIR": str(root),
           "LANG": "C", "LC_ALL": "C", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "PIP_CONFIG_FILE": os.devnull, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
           "VECLIB_MAXIMUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
    run_stage("runtime-create", [base["path"], "-I", "-S", "-B", "-m", "venv", "--copies", "--without-pip", str(venv)],
              str(root), env, deadline)
    python = venv / "bin/python3.11"
    _ordinary_tree(python)
    b = read_file(python, base["bytes"])
    need(len(b) == base["bytes"] and hashlib.sha256(b).hexdigest() == base["sha256"], "copied venv Python identity before execution")
    pip = next(s for s in lock["files"] if s["package"] == "pip")
    argv = [str(python), "-I", "-B", str(source_root / "bootstrap_install.py"),
            "--venv", str(venv), "--pip-wheel", str(wheelhouse / pip["name"]),
            "--pip-sha256", pip["sha256"], "--pip-bytes", str(pip["bytes"]),
            "--requirements", str(req_path), "--requirements-sha256", hashlib.sha256(requirements).hexdigest(),
            "--wheelhouse", str(wheelhouse)]
    run_stage("runtime-install", argv, str(root), env, deadline)
    # No new venv interpreter starts between installation and complete RECORD checks.
    observed = validate_installed(venv, expected, base, plan["limits"], read_file, write_file)
    receipt = write_file(root / "RUNTIME_IDENTITY.json", packed(observed))
    return {"python": str(python), "identity": observed,
            "identity_receipt": {"path": str(root / "RUNTIME_IDENTITY.json"), **receipt},
            "approved_aliases": observed["approved_aliases"]}


def verify_runtime_identity(venv, identity, read_file):
    """Before scientific import, recheck authenticated full inventory and extent.

    Caller must authenticate this identity object with the observed preparation
    receipt, verify this source file, and supply a bounded stable read callback.
    This does not trust mutable local JSON merely because a path exists.
    """
    venv = Path(venv)
    _ordinary_tree(venv)
    need(identity.get("schema") == "hybrid-full-installed-runtime-identity-v1"
         and identity.get("status") == "COMPLETE", "complete authenticated runtime identity required")
    spec = identity["file_inventory"]
    path = Path(spec["path"])
    need(path == venv.parent / "RUNTIME_FILES.jsonl" and 0 <= spec["bytes"] <= 16 * 1024 * 1024,
         "exact contained runtime inventory")
    body = read_file(path, spec["bytes"])
    need(len(body) == spec["bytes"] and hashlib.sha256(body).hexdigest() == spec["sha256"], "runtime inventory identity")
    rows = [json.loads(line) for line in body.splitlines()]
    expected = {}
    for row in rows:
        member = PurePosixPath(row["path"])
        need(not member.is_absolute() and ".." not in member.parts and "\\" not in row["path"], "contained inventory member")
        need(row["path"] not in expected and type(row["bytes"]) is int and row["bytes"] >= 0,
             "unique finite inventory row")
        expected[row["path"]] = row
    need(len(expected) == identity["file_count"], "complete runtime inventory cardinality")
    seen, aliases = set(), {}
    for directory, dirs, names in os.walk(venv, followlinks=False):
        for name in dirs:
            need(not (Path(directory) / name).is_symlink(), "no runtime directory links")
        for name in names:
            p = Path(directory) / name
            rel = p.relative_to(venv).as_posix()
            if p.is_symlink():
                need(str(p) in identity["approved_aliases"], "new runtime alias")
                target = identity["approved_aliases"][str(p)]
                need(os.readlink(p) == target["literal_target"] and str(p.resolve(strict=True)) == target["resolved_target"],
                     "runtime alias changed")
                aliases[str(p)] = target
                continue
            need(rel in expected, "unrecorded runtime file")
            spec = expected[rel]
            b = read_file(p, spec["bytes"])
            need(len(b) == spec["bytes"] and hashlib.sha256(b).hexdigest() == spec["sha256"], "installed runtime file changed")
            seen.add(rel)
    need(seen == set(expected) and aliases == identity["approved_aliases"], "runtime file/alias extent changed")
    return {"status": "COMPLETE_RUNTIME_IDENTITY_RECHECK", "files": len(seen),
            "aliases": len(aliases), "scientific_imports_performed": False}
