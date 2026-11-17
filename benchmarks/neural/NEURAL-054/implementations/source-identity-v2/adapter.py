"""Opt-in repaired entrypoints for the preserved registered-runtime package.

No native imports, source reads or scientific execution occur at import time.
Extraction retains all predecessor admission/authorization checks.
"""
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys

from source_identity import IdentityError, validate_roster


_SOURCE = Path(__file__).resolve().parents[1] / "registered-runtime/package/programme/n054"
_NAME = "n054_source_identity_v2_predecessor"
_PINS = {
    "__init__.py": "d968184192aa686920c0e8b155b5e73f3de4846567fce40529214e26b43c841e",
    "common.py": "81cd5deb2c9f83f06040218c443392ea8f1d80d81fd577a9d2ffc0877699c3eb",
    "spec.py": "7b7d5ebaca590665719ce8a122b96458b8d733c5077c7e253c8e904eeed199c9",
    "views.py": "1030b8ae66227551ec6c415b4fc4353c207d7be3fb99ec1d4866f7d0e6e1a37a",
    "preparation.py": "9443f8f1868d25f53da26521098a202aef5f400b763bc274032ca0e8c608e686",
}


def _module(name):
    # Preserve the source snapshot rather than changing a registered hash in place.
    for filename, expected in _PINS.items():
        if hashlib.sha256((_SOURCE / filename).read_bytes()).hexdigest() != expected:
            raise IdentityError("Predecessor source changed; review adapter binding")
    if _NAME not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            _NAME, _SOURCE / "__init__.py", submodule_search_locations=[str(_SOURCE)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[_NAME] = module
        spec.loader.exec_module(module)
    return importlib.import_module(f"{_NAME}.{name}")


def _roster(admission, root):
    record = admission["roster"]
    common = _module("common")
    common.relative(record["path"])
    return common.load(Path(root) / record["path"], 64 << 20,
                       {key: record[key] for key in ("bytes", "sha256")})


def _authorize(admission, selection):
    if (admission["domain"] != _module("spec").DOMAIN or
            admission["execution_selection"] != selection):
        raise IdentityError("Exact original execution selection required before roster access")


def extract(admission, source_root, image_root, output, execution_selection):
    """Check image identity before opening native FIF, eye CSV or image payloads."""
    _authorize(admission, execution_selection)
    validate_roster(_roster(admission, source_root), images=admission["images"])
    return _module("preparation").extract(
        admission, source_root, image_root, output, execution_selection)


def feature_issuer(admission, root, secret, authorization_pin):
    """Return the original issuer only after exact source/visual-row identity checks."""
    _authorize(admission, authorization_pin)
    validate_roster(_roster(admission, root), image_order=admission["image_order"])
    return _module("views").FeatureIssuer(admission, root, secret, authorization_pin)
