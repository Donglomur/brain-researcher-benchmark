"""Score the frozen NEURAL-012 detector panel without an analyst submission.

This trusted-operator command consumes the existing post-prediction analysis
packet. It does not prepare EEG, run a detector, admit execution evidence, or
grant scientific qualification. Its numerical implementation is the preserved
registered runtime, checked against the exact source pins below before import.
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import types


RUNTIME = (Path(__file__).resolve().parent.parent / "registered-runtime" /
           "runtime/source/neural012/private")
# Dependency order matters because the preserved source uses absolute imports.
SOURCE_PINS = {
    "io_contract": "2342e1a7f09164b6ca7cee8a7b851603dabb7c96dd0624c60180ae3a169f3b51",
    "event_protocol": "462afe5bb002df77567bda53c232607b86552a658f99515c283774635956599c",
    "scientific_contract": "558db102d0d8ab0bba545c231fe8df92720e8e1b5c37195bef662ea3834b7e08",
    "protocol_policy": "2ffc8bbd3b311098943903652a2bf631d9759010c93f459ce1694ad9db3018c4",
    "phase_provenance": "1068bda3923a982b202678998f194fdf127d0d74717846da8a28083fa084237d",
    "vendor.event_protocol": "462afe5bb002df77567bda53c232607b86552a658f99515c283774635956599c",
    "vendor.analysis_core": "c01bafc0b19168224e652631b7d6c04e6ca82967d292763f045eb096b1000a0b",
    "analysis": "36206b4e197fe3d62fe9bb8d8895cde5b8a374d9fedec587a418b1f140d18caa",
}


def load_scoring():
    """Load only checked source bytes and restore all temporary import aliases.

    Intended for the serial CLI; callers must not race this operation with other
    imports. Reading and compiling the same checked bytes avoids a second source
    read after verification. No scientific dependencies or data are imported.
    """
    sources = {}
    for name, expected in SOURCE_PINS.items():
        path = RUNTIME / (name.replace(".", "/") + ".py")
        with path.open("rb") as stream:
            raw = stream.read(100001)
        if len(raw) > 100000 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("preserved scorer source mismatch: " + name)
        sources[name] = (path, raw)
    names = ["vendor", *SOURCE_PINS]
    previous = {name: sys.modules.get(name) for name in names}
    loaded = {}
    try:
        vendor = types.ModuleType("vendor")
        vendor.__path__ = [str(RUNTIME / "vendor")]
        sys.modules["vendor"] = vendor
        for name, (path, raw) in sources.items():
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            if name.startswith("vendor."):
                setattr(vendor, name.split(".", 1)[1], module)
            exec(compile(raw, str(path), "exec"), module.__dict__)
            loaded[name] = module
        return loaded["analysis"], loaded["io_contract"]
    finally:
        for name in names:
            if previous[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous[name]


# Raw source annotation entries, before the fixed merge/split event policy.
# Original annotation_binding.py admits 198 CHB entries; combine_panels.py
# admits 47 Siena entries. These totals are support checks, not label identity.
RAW_ANNOTATION_COUNTS = {"CHB": 198, "Siena": 47}


def score_bytes(raw, input_sha256, analysis, io):
    """Return the original scientific endpoint bound to its complete input."""
    io.need(type(input_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", input_sha256) is not None,
            "exact analysis packet SHA256 required")
    io.need(hashlib.sha256(raw).hexdigest() == input_sha256,
            "input SHA256 mismatch")
    # This invokes the original complete-panel, four-arm, profile and 96-lineage
    # validation; it never calls grade() or accepts a reconstruction submission.
    packet = io.strict(raw)
    rows = analysis.validate_packet(packet)
    counts = {cohort: sum(len(row["annotations"]) for row in rows
                          if row["cohort"] == cohort)
              for cohort in RAW_ANNOTATION_COUNTS}
    io.need(counts == RAW_ANNOTATION_COUNTS,
            "complete original raw annotation support: 198 CHB and 47 Siena")
    result = analysis.detector_outcomes(packet)
    result["input_sha256"] = input_sha256
    result["scorer_sources_sha256"] = hashlib.sha256(io.encoded(SOURCE_PINS)).hexdigest()
    result["evidence_scope"] = "post_prediction_packet_recalculation_only"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    analysis, io = load_scoring()
    io.need(not args.output.exists() and not args.output.is_symlink(),
            "fresh detector outcome path before input access")
    raw = io.read(args.input, io.MAX_JSON, args.input_sha256)
    result = score_bytes(raw, args.input_sha256, analysis, io)
    io.write(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
