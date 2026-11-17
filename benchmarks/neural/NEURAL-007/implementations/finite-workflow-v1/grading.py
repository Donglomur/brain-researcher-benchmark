"""Complete public validation before one protected, descriptive paired grade.

The metric implementation is the authenticated original candidate adapter.
This trusted worker never imports the participant programme or edits predictions.
"""
from dataclasses import dataclass, field
import io
import json
from pathlib import Path
import sys
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


@dataclass(frozen=True)
class Validated:
    specification: object
    viewer: object
    programme: object
    references: object
    _adapter: object = field(repr=False, compare=False)


def _freeze(value):
    # Original validator arrays are already read-only. Structural immutability is
    # for the trusted grading process, not a sandbox for hostile Python imports.
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    return value


def _descriptor(value, cap):
    common.need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
                and type(value["path"]) is str and Path(value["path"]).is_absolute(),
                "exact absolute public descriptor")
    common.checked_pin(common.plain(value), cap)
    return Path(value["path"]), common.plain(value)


def validate_public(viewer, parts, refs, adapter=None):
    """Read and validate all 5,450 rows in both arms and both saved references."""
    if adapter is None:
        adapter = common.load_sources()[0]
    cases = tuple(adapter.Case(name, epochs) for name, epochs in common.SPEC_CASES)
    spec = adapter.checked_specification(adapter.Specification(cases, ("YASA", "RF")))
    common.need(type(parts) is dict and set(parts) == {c.case_id for c in cases},
                "exact complete programme parts")
    common.need(type(refs) is dict and set(refs) == {"YASA", "RF"}, "exact two references")
    # Descriptor validation also finishes before opening any prediction bundle.
    vpath, vpin = _descriptor(viewer, 4_000_000)
    pp = {c.case_id: _descriptor(parts[c.case_id], 400_000) for c in cases}
    rr = {name: _descriptor(refs[name], 4_000_000) for name in spec.comparator_names}
    view = adapter.validate_submission(vpath, vpin, spec)
    people, part_pins = {}, {}
    for case in cases:
        part = adapter.validate_submission(*pp[case.case_id], adapter.Specification((case,), ()))
        # Join only the people dictionaries: no reserialization, clipping,
        # normalization, mask filtering, precision conversion or new inference.
        people[case.case_id] = part["people"][case.case_id]
        part_pins[case.case_id] = part["file"]
    references = {name: adapter.validate_submission(*rr[name], spec) for name in spec.comparator_names}
    programme = {"people": people, "parts": part_pins}
    return Validated(spec, _freeze(view), _freeze(programme), _freeze(references), adapter)


def compare(validated, target_loader, adapter=None):
    """Call the protected loader once, then retain all signed descriptive deltas."""
    common.need(isinstance(validated, Validated) and callable(target_loader), "validated pair and trusted loader")
    if adapter is None:
        adapter = validated._adapter
    spec = adapter.checked_specification(validated.specification)
    common.need(tuple((c.case_id, c.epochs) for c in spec.cases) == common.SPEC_CASES
                and spec.comparator_names == ("YASA", "RF"), "original complete paired panel")
    targets = adapter._checked_targets(target_loader(), spec)
    arms = {"viewer": adapter._score(validated.viewer, targets, spec),
            "programme": adapter._score(validated.programme, targets, spec)}
    references = {name: adapter._score(validated.references[name], targets, spec)
                  for name in spec.comparator_names}
    differences = {"programme_minus_viewer": adapter._difference(arms["programme"], arms["viewer"])}
    for arm, score in arms.items():
        for name, reference in references.items():
            differences[arm + "_minus_" + name] = adapter._difference(score, reference)
    return {
        "schema": "sleep007_finite_paired_grade_v1", "status": "valid_descriptive_paired_result",
        "n_people": len(spec.cases), "full_epochs": sum(c.epochs for c in spec.cases),
        "class_order": list(adapter.CLASS_ORDER), "row_sum_atol": adapter.ROW_SUM_ATOL,
        "argmax_tie_rule": "first_class_index", "normalization_or_clipping": False,
        "arms": arms, "references": references, "signed_differences": differences,
        "input_freezes": {"viewer": dict(validated.viewer["file"]),
                         "programme_parts": {k: dict(v) for k, v in validated.programme["parts"].items()},
                         "references": {k: dict(v["file"]) for k, v in validated.references.items()}},
        "private_loader_calls": 1, "all_public_bundles_validated_before_private_loader": True,
        "binary_scientific_success_threshold": None, "population_inference": False,
        "confidence_interval": None, "p_value": None,
        "epoch_count_is_not_independent_sample_size": True,
        "scope": "Two exposed development people; 5,450 complete clock epochs before target masking.",
        "interpretation": "Workflow-capability comparison with different allowed information and tools; "
                          "not a causal tools-only effect, native-understanding result or unseen-person claim.",
    }


def private_targets(private_locations, original_assets, adapter=None, helper=None):
    """Read original pinned targets; caller must invoke only after public validation."""
    if adapter is None or helper is None:
        loaded = common.load_sources()
        adapter = loaded[0] if adapter is None else adapter
        helper = loaded[1] if helper is None else helper
    locations = json.loads(common.descriptor_read(private_locations, 16_384))
    files = original_assets["private_files"]
    common.need(type(locations) is dict and set(locations) == {"schema", "files"}
                and locations["schema"] == "sleep007_private_locations_v1"
                and type(locations["files"]) is dict and set(locations["files"]) == set(files)
                and set(files) == {"manifest.json", *(name + "_labels.npz" for name, _ in common.SPEC_CASES)},
                "exact original private file locations")
    paths = locations["files"]
    common.need(all(type(path) is str and Path(path).is_absolute() for path in paths.values()),
                "absolute original private paths")
    manifest = json.loads(adapter._locked_bytes(paths["manifest.json"], common.plain(files["manifest.json"])))
    common.need(manifest == original_assets["private_manifest_expected"], "original private lineage manifest")
    targets = {}
    for name, epochs in common.SPEC_CASES:
        case = adapter.Case(name, epochs)
        filename = name + "_labels.npz"
        raw = adapter._locked_bytes(paths[filename], common.plain(files[filename]))
        helper.target_headers(raw, case)
        with adapter.np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=4096) as arrays:
            targets[name] = {key: arrays[key] for key in ("epoch_id", "stage", "score_mask")}
    return targets


def main(argv=None):
    """Hash-authenticated worker request; errors expose only fixed stage labels."""
    stage, calls = "request", 0
    try:
        argv = sys.argv[1:] if argv is None else argv
        common.need(len(argv) == 6 and set(argv[::2]) == {"--request", "--bytes", "--sha256"},
                    "exact worker arguments")
        flags = dict(zip(argv[::2], argv[1::2]))
        request = json.loads(common.read(flags["--request"],
                             {"bytes": int(flags["--bytes"]), "sha256": flags["--sha256"]}, 131_072))
        common.need(type(request) is dict and set(request) == {
            "schema", "source_freeze", "viewer_proof", "programme_commit", "viewer", "parts", "references", "private_locations"}
                    and request["schema"] == "sleep007_finite_grade_v1", "exact grader request")
        stage = "source_authentication"
        common.authenticate_sources(request["source_freeze"])
        import provenance
        stage = "public_provenance"
        provenance.admit_grade(request)
        adapter, helper, assets, _ = common.load_sources()
        stage = "public_validation"
        validated = validate_public(request["viewer"], request["parts"], request["references"], adapter)

        def load_once():
            nonlocal calls, stage
            stage = "private_validation"
            calls += 1
            common.need(calls == 1, "exactly one private load")
            return private_targets(request["private_locations"], assets, adapter, helper)

        result = compare(validated, load_once, adapter)
        stage = "report"
        raw = common.json_bytes(result)
        common.need(len(raw) <= 200_000, "bounded paired grade report")
        sys.stdout.write(raw.decode("utf-8"))
        return 0
    except Exception:
        sys.stdout.write(common.json_bytes({"status": "failed", "failure_stage": stage,
                                           "private_loader_calls": calls}).decode("utf-8"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
