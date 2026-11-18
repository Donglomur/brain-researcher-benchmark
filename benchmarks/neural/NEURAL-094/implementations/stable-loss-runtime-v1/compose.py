"""Build the exact inactive NEURAL-094 stable-loss source successor.

This copies authenticated Python source, never data, model state or code results.
The operator must independently authenticate this module and RECIPE.json first.
The predecessor is read-only; a partial failed output must not be reused.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time


BASE_PIN = {"bytes": 5851, "sha256": "e3595f43bafff2400788ca62bddd30c7763ee7a9a7a83f35f4b92afdaa79d6be"}
SCORER_PIN = {"bytes": 23091, "sha256": "d88210d05247d95ca6ac244fadf549b07c4ff2889d4ed475639c5aa3b342db78"}
RECIPE_PIN = {"bytes": 3247, "sha256": "4a4cc634f41a26c835663731ce762efa05ed857fbc84612da321caa9620ea8c2"}
SCORE = "source/numerics/score_adapter.py"
NUMERICAL = "source/numerics/SOURCE_MANIFEST.json"
CHANGED = frozenset((SCORE, NUMERICAL, "RUNTIME_INVENTORY.json", "DEPENDENCIES.json",
                     "README.md", "INSTALLED_INTERFACE.md", "SOURCE_MANIFEST.json"))
SCOPE = {"sessions": 39, "mice": 10, "literal_regions": 73, "pairs": 2628, "seeds": 5}


class Refusal(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Refusal(message)


def pin(body):
    need(type(body) is bytes, "Immutable source bytes required")
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def decode(body):
    def unique(rows):
        out = {}
        for key, value in rows:
            need(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, "Nonfinite JSON"))


def recipe(body, expected_pin):
    need(expected_pin == RECIPE_PIN and pin(body) == RECIPE_PIN,
         "Exact independently selected successor recipe")
    value = decode(body)
    need(value["predecessor_manifest"] == BASE_PIN and value["stable_scorer"] == SCORER_PIN
         and value["task_id"] == "NEURAL-094" and value["execution_authority"] is False
         and value["scientific_qualification"] is False and value["readiness_promoted"] is False,
         "Fixed predecessor, reviewed scorer and inactive scope")
    need(len(value["changes"]) == len(CHANGED)
         and {row["path"] for row in value["changes"]} == CHANGED
         and all(row["overlay_path"] == "overlay/" + row["path"] for row in value["changes"]),
         "Exactly seven reviewed replacement bodies")
    return value


def closed_component(bodies, expected_manifest):
    need(type(bodies) is dict and "SOURCE_MANIFEST.json" in bodies,
         "Complete source body mapping")
    need(pin(bodies["SOURCE_MANIFEST.json"]) == expected_manifest, "Selected source manifest")
    doc = decode(bodies["SOURCE_MANIFEST.json"])
    need(doc["assignment"] == "NEURAL-094" and doc["scientific_scope"] == SCOPE
         and doc["execution_authority"] is False and doc["scientific_qualification"] is False,
         "Unchanged full scope; no execution authority")
    need(len(doc["files"]) == 34 and set(bodies) == {"SOURCE_MANIFEST.json", *doc["files"]}
         and all(pin(bodies[name]) == expected for name, expected in doc["files"].items()),
         "Every one of 35 source bodies authenticates, no additions or omissions")
    runtime = decode(bodies["RUNTIME_INVENTORY.json"])
    selected = {r["path"]: {k: r[k] for k in ("bytes", "sha256")} for r in runtime["files"]}
    need(len(runtime["files"]) == len(selected) == 29
         and set(selected) == {n for n in doc["files"] if n.startswith("source/")}
         and all(selected[n] == doc["files"][n] for n in selected)
         and runtime["bytes"] == sum(r["bytes"] for r in selected.values())
         and runtime["execution_authority"] is False and runtime["scientific_qualification"] is False
         and doc["runtime_inventory"] == pin(bodies["RUNTIME_INVENTORY.json"]),
         "Complete nested runtime inventory joins actual bodies")
    numerical = decode(bodies[NUMERICAL])
    need(len(numerical) == 8 and "score_adapter" in numerical,
         "Original closed eight-module numerical group")
    for name, row in numerical.items():
        need(row["path"] == name + ".py"
             and {k: row[k] for k in ("bytes", "sha256")} ==
                 pin(bodies["source/numerics/" + name + ".py"]),
             "Numerical loader reaches the selected executable bodies")
    return doc


def compose(predecessor_bodies, overlay_bodies, recipe_body, expected_recipe_pin):
    """Return 35 immutable source bodies; never import or execute any of them."""
    plan = recipe(recipe_body, expected_recipe_pin)
    before = closed_component(predecessor_bodies, BASE_PIN)
    need(type(overlay_bodies) is dict and set(overlay_bodies) == CHANGED,
         "Exact frozen overlay, no arbitrary source replacements")
    for row in plan["changes"]:
        name = row["path"]
        need(pin(predecessor_bodies[name]) == row["before"]
             and pin(overlay_bodies[name]) == row["after"], "Exact before/after source identities")
    result = dict(predecessor_bodies)
    result.update(overlay_bodies)
    after = closed_component(result, plan["successor_manifest"])
    need(pin(result[SCORE]) == SCORER_PIN, "Exactly the reviewed stable-loss scorer")
    need({n for n in result if result[n] != predecessor_bodies[n]} == CHANGED,
         "No unrecorded or empty successor change")
    need(all(before["files"][name] == after["files"][name]
             for name in before["files"] if name not in CHANGED),
         "Unchanged source dependencies retain their identities")
    origins = decode(result["DEPENDENCIES.json"])["public_python_origins"]
    need(sum(r["path"] == SCORE for r in origins) == 1
         and all({k: r[k] for k in ("bytes", "sha256")} == pin(result[r["path"]]) for r in origins),
         "Recorded Python origins join successor, including repaired scorer")
    return result


class Budget:
    def __init__(self, read_bytes, write_bytes, seconds):
        need(type(read_bytes) is int and read_bytes > 0 and type(write_bytes) is int and write_bytes > 0,
             "Explicit positive source read/write allowances")
        need(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0,
             "Explicit finite source-copy deadline")
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.read_bytes = self.write_bytes = 0
        self.end = time.monotonic() + seconds

    def tick(self):
        need(time.monotonic() < self.end, "Source construction deadline")

    def charge(self, kind, count):
        self.tick()
        need(kind in ("read", "write") and type(count) is int and count >= 0, "Typed logical charge")
        name = kind + "_bytes"
        setattr(self, name, getattr(self, name) + count)
        need(getattr(self, name) <= getattr(self, kind + "_limit"), "Source " + kind + " allowance")


def ordinary(root, name):
    need(type(name) is str and name and not name.startswith("/") and "\\" not in name
         and "\x00" not in name and all(x not in ("", ".", "..") for x in name.split("/")),
         "Safe fixed relative source path")
    target = Path(root) / name
    need(not any(p.is_symlink() for p in (target, *target.parents)), "Unlinked source/output ancestry")
    return target


def read(root, name, expected, budget):
    target = ordinary(root, name)
    budget.charge("read", expected["bytes"] + 1)
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == expected["bytes"],
             "Exact ordinary source file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        after, named = os.fstat(fd), target.lstat()
        need(all(getattr(first, k) == getattr(after, k) == getattr(named, k) for k in
                 ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")),
             "Stable source file and name")
    finally:
        os.close(fd)
    need(pin(body) == expected, "Exact captured source body")
    return body


def materialize(predecessor_root, overlay_root, destination, expected_recipe_pin, budget):
    """Copy this finite successor to a fresh root; no runtime or data launch."""
    roots = [Path(p) for p in (predecessor_root, overlay_root, destination)]
    need(all(p.is_absolute() and p.is_dir() and not any(x.is_symlink() for x in (p, *p.parents))
             for p in roots), "Absolute unlinked source and destination roots")
    # Lexical parents do not reveal an ancestor written as child/.. . Resolve
    # only after the unlinked-ancestry check, before testing actual separation.
    roots = [p.resolve(strict=True) for p in roots]
    need(all(a != b and a not in b.parents and b not in a.parents
             for i, a in enumerate(roots) for b in roots[i + 1:]), "Three disjoint roots")
    base, overlay, target = roots
    need(not any(target.iterdir()), "Fresh empty successor destination")
    recipe_body = read(overlay, "RECIPE.json", expected_recipe_pin, budget)
    plan = recipe(recipe_body, expected_recipe_pin)
    manifest = read(base, "SOURCE_MANIFEST.json", BASE_PIN, budget)
    predecessor = {"SOURCE_MANIFEST.json": manifest}
    predecessor.update({name: read(base, name, expected, budget)
                        for name, expected in decode(manifest)["files"].items()})
    replacements = {r["path"]: read(overlay, r["overlay_path"], r["after"], budget)
                    for r in plan["changes"]}
    bodies = compose(predecessor, replacements, recipe_body, expected_recipe_pin)
    # Reserve the complete write before the first output; failed partial copies stay charged.
    budget.charge("write", sum(len(body) for body in bodies.values()))
    for name, body in sorted(bodies.items()):
        budget.tick()
        output = ordinary(target, name)
        output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                need(stream.write(body) == len(body), "Complete source write")
                stream.flush()
                os.fsync(stream.fileno())
            os.fchmod(fd, 0o444)
        finally:
            os.close(fd)
    return {"source_manifest": plan["successor_manifest"], "runtime_inventory": pin(bodies["RUNTIME_INVENTORY.json"]),
            "source_files": len(bodies), "logical_read_bytes": budget.read_bytes,
            "logical_write_reservation_bytes": budget.write_bytes,
            "execution_authority": False, "scientific_qualification": False}
