"""Static, task-specific FIND-032 official-source bundle diagnostic.

No source is imported or executed. Internal pins and static bindings are not
upstream authentication, runtime compatibility, or publication parity.
"""
import ast
import hashlib
import re


REVISION = "a454439aec8936ff9de2199ab255472c7d140b8c"
ROLES = {
    "base": "base.py",
    "sound": "reproduce_and_reorder_sound.py",
    "omission": "reproduce_and_reorder_omission.py",
}
MAX_BODY_BYTES = 131072
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class BundleError(ValueError):
    """The proposed source bundle is not internally consistent."""


def _require(condition, message):
    if not condition:
        raise BundleError(message)


def _targets(node):
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        result = set()
        for item in node.elts:
            result.update(_targets(item))
        return result
    return set()


def _direct_bindings(tree):
    """Syntactic, unconditional module bindings; not Python execution.

    Conditional definitions and implicit import/module side effects are not
    classified as available. Del statements remove directly deleted names.
    Presence does not prove successful initialization or a callable signature.
    """
    bound = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                bound.update(_targets(target))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            bound.update(_targets(node.target))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for item in node.names:
                if item.name != "*":
                    bound.add(item.asname or (item.name.split(".")[0]
                              if isinstance(node, ast.Import) else item.name))
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                bound.difference_update(_targets(target))
    return bound


def inspect_bundle(bundle):
    """Inspect exactly the pinned base/sound/singular-omission source roles.

    Each role is a closed dict with filename, revision, body (bytes), sha256.
    The caller must separately establish where those bytes actually came from.
    This function never downloads, repairs, combines revisions, or issues an
    admission decision. In particular it does not repair missing author helpers.
    """
    _require(type(bundle) is dict and set(bundle) == set(ROLES),
             "exact base, sound and omission roles required")
    trees, identities = {}, {}
    for role, filename in ROLES.items():
        item = bundle[role]
        _require(type(item) is dict and set(item) ==
                 {"filename", "revision", "body", "sha256"},
                 "closed source-role descriptor required")
        _require(item["filename"] == filename, "wrong source-role filename")
        _require(item["revision"] == REVISION,
                 "all roles must retain the same selected source revision")
        body = item["body"]
        _require(type(body) is bytes and 0 < len(body) <= MAX_BODY_BYTES,
                 "nonempty bounded source bytes required")
        digest = item["sha256"]
        _require(type(digest) is str and HEX64.fullmatch(digest) is not None and
                 hashlib.sha256(body).hexdigest() == digest,
                 "source body differs from supplied sha256")
        try:
            text = body.decode("utf-8", errors="strict")
            trees[role] = ast.parse(text, filename=filename)
        except (UnicodeError, SyntaxError, ValueError, RecursionError) as error:
            raise BundleError("source body is not supported UTF-8 Python text") from error
        identities[role] = {"filename": filename, "revision": REVISION,
                            "bytes": len(body), "sha256": digest}
    bound = _direct_bindings(trees["base"])
    consumers = {}
    for role in ("sound", "omission"):
        requested = set()
        wildcard = False
        relative = False
        # Include function/conditional imports too: this is a requirement census,
        # not a claim that every import is reached in an actual execution.
        for node in ast.walk(trees[role]):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level and node.module is None and any(
                    item.name == "base" for item in node.names):
                # ``from . import base`` refers to a relative module binding,
                # not the selected top-level base.py or a proven export of it.
                relative = True
                continue
            if node.module == "base":
                wildcard |= any(item.name == "*" for item in node.names)
                if node.level:
                    relative = True
                    continue
                requested.update(item.name for item in node.names if item.name != "*")
        consumers[role] = {
            "requested_base_names": sorted(requested),
            "missing_direct_base_bindings": sorted(requested - bound),
            "wildcard_import_unresolved": wildcard,
            "relative_base_import_unresolved": relative,
        }
    gap = any(row["missing_direct_base_bindings"] or row["wildcard_import_unresolved"] or
              row["relative_base_import_unresolved"]
              for row in consumers.values())
    return {
        "schema": "find032-source-bundle-preflight/v1",
        "task_id": "PAPER-FIND-032",
        "source_revision": REVISION,
        "source_identities": identities,
        "direct_base_bindings": sorted(bound),
        "consumers": consumers,
        "diagnostic": "static_source_gap" if gap else "no_direct_binding_gap_detected",
        "admission_issued": False,
        "source_executed": False,
        "upstream_authentication_established": False,
        "runtime_executability_established": False,
        "publication_parity_established": False,
        "limits": [
            "Pins establish internal byte identity, not official provenance.",
            "Static binding presence does not prove import execution, values, signatures or scientific compatibility.",
            "Conditional/dynamic exports, wildcard imports and relative base imports remain unresolved.",
            "No participant, trial, fold, model, timing, output or inference identity is qualified.",
        ],
    }
