"""Compose one source-pinned actor without importing or executing candidate code."""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

CAP = 65536


def need(ok, message):
    if not ok:
        raise ValueError(message)


def capture(path, expected):
    path = Path(path).absolute()
    need(".." not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), "Unlinked ordinary source path required")
    original = path.stat()
    need(stat.S_ISREG(original.st_mode) and original.st_nlink == 1 and 0 < original.st_size <= CAP, "Bounded source required")
    fingerprint = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    with path.open("rb") as stream:
        need(fingerprint(os.fstat(stream.fileno())) == fingerprint(original), "Source changed before capture")
        body = stream.read(original.st_size + 1)
        need(fingerprint(os.fstat(stream.fileno())) == fingerprint(original), "Source changed during capture")
    need(len(body) == original.st_size and fingerprint(path.stat()) == fingerprint(original)
         and hashlib.sha256(body).hexdigest() == expected, "Source pin mismatch")
    return body


def assemble(template, callback):
    need(type(template) is bytes and type(callback) is bytes and 0 < len(template) <= CAP and 0 < len(callback) <= CAP,
         "Two finite source bodies required")
    tree = ast.parse(callback.decode("utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "decide"]
    need(len(functions) == 1 and not functions[0].decorator_list, "One plain top-level decide(context) function required")
    args = functions[0].args
    need(len(args.posonlyargs) + len(args.args) == 1 and not args.vararg and not args.kwarg and not args.kwonlyargs
         and not args.defaults, "Exact one-context callback signature required")
    # Parsing source is not candidate execution or proof of scientific procedure.
    expected = {"bytes": len(callback), "sha256": hashlib.sha256(callback).hexdigest()}
    replacements = {
        b"CALLBACK_BASE64 = None  # ASSEMBLED_CALLBACK_BYTES":
            ("CALLBACK_BASE64 = " + repr(base64.b64encode(callback).decode("ascii")) + "  # ASSEMBLED_CALLBACK_BYTES").encode(),
        b"CALLBACK_PIN = None  # ASSEMBLED_CALLBACK_PIN":
            ("CALLBACK_PIN = " + repr(expected) + "  # ASSEMBLED_CALLBACK_PIN").encode(),
    }
    result = template
    for old, new in replacements.items():
        need(result.count(old) == 1, "Exact unassembled template marker required")
        result = result.replace(old, new)
    need(len(result) <= CAP, "Assembled actor exceeds original single-source cap")
    freeze = json.dumps({"op": "freeze", "source": result.decode("utf-8")}, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode() + b"\n"
    need(len(freeze) <= CAP, "Assembled freeze envelope exceeds original actor wire cap")
    ast.parse(result.decode("utf-8"))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("template", "template-sha256", "callback", "callback-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    template = capture(args.template, args.template_sha256)
    callback = capture(args.callback, args.callback_sha256)
    result = assemble(template, callback)
    output = Path(args.output).absolute()
    need(".." not in output.parts and all(not p.is_symlink() for p in (output, *output.parents))
         and output.parent.is_dir(), "Fresh ordinary output required")
    with output.open("xb") as stream:
        stream.write(result)
        stream.flush()
        os.fsync(stream.fileno())
    print("actor_sha256=" + hashlib.sha256(result).hexdigest() + " bytes=" + str(len(result)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, SyntaxError) as error:
        print(type(error).__name__ + ": " + str(error)[:1600], file=sys.stderr)
        raise SystemExit(2)
