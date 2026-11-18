"""Externally selected package verification; no installation or scientific admission.

This entry point is trusted operator code. The caller must select its exact bytes
and the expected PACKAGE.json digest outside this directory. No source embeds
the digest of a manifest which hashes that source.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

PROFILE_ID = "n019-dejavu-sans-mono-12-rgb-v1"
FONT = [340240, "602ec86b8948cfcd956482fe64f94c36c867770149ef2f791d4613f443bcecb3"]
NOTICE = [4816, "d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e"]
VIEWER = [16459, "25da9e4d159d17cdaa8c912312a86b17d41eef4774c408d642c59de99e7e9f37"]
LIMITS = {"png_transport.py": 32768, "runtime_preflight.py": 16384,
          "PROFILE.json": 8192, "assets/DejaVuSansMono.ttf": FONT[0],
          "assets/LICENSE_DEJAVU": NOTICE[0]}
REFERENCE_RUNTIME = {"pillow": "12.3.0", "freetype": "2.14.3",
                     "numpy_distribution_version": "2.4.6"}
SETTINGS = {"font_size_px": 12, "pixel_format": "RGB", "layout": "BASIC",
            "anchor": "ls", "stroke_width": 0, "foreground": "black",
            "background": "white", "zero_fill": "#ffffff", "nonzero_fill": "#e6eef8",
            "cell_border": "#cccccc", "cell_size": [53, 23], "cell_step": [54, 24],
            "crop_max": [16, 20], "canvas_max": [1180, 928],
            "png_optimize": False, "png_compress_level": 9,
            "max_png_bytes": 262144, "max_frame_bytes": 393216}
HERE = Path(__file__).resolve().parent


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def parse(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "nonfinite JSON"))


def read_bounded(path, cap, *, identity=None):
    """Read exact stable regular bytes; reject leaf links, hardlinks and overflow."""
    path = Path(path).absolute()
    need(type(cap) is int and 0 < cap <= 1048576 and len(str(path)) <= 4096,
         "bounded dependency request")
    need(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NONBLOCK"), "POSIX guards required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, "dependency type or extent mismatch")
        chunks, remaining = [], cap + 1
        while remaining:
            block = os.read(fd, min(65536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        raw = b"".join(chunks)
        need(0 < len(raw) <= cap, "dependency overflow")
        if identity is not None:
            need([len(raw), sha(raw)] == identity, "dependency identity mismatch")
        after, named = os.fstat(fd), path.lstat()
        attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        need(all(getattr(before, key) == getattr(after, key) == getattr(named, key)
                 for key in attrs), "dependency changed during read")
        return raw
    finally:
        os.close(fd)


def valid_pin(value, cap):
    return (type(value) is list and len(value) == 2 and type(value[0]) is int and
            0 < value[0] <= cap and type(value[1]) is str and
            re.fullmatch(r"[0-9a-f]{64}", value[1]) is not None)


def expected_profile(files):
    return {"schema": "neural019-raster-profile/v1", "profile_id": PROFILE_ID,
            "font": {"path": "assets/DejaVuSansMono.ttf", "pin": FONT},
            "notice": {"path": "assets/LICENSE_DEJAVU", "pin": NOTICE},
            "renderer": files["png_transport.py"], "preflight": files["runtime_preflight.py"],
            "viewer": VIEWER, "rendering": SETTINGS,
            "runtime": {"pillow_required": "12.3.0", "freetype_policy": "observed_only",
                        "prospective_reference": REFERENCE_RUNTIME},
            "support": {"calibration_trials": 1340, "assessment_trials": 126,
                        "units": 137, "bins": 140, "response_values": 35280},
            "scope": "Versioned presentation; no pixel equivalence, scientific mode or readability admission."}


def verify_package(manifest_path, expected_manifest_sha256, viewer_path, *, font_path=None):
    """Authenticate every byte before any dynamic component execution.

    The external digest is mandatory; deriving it from this unselected directory
    inside the operator route would defeat the selection boundary. Font override
    admits only identical bytes, allowing the unchanged mechanical test CLI.
    """
    need(type(expected_manifest_sha256) is str and
         re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is not None,
         "externally selected manifest digest required")
    manifest_path = Path(manifest_path).absolute()
    raw = read_bounded(manifest_path, 8192)
    need(sha(raw) == expected_manifest_sha256, "selected manifest mismatch")
    manifest = parse(raw)
    need(type(manifest) is dict and set(manifest) == {"schema", "profile_id", "files", "viewer"},
         "exact package fields required")
    need(manifest["schema"] == "neural019-selected-package/v1" and
         manifest["profile_id"] == PROFILE_ID and manifest["viewer"] == VIEWER,
         "package profile or viewer mismatch")
    files = manifest["files"]
    need(type(files) is dict and set(files) == set(LIMITS), "exact package inventory")
    need(all(valid_pin(files[name], cap) for name, cap in LIMITS.items()), "invalid package pin")
    need(files["assets/DejaVuSansMono.ttf"] == FONT and files["assets/LICENSE_DEJAVU"] == NOTICE,
         "exact font and complete notice required")
    blobs = {name: read_bounded(manifest_path.parent / name, cap, identity=files[name])
             for name, cap in LIMITS.items()}
    # Check this trusted entry point too, without a self-referential embedded hash.
    need(read_bounded(Path(__file__), LIMITS["runtime_preflight.py"],
                      identity=files["runtime_preflight.py"]) == blobs["runtime_preflight.py"],
         "entry point differs from selected package")
    if font_path is not None:
        need(read_bounded(font_path, FONT[0], identity=FONT) == blobs["assets/DejaVuSansMono.ttf"],
             "font override differs")
    profile = parse(blobs["PROFILE.json"])
    need(profile == expected_profile(files), "profile settings or source bindings differ")
    blobs["viewer.py"] = read_bounded(viewer_path, VIEWER[0], identity=VIEWER)
    binding = {"manifest_sha256": expected_manifest_sha256,
               "profile_sha256": files["PROFILE.json"][1],
               "renderer_sha256": files["png_transport.py"][1],
               "preflight_sha256": files["runtime_preflight.py"][1],
               "viewer_sha256": VIEWER[1], "font_sha256": FONT[1], "notice_sha256": NOTICE[1]}
    return blobs, profile, binding


def renderer_versions():
    observed = {"pillow": None, "freetype": None, "numpy_distribution_version": None}
    try:
        import PIL
        from PIL import features
        observed["pillow"] = PIL.__version__
        observed["freetype"] = features.version("freetype2")
    except (ImportError, OSError):
        pass
    try:
        observed["numpy_distribution_version"] = importlib.metadata.version("numpy")
    except importlib.metadata.PackageNotFoundError:
        pass
    return observed


def observation(binding, *, verify_only=False):
    result = {"status": "selected_package_bytes_verified", "profile_id": PROFILE_ID,
              "python_version": ".".join(str(v) for v in sys.version_info[:3]),
              "package_binding": dict(binding), "source_verified": True,
              "renderer_constructed": False, "runtime_admitted": False,
              "full_png_CI_provisioned": False, "scientific_mode_selected": False,
              "authentic_readability_qualified": False, "binary_environment_qualified": False}
    if not verify_only:
        versions = renderer_versions()
        prerequisites = versions["pillow"] == "12.3.0" and bool(versions["numpy_distribution_version"])
        result.update(status="renderer_prerequisites_observed" if prerequisites else "held",
                      observed_runtime=versions, renderer_prerequisites_observed=prerequisites,
                      prospective_reference_runtime=dict(REFERENCE_RUNTIME),
                      reference_runtime_matches=versions == REFERENCE_RUNTIME,
                      freetype_policy="Observed software profile; no universal renderer or scientific gate.",
                      numpy_importability_qualified=False)
    return result


def compile_module(raw, path, name, extra=None):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    if extra:
        module.__dict__.update(extra)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_selected(manifest_path, expected_manifest_sha256, viewer_path):
    """Trusted operator route; never hand its Python objects to a participant."""
    blobs, profile, binding = verify_package(manifest_path, expected_manifest_sha256, viewer_path)
    observed = observation(binding)
    need(observed["status"] == "renderer_prerequisites_observed", "renderer prerequisites held")
    transport = compile_module(blobs["png_transport.py"], Path(manifest_path).parent / "png_transport.py",
                               "neural019_selected_dejavu_transport",
                               {"_SELECTED_PACKAGE_BINDING": types.MappingProxyType(dict(binding))})
    viewer = compile_module(blobs["viewer.py"], viewer_path, "neural019_selected_frozen_viewer")
    renderer = transport.Renderer(blobs["assets/DejaVuSansMono.ttf"])
    return types.SimpleNamespace(transport=transport, viewer=viewer, renderer=renderer,
                                 binding=types.MappingProxyType(dict(binding)), observation=observed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=HERE / "PACKAGE.json")
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        _, _, binding = verify_package(args.manifest, args.manifest_sha256, args.viewer, font_path=args.font)
        result = observation(binding, verify_only=args.verify_only)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        result = {"status": "held", "error_type": type(exc).__name__,
                  "runtime_admitted": False, "full_png_CI_provisioned": False,
                  "scientific_mode_selected": False}
    print(json_bytes(result).decode(), end="")
    return 2 if result["status"] == "held" else 0


if __name__ == "__main__":
    raise SystemExit(main())
